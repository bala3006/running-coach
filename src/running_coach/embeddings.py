import os

import httpx

from running_coach.db import (
    list_unembedded_training_documents,
    save_training_embedding,
    training_memory_stats as get_training_memory_stats,
)


def embedding_model() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{base_url}/api/embed",
            json={"model": embedding_model(), "input": texts},
        )
        response.raise_for_status()
    vectors = response.json().get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise ValueError("Ollama returned an invalid embedding response")
    if any(not isinstance(vector, list) or not vector for vector in vectors):
        raise ValueError("Ollama returned an empty embedding vector")
    dimensions = len(vectors[0])
    if any(len(vector) != dimensions for vector in vectors):
        raise ValueError("Ollama returned vectors with inconsistent dimensions")
    return vectors


async def index_pending_training_memory(batch_size: int = 32) -> dict[str, str | int | bool]:
    model = embedding_model()
    indexed = 0
    while True:
        documents = list_unembedded_training_documents(model, limit=batch_size)
        if not documents:
            available = indexed > 0 or await embedding_model_available()
            stats = get_training_memory_stats(model)
            return {
                "model": model,
                "indexed": indexed,
                "pending": stats["total"] - stats["embedded"],
                "available": available,
            }
        inputs = [f"{document['title']}\n{document['content']}" for document in documents]
        try:
            vectors = await embed_texts(inputs)
        except (httpx.HTTPError, ValueError):
            stats = get_training_memory_stats(model)
            return {
                "model": model,
                "indexed": indexed,
                "pending": stats["total"] - stats["embedded"],
                "available": False,
            }
        for document, vector in zip(documents, vectors):
            save_training_embedding(
                document["source_type"], document["source_id"], model, vector
            )
        indexed += len(documents)


def training_memory_stats(model: str | None = None) -> dict[str, int]:
    return get_training_memory_stats(model or embedding_model())


async def embedding_model_available() -> bool:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
        installed = {item.get("name") for item in response.json().get("models", [])}
        return embedding_model() in installed
    except (httpx.HTTPError, ValueError):
        return False

