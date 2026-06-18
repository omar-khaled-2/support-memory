import math
import re
from typing import Any, Dict, List, Tuple

from openai import AsyncOpenAI

from app.config import get_settings


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def _keyword_score(question: str, belief_text: str) -> float:
    question_tokens = _tokenize(question)
    belief_tokens = _tokenize(belief_text)
    if not question_tokens or not belief_tokens:
        return 0.0
    overlap = question_tokens & belief_tokens
    return len(overlap) / max(len(question_tokens), len(belief_tokens))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _rrf_score(ranks: List[int], k: int = 60) -> float:
    return sum(1.0 / (k + rank) for rank in ranks)


def _prepare_candidates(
    beliefs: Dict[str, Any],
) -> List[Tuple[str, str, Any]]:
    candidates = []
    for attribute, meta in beliefs.items():
        if isinstance(meta, dict) and "value" in meta:
            text = f"{attribute}: {meta['value']}"
        else:
            text = f"{attribute}: {meta}"
        candidates.append((attribute, text, meta))
    return candidates


async def select_relevant_beliefs(
    question: str, beliefs: Dict[str, Any], top_k: int = 10
) -> List[Tuple[str, Any]]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for belief relevance selection")

    candidates = _prepare_candidates(beliefs)
    if not candidates:
        return []

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    texts = [question] + [text for _, text, _ in candidates]
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )

    question_embedding = response.data[0].embedding
    keyword_ranks: List[Tuple[str, Any, float]] = []
    embedding_ranks: List[Tuple[str, Any, float]] = []

    for idx, (attribute, text, value) in enumerate(candidates):
        belief_embedding = response.data[idx + 1].embedding
        embedding_score = _cosine_similarity(question_embedding, belief_embedding)
        keyword_score = _keyword_score(question, text)

        keyword_ranks.append((attribute, value, keyword_score))
        embedding_ranks.append((attribute, value, embedding_score))

    keyword_ranks.sort(key=lambda item: item[2], reverse=True)
    embedding_ranks.sort(key=lambda item: item[2], reverse=True)

    keyword_rank_by_attr = {
        attr: rank for rank, (attr, _, _) in enumerate(keyword_ranks, start=1)
    }
    embedding_rank_by_attr = {
        attr: rank for rank, (attr, _, _) in enumerate(embedding_ranks, start=1)
    }

    fused: List[Tuple[str, Any, float]] = []
    for attribute, value, _ in candidates:
        kr = keyword_rank_by_attr[attribute]
        er = embedding_rank_by_attr[attribute]
        score = _rrf_score([kr, er])
        fused.append((attribute, value, score))

    fused.sort(key=lambda item: item[2], reverse=True)
    return [(attribute, value) for attribute, value, _ in fused[:top_k]]
