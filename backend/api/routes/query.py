"""
RAG Query API Route — POST /api/query

Handles semantic search + LLM answer generation from uploaded documents.
Supports both streaming (SSE) and non-streaming modes.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from core.logger import get_logger
from rag.retriever import retrieve_and_answer, stream_rag_answer
from models.schemas import QueryRequest, QueryResponse

router = APIRouter(prefix="/api/query", tags=["query"])
logger = get_logger(__name__)


@router.post("", response_model=QueryResponse)
async def query_documents(req: QueryRequest):
    """
    Query your uploaded documents using natural language.

    The system will:
    1. Embed your query into a vector
    2. Find the top-K most relevant document chunks
    3. Ask the LLM to answer using ONLY those chunks
    4. Return the answer + source citations

    Set `stream: true` to get a streaming SSE response instead.
    """
    if req.stream:
        return StreamingResponse(
            stream_rag_answer(
                query=req.query,
                namespace=req.namespace,
                top_k=req.top_k,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    result = await retrieve_and_answer(
        query=req.query,
        namespace=req.namespace,
        top_k=req.top_k,
        session_id=req.session_id or "default",
    )

    logger.info(
        "Query answered",
        query=req.query[:80],
        sources=len(result.sources),
        namespace=req.namespace,
    )

    return result


@router.get("/stats")
async def get_stats(namespace: str = "default"):
    """Get vector store statistics for a namespace."""
    from rag.vector_store import vector_store
    return vector_store.get_stats(namespace)
