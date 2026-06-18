import pytest

from app.services.relevance import (
    _cosine_similarity,
    _keyword_score,
    _rrf_score,
    select_relevant_beliefs,
)


class _FakeEmbedding:
    def __init__(self, embedding):
        self.embedding = embedding


class _FakeEmbeddingsResponse:
    def __init__(self, embeddings):
        self.data = [_FakeEmbedding(e) for e in embeddings]


class _FakeEmbeddings:
    async def create(self, *args, **kwargs):
        # First item is the question, then candidates in order.
        return _FakeEmbeddingsResponse(
            [
                [1.0, 0.0, 0.0],  # question
                [0.9, 0.1, 0.0],  # plan: Enterprise
                [0.1, 0.9, 0.0],  # region: Berlin
                [0.0, 0.0, 1.0],  # account_name: Helios Apps
            ]
        )


class _FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.embeddings = _FakeEmbeddings()


@pytest.mark.asyncio
async def test_select_relevant_beliefs_orders_by_similarity(monkeypatch):
    monkeypatch.setattr("app.services.relevance.AsyncOpenAI", _FakeOpenAI)
    monkeypatch.setattr(
        "app.services.relevance.get_settings",
        lambda: type(
            "S",
            (),
            {
                "openai_api_key": "sk-test",
                "openai_embedding_model": "text-embedding-test",
            },
        ),
    )

    beliefs = {
        "plan": {"value": "Enterprise"},
        "region": {"value": "Berlin"},
        "account_name": {"value": "Helios Apps"},
    }
    result = await select_relevant_beliefs("What is the plan?", beliefs, top_k=2)
    assert len(result) == 2
    attributes = [attr for attr, _ in result]
    assert attributes[0] == "plan"
    assert "region" in attributes


@pytest.mark.asyncio
async def test_select_relevant_beliefs_raises_without_key():
    from app.services.relevance import get_settings

    settings = get_settings()
    settings.openai_api_key = ""
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await select_relevant_beliefs("What?", {"plan": {"value": "Enterprise"}})


def test_cosine_similarity():
    a = [1.0, 0.0]
    b = [1.0, 0.0]
    assert _cosine_similarity(a, b) == pytest.approx(1.0)

    c = [0.0, 1.0]
    assert _cosine_similarity(a, c) == pytest.approx(0.0)

    zero = [0.0, 0.0]
    assert _cosine_similarity(a, zero) == 0.0


def test_keyword_score():
    assert _keyword_score("What is the plan?", "plan: Enterprise") > 0
    assert _keyword_score("random unrelated", "plan: Enterprise") == 0.0


def test_rrf_score():
    assert _rrf_score([1, 1]) == pytest.approx(2 / 61)
    assert _rrf_score([1, 2]) == pytest.approx(1 / 61 + 1 / 62)
