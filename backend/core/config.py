"""
Core configuration management using Pydantic Settings.
Reads from .env file with sensible defaults for local development.
Swap LLM_PROVIDER, VECTOR_DB, etc. via environment variables — zero code changes needed.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Autonomous AI System"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ── LLM Provider ─────────────────────────────────────────────────────────
    # Options: "openai" | "groq" | "ollama"
    # Groq is free and fast — great default for development
    LLM_PROVIDER: str = "groq"
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── LLM Models ───────────────────────────────────────────────────────────
    OPENAI_MODEL: str = "gpt-4o"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OLLAMA_MODEL: str = "mistral"

    # ── Embeddings ───────────────────────────────────────────────────────────
    # Options: "openai" | "huggingface"
    # HuggingFace is free and runs locally
    EMBEDDING_PROVIDER: str = "huggingface"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # ── Vector Database ──────────────────────────────────────────────────────
    # Options: "faiss" | "pinecone"
    VECTOR_DB: str = "faiss"
    FAISS_INDEX_PATH: str = "./data/faiss_index"
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENV: Optional[str] = None
    PINECONE_INDEX: str = "autonomous-ai"

    # ── Relational Database ──────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    # ── File Upload ──────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # ── RAG Parameters ───────────────────────────────────────────────────────
    CHUNK_SIZE: int = 512           # tokens per chunk
    CHUNK_OVERLAP: int = 64         # overlap between consecutive chunks
    TOP_K: int = 5                  # number of retrieved chunks per query

    # ── Agent Memory ─────────────────────────────────────────────────────────
    MAX_HISTORY: int = 20           # max messages kept in short-term memory

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]

    # ── Retry / Resilience ───────────────────────────────────────────────────
    MAX_RETRIES: int = 3
    RETRY_WAIT_SECONDS: float = 1.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# ── Singleton — import `settings` everywhere ──────────────────────────────────
settings = Settings()

# Ensure required data directories exist on startup
for _path in [settings.UPLOAD_DIR, settings.FAISS_INDEX_PATH, "./data/logs"]:
    Path(_path).mkdir(parents=True, exist_ok=True)
