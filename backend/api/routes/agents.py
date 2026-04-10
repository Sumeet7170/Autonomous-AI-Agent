"""
Agent Execution API Route — POST /api/agents/run

Triggers the full multi-agent pipeline for a task.
Supports streaming (SSE) and non-streaming modes.

Streaming is recommended for the dashboard — it shows live agent progress.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agents.orchestrator import orchestrator
from core.logger import get_logger
from db.database import get_db
from db.models import TaskRecord
from models.schemas import TaskRequest, TaskResponse, AgentStatus

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = get_logger(__name__)


@router.post("/run", response_model=TaskResponse)
async def run_agent_task(
    req: TaskRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a multi-step task using the full agent pipeline:
        PlannerAgent → ExecutorAgent → DebugAgent → ReviewerAgent

    Set `stream: true` in the request body to receive real-time SSE events.
    The frontend task dashboard uses streaming mode.
    """
    session_id = req.session_id or str(uuid.uuid4())

    if req.stream:
        # ── Streaming Mode ────────────────────────────────────────────────────
        return StreamingResponse(
            orchestrator.stream(
                task=req.task,
                session_id=session_id,
                context=req.context,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ── Non-Streaming Mode ────────────────────────────────────────────────────
    logger.info("Starting agent task", task=req.task[:100], session_id=session_id)

    # Create pending DB record
    task_record = TaskRecord(
        id=str(uuid.uuid4()),
        session_id=session_id,
        task_text=req.task,
        status="running",
    )
    db.add(task_record)
    await db.flush()

    # Run the orchestrator
    result = await orchestrator.run(
        task=req.task,
        session_id=session_id,
        context=req.context,
    )

    # Update DB record with result
    task_record.status = result.status.value
    task_record.step_count = len(result.steps)
    task_record.final_output = result.final_output
    task_record.duration_ms = result.total_duration_ms
    task_record.plan_json = [p.model_dump() for p in result.plan]
    task_record.steps_json = [s.model_dump(mode="json") for s in result.steps]
    task_record.completed_at = datetime.utcnow()

    logger.info(
        "Task complete",
        task_id=result.task_id,
        steps=len(result.steps),
        duration_ms=result.total_duration_ms,
    )

    return result


@router.get("/history/{session_id}")
async def get_task_history(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get all task executions for a session."""
    from sqlalchemy import select
    result = await db.execute(
        select(TaskRecord)
        .where(TaskRecord.session_id == session_id)
        .order_by(TaskRecord.created_at.desc())
        .limit(20)
    )
    records = result.scalars().all()
    return [
        {
            "task_id": r.id,
            "task": r.task_text[:200],
            "status": r.status,
            "step_count": r.step_count,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
