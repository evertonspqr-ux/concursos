# Contexto para Claude — Projeto Concursos

Você está continuando o projeto em `/home/atlas/concursos`.

Leia primeiro [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Ele é o contrato canônico do projeto. Não renomeie entidades, rotas ou colunas já existentes sem uma migração e uma atualização explícita desse documento.

## Stack

- Frontend: Next.js App Router, TypeScript e Tailwind (`frontend/`).
- Backend: FastAPI assíncrono e SQLAlchemy (`backend/app/`).
- Banco: PostgreSQL 16 + pgvector.
- IDs UUID; datas ISO 8601/UTC; timezone de produto `America/Sao_Paulo`.
- API REST sob `/api/v1/`; use `Authorization: Bearer <JWT>` para recursos autenticados.

## O que já está implementado

1. Fundação: Docker Compose, configuração, FastAPI, Next.js, PostgreSQL/pgvector e autenticação JWT.
2. Modelagem: entidades `User`, `Exam`, `Position`, `Notice`, `Subject`, `Topic`, `Question`, `ExamPaper`, `Simulation`, `StudyPlan`, `StudySession`, `CutoffScore`, `UserPerformance` e tabelas de associação em `backend/app/models.py`.
3. Editais/PDF: upload, armazenamento local, extração de texto/metadados e download em `backend/app/notices.py`.
4. Análise de edital: rota `POST /api/v1/exams/{exam_id}/notices/{notice_id}/analyze`, com extração heurística e persistência.
5. Provas e gabaritos: criação de provas, importação de questões, gabarito e correção de tentativas em `backend/app/papers.py`.

## Suas entregas restantes

### 6. Classificador de questões

Classifique uma `Question` em `Subject → Topic` usando IA, com confiança e possibilidade de revisão humana.

- Preserve `Question.subject_id`, `Question.topic_id` e `Question.classification_confidence`.
- Crie um adaptador de provedor de IA; nenhuma chave deve ser obrigatória para iniciar a API.
- Disponibilize classificação unitária e em lote autenticadas.
- Tenha fallback determinístico quando o provedor não estiver configurado.
- Nunca classifique silenciosamente com confiança baixa: devolva/registre status para revisão.

### 8. Planejador adaptativo

Gere e atualize rotinas em `StudyPlan`, `StudyPlanItem` e `StudySession`.

- Entradas: tempo disponível, data da prova, pesos de `ExamSubject`, desempenho por assunto e revisões pendentes.
- Priorize proximidade da prova, peso e baixa precisão.
- Não altere histórico concluído; reagende somente itens futuros.
- Exponha rotas autenticadas para criar plano, ver agenda e registrar conclusão/pulo de sessão.

### 9. Nota de corte e inteligência

Implemente estimativas e recomendações usando `CutoffScore`, provas e `UserPerformance`.

- Diferencie claramente dado histórico, estimativa e recomendação.
- Calcule margem do usuário, tendência e índice competitivo com fórmulas documentadas e dados insuficientes explícitos.
- Não invente notas de corte: apenas persista dados com fonte/URL ou use entradas fornecidas.
- Exponha endpoints autenticados de consulta e atualização.

## Regras de implementação

- Não use `user_id` do cliente para autorização; obtenha-o por `get_current_user` em `backend/app/dependencies.py`.
- Provas/editais são catálogo compartilhado, mas planos, sessões, tentativas, simulados e desempenho devem sempre ser filtrados pelo usuário autenticado.
- Importe routers novos em `backend/app/main.py`.
- Amplie `backend/app/schemas.py` com contratos Pydantic para rotas novas.
- Atualize `docs/ARCHITECTURE.md` para cada contrato compartilhado criado.
- Use `apply_patch` para edições, rode `python3 -m compileall -q backend/app` e `git diff --check` ao terminar.

## Como executar

```bash
cp .env.example .env
docker compose up --build
```

O ambiente atual pode não ter Docker instalado. Não remova `compose.yaml` nem substitua pgvector por outro banco. Dependências do backend estão em `backend/requirements.txt`.

## Limites de escopo

Não implemente dashboard (etapa 10), novos fluxos de PDF (etapa 3) ou mudanças em prova/gabarito (etapa 5), exceto se algo for estritamente necessário para integrar as suas entregas. Preserve as rotas existentes.
