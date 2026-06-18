import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.config import get_settings


EXTRACTION_PROMPT = """Extract structured facts from this support event.
Return ONLY a JSON array of objects. Each object must have:
- entity_type (string)
- entity_id (string)
- attribute (string)
- value (string or number or boolean, converted to string)
- confidence (number between 0 and 1)

If an attribute value is found only in the text and not in the payload, include it.
Do not include duplicate facts already present in the payload unless the text contradicts them.

Event:
entity_type: {entity_type}
entity_id: {entity_id}
payload: {payload}
text: {text}
"""


class LLMFactExtractor:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.temperature = temperature if temperature is not None else settings.openai_temperature
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def extract_facts(
        self,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any],
        text: str,
    ) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []

        prompt = EXTRACTION_PROMPT.format(
            entity_type=entity_type,
            entity_id=entity_id,
            payload=json.dumps(payload),
            text=text,
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": "You are a precise fact extraction assistant."},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or "[]"
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            facts = json.loads(content)
        except json.JSONDecodeError:
            return []

        if not isinstance(facts, list):
            return []

        normalized = []
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            entity_type_out = fact.get("entity_type") or entity_type
            entity_id_out = fact.get("entity_id") or entity_id
            attribute = fact.get("attribute")
            value = fact.get("value")
            if attribute is None or value is None:
                continue
            normalized.append(
                {
                    "entity_type": entity_type_out,
                    "entity_id": entity_id_out,
                    "attribute": str(attribute),
                    "value": str(value),
                    "confidence": float(fact.get("confidence", 0.75)),
                }
            )
        return normalized


_extractor: Optional[LLMFactExtractor] = None


def get_extractor() -> LLMFactExtractor:
    global _extractor
    if _extractor is None:
        _extractor = LLMFactExtractor()
    return _extractor
