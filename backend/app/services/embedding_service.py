import os

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434",
).rstrip("/")

EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL",
    "qwen3-embedding:4b",
)

EMBEDDING_DIMENSIONS = int(
    os.getenv(
        "OLLAMA_EMBEDDING_DIMENSIONS",
        "1536",
    )
)

EMBEDD_URL = f"{OLLAMA_URL}/api/embed"


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    payload = {
        "model": EMBEDDING_MODEL,
        "input": text,
        "dimensions": EMBEDDING_DIMENSIONS,
    }

    response = httpx.post(
        EMBEDD_URL,
        json=payload,
        timeout=120.0,
    )

    response.raise_for_status()

    data = response.json()
    embeddings = data.get("embeddings")

    if not embeddings:
        raise RuntimeError("Ollama returned no embedding.")

    embedding = embeddings[0]

    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"Expected {EMBEDDING_DIMENSIONS}-dimensional embedding, "
            f"but received {len(embedding)} dimensions."
        )

    return embedding