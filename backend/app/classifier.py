import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Protocol


def _normalized_words(value: str) -> set[str]:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    cleaned = re.sub(r"[^a-z0-9 ]", " ", value)
    return {word for word in cleaned.split() if len(word) > 2}


def _options_text(options: list) -> str:
    parts = []
    for option in options:
        if isinstance(option, dict):
            parts.append(str(option.get("text") or option.get("label") or ""))
        else:
            parts.append(str(option))
    return " ".join(parts)


@dataclass
class TopicCandidate:
    id: uuid.UUID
    name: str


@dataclass
class SubjectCandidate:
    id: uuid.UUID
    name: str
    topics: list[TopicCandidate] = field(default_factory=list)


@dataclass
class ProviderClassification:
    subject_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    confidence: float
    rationale: str | None = None


@dataclass
class ClassificationOutcome:
    subject_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    confidence: float
    method: str
    needs_review: bool
    rationale: str | None = None


class ClassifierProvider(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    async def classify(
        self, statement: str, options: list, candidates: list[SubjectCandidate]
    ) -> ProviderClassification | None: ...


def heuristic_classify(statement: str, options: list, candidates: list[SubjectCandidate]) -> ProviderClassification:
    """Classificador determinístico por sobreposição léxica entre a questão e os nomes do catálogo.

    Não usa IA; serve de fallback quando nenhum provedor está configurado ou disponível.
    A confiança é sempre limitada a 0.7, pois é uma heurística, não um julgamento semântico.
    """
    statement_words = _normalized_words(f"{statement} {_options_text(options)}")
    best_subject: SubjectCandidate | None = None
    best_topic: TopicCandidate | None = None
    best_score = 0.0
    for subject in candidates:
        subject_words = _normalized_words(subject.name)
        subject_score = len(subject_words & statement_words) / len(subject_words) if subject_words else 0.0
        if subject_score > best_score:
            best_score, best_subject, best_topic = subject_score, subject, None
        for topic in subject.topics:
            topic_words = _normalized_words(topic.name)
            topic_score = len(topic_words & statement_words) / len(topic_words) if topic_words else 0.0
            combined = topic_score * 0.7 + subject_score * 0.3
            if combined > best_score:
                best_score, best_subject, best_topic = combined, subject, topic
    confidence = round(min(best_score, 0.7), 4)
    return ProviderClassification(
        subject_id=best_subject.id if best_subject and confidence > 0 else None,
        topic_id=best_topic.id if best_topic and confidence > 0 else None,
        confidence=confidence,
        rationale="heuristica_sobreposicao_lexica",
    )


async def classify_question_statement(
    statement: str,
    options: list,
    candidates: list[SubjectCandidate],
    provider: ClassifierProvider | None,
    review_threshold: float,
) -> ClassificationOutcome:
    result: ProviderClassification | None = None
    method = "heuristic"
    if provider is not None and provider.available:
        try:
            result = await provider.classify(statement, options, candidates)
        except Exception:
            result = None
        if result is not None:
            method = provider.name
    if result is None:
        result = heuristic_classify(statement, options, candidates)
        method = "heuristic"
    needs_review = result.subject_id is None or result.confidence < review_threshold
    return ClassificationOutcome(
        subject_id=result.subject_id,
        topic_id=result.topic_id,
        confidence=result.confidence,
        method=method,
        needs_review=needs_review,
        rationale=result.rationale,
    )
