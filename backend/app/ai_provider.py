import json
import re
import uuid

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency, fallback handles absence
    httpx = None

from .classifier import ProviderClassification, SubjectCandidate

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


def _build_prompt(statement: str, options: list, candidates: list[SubjectCandidate]) -> str:
    lines = ["Catálogo de assuntos e tópicos disponíveis (use exclusivamente estes IDs, nunca invente um novo):"]
    for subject in candidates:
        lines.append(f"- subject_id={subject.id} | {subject.name}")
        for topic in subject.topics:
            lines.append(f"    - topic_id={topic.id} | {topic.name}")
    option_text = "\n".join(f"- {option}" for option in options) if options else "(sem alternativas)"
    lines.append("\nQuestão:")
    lines.append(statement)
    lines.append("\nAlternativas:")
    lines.append(option_text)
    lines.append(
        "\nResponda SOMENTE com um JSON, sem texto adicional, no formato: "
        '{"subject_id": "<uuid ou null>", "topic_id": "<uuid ou null>", "confidence": <numero de 0 a 1>, "rationale": "<motivo breve>"}. '
        "Use apenas IDs do catálogo acima. Se não houver correspondência clara, responda com null e confidence baixa."
    )
    return "\n".join(lines)


class AnthropicClassifierProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float):
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(httpx is not None and self._api_key)

    async def classify(
        self, statement: str, options: list, candidates: list[SubjectCandidate]
    ) -> ProviderClassification | None:
        if not self.available or not candidates:
            return None
        payload = {
            "model": self._model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": _build_prompt(statement, options, candidates)}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        parsed = json.loads(match.group(0))
        candidate_subject_ids = {str(subject.id) for subject in candidates}
        candidate_topic_ids = {str(topic.id) for subject in candidates for topic in subject.topics}
        subject_id = parsed.get("subject_id")
        topic_id = parsed.get("topic_id")
        if subject_id not in candidate_subject_ids:
            subject_id = None
        if topic_id not in candidate_topic_ids:
            topic_id = None
        confidence = max(0.0, min(1.0, float(parsed.get("confidence") or 0)))
        return ProviderClassification(
            subject_id=uuid.UUID(subject_id) if subject_id else None,
            topic_id=uuid.UUID(topic_id) if topic_id else None,
            confidence=confidence,
            rationale=parsed.get("rationale"),
        )
