"""
Autonomous AI System — FastAPI Application Entrypoint

Startup sequence:
  1. Configure structured logging
  2. Initialize the database (create tables if not exists)
  3. Register all API routers
  4. Start accepting requests

Run with:
  uvicorn main:app --reload --port 8000
"""
import sys
# Ensure stdout uses UTF-8 on Windows (prevents UnicodeEncodeError with emoji in logs)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from core.config import settings
from core.logger import setup_logging, get_logger
from db.database import init_db

# Import route modules
from api.routes import chat, upload, agents, query

# ── Logging Setup ─────────────────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup (before accepting requests) and on shutdown.
    Use this for initialization and cleanup.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info(
        "Autonomous AI System starting",
        version=settings.VERSION,
        llm_provider=settings.LLM_PROVIDER,
        vector_db=settings.VECTOR_DB,
        embedding_provider=settings.EMBEDDING_PROVIDER,
    )

    # Initialize database tables
    await init_db()
    logger.info("[OK] Database ready")

    # Pre-warm the embedding model (avoids cold start on first request)
    try:
        from rag.embedder import embedder
        test = await embedder.embed_text("warmup")
        logger.info("[OK] Embedding model loaded", dim=embedder.dimension)
    except Exception as e:
        logger.warning("[WARN] Embedding model warmup failed", error=str(e))

    logger.info("[OK] Server ready — accepting requests")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("[BYE] Server shutting down")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Production-grade Autonomous AI System with multi-agent orchestration "
        "and RAG (Retrieval-Augmented Generation) over private documents."
    ),
    docs_url="/docs",        # Swagger UI
    redoc_url="/redoc",      # ReDoc UI
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

# CORS — allow the Next.js frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression for large responses
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(agents.router)
app.include_router(query.router)


# ── Health Endpoints ──────────────────────────────────────────────────────────

@app.get("/", tags=["system"])
async def root():
    """Root endpoint — confirms the server is running."""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
async def health():
    """Detailed health check — used by load balancers and monitoring."""
    from models.schemas import HealthResponse
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        llm_provider=settings.LLM_PROVIDER,
        vector_db=settings.VECTOR_DB,
        embedding_provider=settings.EMBEDDING_PROVIDER,
    )


# ── Local Dev Runner ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
