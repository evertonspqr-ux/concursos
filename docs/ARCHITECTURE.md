# Arquitetura — Concursos

## Stack e convenções

- Frontend: Next.js (App Router), TypeScript e Tailwind CSS.
- Backend: FastAPI com SQLAlchemy assíncrono.
- Banco: PostgreSQL 16 com extensão `pgvector`.
- IDs: UUID. Datas: ISO 8601 em UTC. Timezone: `America/Sao_Paulo`.
- API: REST com prefixo `/api/v1/`. Todo dado de usuário é filtrado por `user_id`.
- Auth: `Authorization: Bearer <JWT>`; `user_id` do cliente nunca autoriza uma operação.

## Entidades canônicas

`User`, `Exam`, `Position`, `Notice`, `Subject`, `Topic`, `Question`, `ExamPaper`, `Simulation`, `StudyPlan`, `StudySession`, `CutoffScore`, `UserPerformance`.

Use esses nomes em inglês, no singular, para modelos, tabelas e contratos de API. Não introduza sinônimos como `Contest` ou `Concurso` para `Exam`.

## Limites

- `frontend/`: interface e cliente HTTP; sem regra de negócio crítica.
- `backend/app/`: API e persistência.
- Alterações do schema de produção exigem migração Alembic.
- Cada bloco muda somente seus módulos e atualiza este documento ao ampliar contratos compartilhados.

## Estado atual

O bloco 1 entrega infraestrutura executável e auth básica. O bloco 2 entrega o schema de domínio no módulo `backend/app/models.py`, incluindo as tabelas de associação necessárias: `ExamSubject`, `ExamPaperQuestion`, `SimulationQuestion`, `UserQuestionAttempt` e `StudyPlanItem`.

O bloco 3 oferece `POST /api/v1/exams/{exam_id}/notices` para PDFs autenticados. Arquivos são guardados fora do banco por `storage_key`; texto e metadados extraídos ficam em `Notice`. O tamanho máximo e o diretório de armazenamento são configuráveis por ambiente.

O bloco 4 oferece `POST /api/v1/exams/{exam_id}/notices/{notice_id}/analyze`. A análise heurística é persistida em `Notice.extraction_metadata.analysis` e aplica dados identificados a `Exam`, `Position`, `Subject` e `ExamSubject`.

O bloco 5 oferece provas e gabaritos em `/api/v1/exams/{exam_id}/papers`. Questões importadas recebem uma ordem imutável por prova; respostas do usuário ficam em `UserQuestionAttempt`, e a correção usa o peso de `ExamPaperQuestion`.

O bloco 6 oferece classificação de `Question` em `/api/v1/questions`:

- `POST /api/v1/questions/{question_id}/classify`: classifica uma questão contra o catálogo atual de `Subject`/`Topic`.
- `POST /api/v1/questions/classify:batch`: classifica em lote (até 200 IDs por chamada).
- `GET /api/v1/questions/review-queue`: lista questões com `classification_status = needs_review`.
- `PUT /api/v1/questions/{question_id}/classification`: revisão humana; sobrescreve `subject_id`/`topic_id`, marca `classification_status = classified` e `classification_confidence = 1.0`.

`Question` ganhou duas colunas aditivas (sem renomear as existentes): `classification_status` (`unclassified` | `classified` | `needs_review`) e `classification_metadata` (JSONB com `method`, `rationale` e `classified_at`). `subject_id`, `topic_id` e `classification_confidence` continuam com o mesmo significado.

O classificador (`backend/app/classifier.py`) tenta primeiro um provedor de IA plugável (`backend/app/ai_provider.py`, adaptador Anthropic via `ANTHROPIC_API_KEY`); se o provedor não estiver configurado ou a chamada falhar, cai para uma heurística determinística por sobreposição léxica entre o enunciado e os nomes do catálogo (`classifier.heuristic_classify`), sempre limitada a confiança ≤ 0.7. A API funciona sem nenhuma chave configurada — nesse caso, todo resultado usa a heurística. Uma classificação com `subject_id` nulo ou confiança abaixo de `CLASSIFIER_REVIEW_THRESHOLD` (padrão 0.6) é marcada `needs_review` em vez de aplicada silenciosamente. O provedor de IA nunca inventa IDs: candidatos que não pertençam ao catálogo carregado do banco são descartados antes de persistir.

O bloco 8 oferece planejamento adaptativo em `/api/v1/study-plans`, sempre filtrado por `user_id` (planos, itens e sessões são dados do usuário, diferente do catálogo de provas/editais):

