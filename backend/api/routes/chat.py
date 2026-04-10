"""
Chat API Route — POST /api/chat

Unified chat endpoint supporting 3 modes:
  - "chat"  → Regular LLM conversation with session memory
  - "rag"   → Document Q&A (RAG mode — answers from uploaded files only)
  - "agent" → Trigger the multi-agent pipeline

Streaming (SSE) is the default for all modes.
"""
import json
import uuid
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from core.llm import llm_client
from core.logger import get_logger
from memory.agent_memory import agent_memory
from models.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = get_logger(__name__)

CHAT_SYSTEM_PROMPT = """You are a helpful, intelligent AI assistant.
Be clear, concise, and accurate. Format your responses with markdown when it improves readability.
If you don't know something, say so honestly."""


@router.post("")
async def chat(req: ChatRequest):
    """
    Unified chat endpoint.

    Modes:
      - `chat`:  General LLM conversation with memory
      - `rag`:   RAG query — answers come ONLY from uploaded documents
      - `agent`: Triggers the multi-agent task execution pipeline

    All modes support streaming by default. Returns SSE-formatted text.
    """
    session_id = req.session_id or str(uuid.uuid4())

    # ── RAG Mode ──────────────────────────────────────────────────────────────
    if req.mode == "rag":
        from rag.retriever import stream_rag_answer
        return StreamingResponse(
            stream_rag_answer(
                query=req.message,
                namespace=req.namespace,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Agent Mode ────────────────────────────────────────────────────────────
    if req.mode == "agent":
        from agents.orchestrator import orchestrator
        return StreamingResponse(
            orchestrator.stream(
                task=req.message,
                session_id=session_id,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Chat Mode (default) ───────────────────────────────────────────────────
    # Add user message to memory
    agent_memory.add_message(session_id, "user", req.message)

    # Build message list: system + history
    history = agent_memory.get_messages(session_id)
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + history

    async def event_stream():
        full_response = ""
        try:
            async for chunk in llm_client.stream(messages):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'token', 'data': chunk})}\n\n"
        except Exception as e:
            logger.error("Chat stream error", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
        finally:
            # Save assistant response to memory
            if full_response:
                agent_memory.add_message(session_id, "assistant", full_response)
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get chat history for a session."""
    messages = agent_memory.get_messages(session_id)
    summary = agent_memory.get_summary(session_id)
    return {"session_id": session_id, "messages": messages, "summary": summary}


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear all memory for a session."""
    agent_memory.clear_session(session_id)
    return {"message": f"Session {session_id} cleared."}
