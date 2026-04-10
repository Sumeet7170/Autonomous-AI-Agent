"""
RAG Vector Store — FAISS-backed Persistent Index

This module manages the FAISS vector index (the "memory" of the RAG system).
It stores document embeddings and supports fast approximate nearest-neighbor search.

Architecture:
  - One FAISS IndexFlatIP index per namespace (supports multi-tenant document collections)
  - Metadata (filename, page, chunk text) stored in a parallel dict keyed by FAISS ID
  - Index persists to disk — survives server restarts

FAISS IndexFlatIP uses Inner Product similarity (equivalent to cosine similarity
for normalized vectors, which our embedder produces).
"""
import json
import pickle
import numpy as np
from pathlib import Path

import faiss

from core.config import settings
from core.logger import get_logger
from rag.embedder import embedder
from rag.ingestor import Document

logger = get_logger(__name__)


class VectorStore:
    """
    Manages FAISS indexes (one per namespace) with persistence.

    Namespaces allow logical separation of document groups:
        - "default"     → general documents
        - "legal"       → legal contracts
        - "codebase"    → source code docs (per project)
    """

    def __init__(self):
        self._indexes: dict[str, faiss.Index] = {}
        self._metadata: dict[str, list[dict]] = {}
        self._index_dir = Path(settings.FAISS_INDEX_PATH)
        self._index_dir.mkdir(parents=True, exist_ok=True)
        logger.info("VectorStore initialized", index_dir=str(self._index_dir))

    def _index_path(self, namespace: str) -> Path:
        return self._index_dir / f"{namespace}.index"

    def _meta_path(self, namespace: str) -> Path:
        return self._index_dir / f"{namespace}.meta"

    def _load_or_create(self, namespace: str) -> None:
        """Load an existing index from disk, or create a new empty one."""
        if namespace in self._indexes:
            return  # Already loaded

        idx_path = self._index_path(namespace)
        meta_path = self._meta_path(namespace)

        if idx_path.exists() and meta_path.exists():
            logger.info("Loading existing FAISS index", namespace=namespace)
            self._indexes[namespace] = faiss.read_index(str(idx_path))
            with open(meta_path, "rb") as f:
                self._metadata[namespace] = pickle.load(f)
        else:
            logger.info("Creating new FAISS index", namespace=namespace, dim=embedder.dimension)
            # IndexFlatIP: exact inner-product (cosine for normalized vectors)
            self._indexes[namespace] = faiss.IndexFlatIP(embedder.dimension)
            self._metadata[namespace] = []

    def _save(self, namespace: str) -> None:
        """Persist index and metadata to disk."""
        faiss.write_index(self._indexes[namespace], str(self._index_path(namespace)))
        with open(self._meta_path(namespace), "wb") as f:
            pickle.dump(self._metadata[namespace], f)

    async def add_documents(self, documents: list[Document]) -> int:
        """
        Embed and add a list of Document chunks to the vector store.

        Args:
            documents: List of Document objects from the ingestor

        Returns:
            Number of chunks successfully added
        """
        if not documents:
            return 0

        # Group by namespace
        by_namespace: dict[str, list[Document]] = {}
        for doc in documents:
            ns = doc.metadata.get("namespace", "default")
            by_namespace.setdefault(ns, []).append(doc)

        total_added = 0

        for namespace, docs in by_namespace.items():
            self._load_or_create(namespace)

            texts = [doc.content for doc in docs]
            logger.info("Embedding batch", namespace=namespace, count=len(texts))

            # Embed all chunks in one batch (much faster than one-by-one)
            vectors = await embedder.embed_batch(texts)

            # Add to FAISS index
            self._indexes[namespace].add(vectors)

            # Store metadata alongside
            for doc in docs:
                self._metadata[namespace].append({
                    "chunk_id": doc.chunk_id,
                    "filename": doc.metadata.get("filename", "unknown"),
                    "page": doc.metadata.get("page"),
                    "namespace": namespace,
                    "content": doc.content,  # Store text so we can return it in results
                })

            self._save(namespace)
            total_added += len(docs)
            logger.info("Chunks added to index", namespace=namespace, count=len(docs))

        return total_added

    async def search(
        self, query: str, namespace: str = "default", top_k: int = 5
    ) -> list[dict]:
        """
        Semantic search: find the top-k most similar chunks to the query.

        Args:
            query:     User's search string
            namespace: Which namespace/collection to search
            top_k:     How many results to return

        Returns:
            List of dicts with keys: chunk_id, filename, page, content, score
        """
        self._load_or_create(namespace)
        index = self._indexes.get(namespace)

        if index is None or index.ntotal == 0:
            logger.warning("Empty or missing index", namespace=namespace)
            return []

        # Embed the query
        query_vec = await embedder.embed_text(query)
        query_vec = query_vec.reshape(1, -1)  # FAISS expects shape (1, dim)

        # Search FAISS
        k = min(top_k, index.ntotal)
        scores, indices = index.search(query_vec, k)

        results = []
        meta_list = self._metadata.get(namespace, [])

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(meta_list):
                continue  # FAISS returns -1 for empty slots
            meta = meta_list[idx]
            results.append({
                "chunk_id": meta["chunk_id"],
                "filename": meta.get("filename", "unknown"),
                "page": meta.get("page"),
                "content": meta.get("content", ""),
                "score": float(score),
            })

        logger.debug("Vector search complete", namespace=namespace, results=len(results))
        return results

    def get_stats(self, namespace: str = "default") -> dict:
        """Return index statistics for the dashboard."""
        self._load_or_create(namespace)
        index = self._indexes.get(namespace)
        return {
            "namespace": namespace,
            "total_chunks": index.ntotal if index else 0,
            "dimension": embedder.dimension,
        }

    def list_namespaces(self) -> list[str]:
        """Return all namespaces that have an index file on disk."""
        return [p.stem for p in self._index_dir.glob("*.index")]


# ── Singleton ─────────────────────────────────────────────────────────────────
vector_store = VectorStore()
