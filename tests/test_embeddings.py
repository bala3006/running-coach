import httpx
import pytest

from running_coach import embeddings
from running_coach.db import search_training_memory, upsert_runs


def test_default_embedding_model_matches_ollama_tag(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_EMBED_MODEL", raising=False)

    assert embeddings.embedding_model() == "nomic-embed-text:latest"


@pytest.mark.asyncio
async def test_pending_training_records_are_embedded_and_stored(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "test-embed")
    upsert_runs(
        [
            {
                "id": "run-1",
                "name": "Recovery jog",
                "distance_km": 5,
                "moving_time_minutes": 32,
                "start_date_local": "2026-10-01",
            }
        ]
    )

    async def fake_embed_texts(texts):
        assert "Recovery jog" in texts[0]
        return [[0.4, 0.8, 0.2] for _ in texts]

    monkeypatch.setattr(embeddings, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(embeddings, "embedding_model_available", lambda: None)

    result = await embeddings.index_pending_training_memory()

    assert result == {"model": "test-embed", "indexed": 1, "pending": 0, "available": True}
    retrieved = search_training_memory(
        "fatigued",
        query_embedding=[0.4, 0.8, 0.2],
        embedding_model="test-embed",
    )
    assert retrieved[0]["source_id"] == "run-1"


@pytest.mark.asyncio
async def test_missing_embedding_model_keeps_records_pending(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "missing-model")
    upsert_runs(
        [
            {
                "id": "run-1",
                "name": "Easy run",
                "distance_km": 5,
                "moving_time_minutes": 32,
            }
        ]
    )

    async def unavailable(texts):
        raise httpx.ConnectError("Ollama is offline")

    monkeypatch.setattr(embeddings, "embed_texts", unavailable)

    result = await embeddings.index_pending_training_memory()

    assert result == {"model": "missing-model", "indexed": 0, "pending": 1, "available": False}