- `POST /api/v1/study-plans`: cria um `StudyPlan` para um `exam_id` (+ `position_id` opcional) e gera os `StudyPlanItem`/`StudySession` (status `planned`) entre `starts_on` e `ends_on` (ou `exam.exam_date - 1 dia`, se `ends_on` não for informado).
- `GET /api/v1/study-plans`: lista os planos do usuário autenticado.
- `GET /api/v1/study-plans/{plan_id}/schedule`: agenda completa do plano, com nome de disciplina/tópico e status da sessão vinculada.
- `POST /api/v1/study-plans/{plan_id}/reschedule`: recalcula a agenda. Preserva sem alterações qualquer item de hoje/passado ou vinculado a uma `StudySession` com `status = completed`; apaga e regenera apenas itens estritamente futuros (a partir de amanhã), com prioridades recalculadas a partir do desempenho atual.
- `POST /api/v1/study-plans/{plan_id}/items/{item_id}/complete` e `.../skip`: registram conclusão ou pulo da `StudySession` vinculada ao item (cria a sessão se ainda não existir).

O algoritmo (`backend/app/planner.py`) gera candidatos de estudo por `Subject`/`Topic` do catálogo (`ExamSubject`, com fallback para o peso genérico do concurso quando não há peso específico do cargo) e calcula uma prioridade determinística:

```
prioridade = 0.4 × peso_normalizado(ExamSubject) + 0.4 × (1 − acurácia_do_usuário) + 0.2 × dias_sem_revisão/30 (saturado em 1.0)
```

Sem dado de `UserPerformance`, a fraqueza assumida é 0.75 (moderada, não máxima); sem `StudySession` concluída para o tema, a "vacância de revisão" é máxima (1.0). Os candidatos são distribuídos nos dias do período por round-robin ponderado pela prioridade (crédito acumulado por prioridade a cada rodada, maior crédito consome o próximo bloco de estudo de `available_minutes_per_day`), garantindo que temas mais próximos da prova, com maior peso ou pior desempenho apareçam com mais frequência sem excluir os demais.

O bloco 9 oferece nota de corte e inteligência em `/api/v1/exams/{exam_id}/cutoff-scores` e `/api/v1/exams/{exam_id}/cutoff-intelligence`:

- `POST/GET /cutoff-scores` e `PUT /cutoff-scores/{cutoff_id}`: CRUD de `CutoffScore` (catálogo compartilhado, como provas/editais — sem filtro por usuário). Criar exige `score`; nunca é gerado por heurística ou IA — só existe se vier de uma chamada autenticada (idealmente com `source_url`) ou de uma migração de dados explícita.
- `GET /cutoff-intelligence` (`position_id`/`category` opcionais na query): combina, com tipos explícitos por campo (`historical` | `estimate` | `insufficient_data`):
  - `historical`: lista bruta de `CutoffScore` — desta prova e de outros concursos da **mesma banca** (`Exam.examining_board`) com cargo de **mesmo nome**, mesma `category`. Nunca computado, é dado persistido.
  - `trend`: `trend_per_period = (última - primeira nota histórica) / nº de intervalos`; `projected_next_score = última + trend_per_period`. Requer ≥ 2 pontos históricos; abaixo disso, `insufficient_data`.
  - `user_score_estimate`: média ponderada pela `weight` de `ExamSubject` da `accuracy` em `UserPerformance` do usuário autenticado, em escala 0–100 (`100 × Σ(peso×acurácia) / Σ(peso das disciplinas com dado)`). Disciplinas sem `UserPerformance` ficam de fora da média e são reportadas em `subjects_without_data`; sem nenhum dado, `insufficient_data`.
  - `margin`: `nota estimada do usuário − referência`. A referência é a `CutoffScore` oficial deste exame/cargo/categoria quando existe (`historical`); senão a projeção de `trend` (`estimate`); senão `insufficient_data`. Nunca combina os dois.
  - `competitive_index`: z-score `(nota do usuário − média das notas de corte comparáveis) / desvio-padrão populacional`; se o desvio for zero, cai para uma razão simples (`method = "ratio_degenerate"`). Exige ≥ 2 notas históricas comparáveis.
  - `recommendations`: texto determinístico (não gerado por IA) derivado exclusivamente dos campos acima — nunca inventa nota de corte nem entra em conflito com os dados computados.

A lógica de cálculo (`backend/app/cutoff_intelligence.py`) é pura e testável sem banco; o roteador (`backend/app/cutoff.py`) apenas carrega os dados do usuário autenticado e do catálogo (reaproveita `study_plans.load_exam_subjects` para os pesos por disciplina).
