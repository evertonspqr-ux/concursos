import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PRODUCT_TIMEZONE = ZoneInfo("America/Sao_Paulo")
DEFAULT_BLOCK_MINUTES = 50
DEFAULT_STUDY_START_HOUR = 8


@dataclass
class StudyCandidate:
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None
    weight: float
    accuracy: float | None
    last_reviewed_at: datetime | None


@dataclass
class PlannedItem:
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None
    scheduled_for: datetime
    planned_minutes: int
    priority: float


def compute_priority(candidate: StudyCandidate, max_weight: float, reference_date: datetime) -> float:
    """Prioridade = 40% peso da disciplina no edital + 40% fraqueza do usuário + 20% tempo sem revisão.

    - `weight_score`: peso do `ExamSubject` normalizado pelo maior peso do concurso.
    - `weakness_score`: 1 - acurácia conhecida; sem dado de desempenho, assume-se fraqueza moderada (0.75)
      para priorizar cobertura sem tratar o desconhecido como pior que uma fraqueza comprovada.
    - `staleness_score`: dias desde a última sessão concluída, saturando em 30 dias; nunca revisado = máximo.
    """
    weight_score = (candidate.weight / max_weight) if max_weight else 0.0
    weakness_score = (1 - candidate.accuracy) if candidate.accuracy is not None else 0.75
    if candidate.last_reviewed_at is None:
        staleness_score = 1.0
    else:
        staleness_days = max((reference_date - candidate.last_reviewed_at).days, 0)
        staleness_score = min(staleness_days / 30, 1.0)
    return round(weight_score * 0.4 + weakness_score * 0.4 + staleness_score * 0.2, 4)


def build_schedule(
    candidates: list[StudyCandidate],
    starts_on: date,
    ends_on: date,
    available_minutes_per_day: int,
    reference_date: datetime,
    block_minutes: int = DEFAULT_BLOCK_MINUTES,
) -> list[PlannedItem]:
    """Distribui os candidatos nos dias do período usando round-robin ponderado por prioridade.

    A cada iteração, todo candidato acumula crédito igual à sua prioridade; o de maior crédito
    acumulado é escolhido e tem seu crédito decrementado em 1. Isso garante que temas mais
    prioritários (peso alto, baixa acurácia, muito tempo sem revisão) apareçam com mais frequência
    ao longo do plano, sem nunca excluir por completo os demais.
    """
    if not candidates or available_minutes_per_day <= 0 or ends_on < starts_on:
        return []
    max_weight = max((candidate.weight for candidate in candidates), default=1.0) or 1.0
    scored = sorted(
        ((candidate, compute_priority(candidate, max_weight, reference_date)) for candidate in candidates),
        key=lambda pair: pair[1],
        reverse=True,
    )
    credits = [0.0] * len(scored)
    block = max(5, min(block_minutes, available_minutes_per_day))

    items: list[PlannedItem] = []
    day = starts_on
    while day <= ends_on:
        remaining = available_minutes_per_day
        cursor = datetime(day.year, day.month, day.day, DEFAULT_STUDY_START_HOUR, tzinfo=PRODUCT_TIMEZONE)
        while remaining > 0:
            for index in range(len(scored)):
                credits[index] += scored[index][1]
            chosen_index = max(range(len(scored)), key=lambda index: credits[index])
            candidate, priority = scored[chosen_index]
            chunk = min(block, remaining)
            items.append(
                PlannedItem(
                    subject_id=candidate.subject_id,
                    topic_id=candidate.topic_id,
                    scheduled_for=cursor,
                    planned_minutes=chunk,
                    priority=priority,
                )
            )
            credits[chosen_index] -= 1.0
            cursor += timedelta(minutes=chunk)
            remaining -= chunk
        day += timedelta(days=1)
    return items
