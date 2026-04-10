"""
RAG Embedder — Text → Dense Vector Representations

Supports two embedding providers:
  1. HuggingFace (default) — Free, runs locally, no API key needed
     Model: all-MiniLM-L6-v2 (384-dim) — Fast and accurate
  2. OpenAI — Higher quality, requires API key
     Model: text-embedding-3-small (1536-dim)

The embedder is a singleton: the model loads once at startup
and is reused for every document chunk and query.
"""
from typing import Union
import numpy as np
from core.config import settings
from core.logger import get_logger
from core.retry import llm_retry

logger = get_logger(__name__)


class Embedder:
    """
    Unified embedding interface.
    Converts text → float32 numpy arrays (dense vectors).

    Usage:
        embedder = Embedder()
        vector = await embedder.embed_text("Hello world")   # shape: (384,)
        matrix = await embedder.embed_batch(["Hello", "World"])  # shape: (2, 384)
    """

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        self.model_name = settings.EMBEDDING_MODEL_NAME
        self._model = None
        self._dim: int = 0
        self._load_model()
        logger.info(
            "Embedder ready",
            provider=self.provider,
            model=self.model_name,
            dim=self._dim,
        )

    def _load_model(self) -> None:
        """Load the embedding model at startup (blocking — runs once)."""
        if self.provider == "huggingface":
            from sentence_transformers import SentenceTransformer
            logger.info("Loading HuggingFace embedding model...", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
            # Determine embedding dimension from a test encode
            test = self._model.encode(["test"], convert_to_numpy=True)
            self._dim = test.shape[1]

        elif self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set."
                )
            from openai import OpenAI
            self._model = OpenAI(api_key=settings.OPENAI_API_KEY)
            # Dimensions for common OpenAI embedding models
            dim_map = {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072,
                "text-embedding-ada-002": 1536,
            }
            self._dim = dim_map.get(self.model_name, 1536)
        else:
            raise ValueError(
                f"Unknown EMBEDDING_PROVIDER: '{self.provider}'. "
                "Supported: huggingface | openai"
            )

    @property
    def dimension(self) -> int:
        """Embedding vector dimensionality. Needed when creating FAISS index."""
        return self._dim

    @llm_retry
    async def embed_text(self, text: str) -> np.ndarray:
        """
        Embed a single string into a dense vector.
        Returns: numpy float32 array of shape (dim,)
        """
        result = await self.embed_batch([text])
        return result[0]

    @llm_retry
    async def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Batch embed a list of strings.
        More efficient than calling embed_text() in a loop.

        Returns: numpy float32 array of shape (n, dim)
        """
        if not texts:
            return np.array([], dtype=np.float32)

        if self.provider == "huggingface":
            # SentenceTransformers is sync — run in an executor to avoid blocking the event loop
            import asyncio
            loop = asyncio.get_event_loop()
            vectors = await loop.run_in_executor(
                None,
                lambda: self._model.encode(
                    texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True,  # L2 normalize for cosine similarity
                    show_progress_bar=len(texts) > 10,
                )
            )
            return vectors.astype(np.float32)

        elif self.provider == "openai":
            response = self._model.embeddings.create(
                model=self.model_name,
                input=texts,
            )
            vectors = np.array(
                [item.embedding for item in response.data],
                dtype=np.float32,
            )
            return vectors

        raise ValueError(f"Unknown provider: {self.provider}")


# ── Singleton ─────────────────────────────────────────────────────────────────
embedder = Embedder()
