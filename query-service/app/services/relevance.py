import math
from typing import Any, Dict, List, Tuple

from openai import AsyncOpenAI

from app.config import get_settings


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def select_relevant_beliefs(
    question: str, beliefs: Dict[str, Any], top_k: int = 10
) -> List[Tuple[str, Any]]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for belief relevance selection")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    candidates: List[Tuple[str, str]] = []
    for attribute, meta in beliefs.items():
        if isinstance(meta, dict) and "value" in meta:
            text = f"{attribute}: {meta['value']}"
        else:
            text = f"{attribute}: {meta}"
        candidates.append((attribute, text))

    if not candidates:
        return []

    texts = [question] + [text for _, text in candidates]
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )

    question_embedding = response.data[0].embedding
    scored: List[Tuple[str, Any, float]] = []
    for idx, (attribute, _) in enumerate(candidates, start=1):
        belief_embedding = response.data[idx].embedding
        similarity = _cosine_similarity(question_embedding, belief_embedding)
        scored.append((attribute, beliefs[attribute], similarity))

    scored.sort(key=lambda item: item[2], reverse=True)
    return [(attribute, value) for attribute, value, _ in scored[:top_k]]
