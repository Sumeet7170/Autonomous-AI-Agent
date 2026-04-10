"""
Agent Orchestrator — The Multi-Agent Coordination Engine.

This is the heart of the system. It coordinates all 4 agents:
    PlannerAgent  → creates the plan
    ExecutorAgent → executes each step
    DebugAgent    → validates/fixes each step's output
    ReviewerAgent → final quality synthesis

The Orchestrator supports TWO modes:
    1. run()       — Returns the full result at once (for simple API calls)
    2. stream()    — Yields SSE events in real-time (for the chat dashboard)

The stream() method allows the frontend to show LIVE agent progress:
    "🧠 PlannerAgent: Created 4-step plan..."
    "⚙️ ExecutorAgent: Writing the code fix..."
    "🔧 DebugAgent: Found 1 issue, fixed..."
    "✅ ReviewerAgent: All done!"
"""
import json
import uuid
import asyncio
from datetime import datetime
from typing import AsyncIterator

from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent
from agents.debugger import DebugAgent
from agents.reviewer import ReviewerAgent
from memory.agent_memory import agent_memory
from core.logger import get_logger
from models.schemas import (
    AgentName, AgentStatus, AgentStep,
    PlanStep, TaskResponse,
)

logger = get_logger(__name__)


class AgentOrchestrator:
    """
    Coordinates Planner → Executor → Debug → Reviewer in sequence.
    One instance shared across all requests (stateless — session tracked via memory).
    """

    def __init__(self):
        self.planner  = PlannerAgent()
        self.executor = ExecutorAgent()
        self.debugger = DebugAgent()
        self.reviewer = ReviewerAgent()
        logger.info("AgentOrchestrator initialized")

    async def run(self, task: str, session_id: str, context: dict = {}) -> TaskResponse:
        """
        Non-streaming execution — runs the full pipeline and returns TaskResponse.
        Used for simple API calls that don't need real-time updates.
        """
        task_id = str(uuid.uuid4())
        start = datetime.utcnow()
        all_steps: list[AgentStep] = []
        plan: list[PlanStep] = []

        # ── STEP 1: Plan ──────────────────────────────────────────────────────
        planner_step, plan = await self.planner.run(task, context)
        all_steps.append(planner_step)

        if not plan or planner_step.status == AgentStatus.FAILED:
            return TaskResponse(
                task_id=task_id,
                session_id=session_id,
                status=AgentStatus.FAILED,
                task=task,
                steps=all_steps,
                error="PlannerAgent failed to create a plan.",
            )

        # ── STEP 2: Execute + Debug each step ────────────────────────────────
        previous_outputs: list[str] = []

        for plan_step in plan:
            # Execute
            exec_step = await self.executor.run(
                step=plan_step,
                task=task,
                previous_outputs=previous_outputs,
            )
            all_steps.append(exec_step)

            if exec_step.status == AgentStatus.FAILED:
                logger.warning("Executor failed, skipping debug", step=plan_step.step_number)
                continue

            # Debug / validate
            debug_step = await self.debugger.run(
                step_number=plan_step.step_number,
                step_description=plan_step.description,
                executor_output=exec_step.output,
                task=task,
            )
            all_steps.append(debug_step)

            # Use the debugger's cleaned output for subsequent steps
            cleaned = debug_step.metadata.get("cleaned_output", exec_step.output)
            previous_outputs.append(cleaned)

        # ── STEP 3: Review ────────────────────────────────────────────────────
        review_step = await self.reviewer.run(task=task, all_steps=all_steps)
        all_steps.append(review_step)

        # ── Save to Memory ────────────────────────────────────────────────────
        agent_memory.add_message(session_id, "user", task)
        agent_memory.add_message(session_id, "assistant", review_step.output)
        agent_memory.add_task_result(session_id, {
            "task_id": task_id,
            "task": task,
            "status": AgentStatus.SUCCESS,
        })

        total_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        logger.info("Task complete", task_id=task_id, steps=len(all_steps), duration_ms=total_ms)

        return TaskResponse(
            task_id=task_id,
            session_id=session_id,
            status=AgentStatus.SUCCESS,
            task=task,
            plan=plan,
            steps=all_steps,
            final_output=review_step.output,
            total_duration_ms=total_ms,
        )

    async def stream(
        self, task: str, session_id: str, context: dict = {}
    ) -> AsyncIterator[str]:
        """
        Streaming SSE execution — yields JSON events as each agent completes.

        Event format (newline-delimited JSON, wrapped in SSE):
            data: {"type": "agent_step", "step": {...}}

        Event types:
            "start"      — task started
            "plan"       — planner finished, showing the plan
            "agent_step" — one executor/debug step finished
            "review"     — reviewer step finished
            "complete"   — all done, includes final_output
            "error"      — something went wrong
        """
        task_id = str(uuid.uuid4())
        all_steps: list[AgentStep] = []
        plan: list[PlanStep] = []
        start = datetime.utcnow()

        def sse(event_type: str, data: dict) -> str:
            """Format a payload as an SSE event line."""
            return f"data: {json.dumps({'type': event_type, 'task_id': task_id, **data})}\n\n"

        try:
            # ── START ─────────────────────────────────────────────────────────
            yield sse("start", {"task": task, "session_id": session_id})

            # ── PLAN ──────────────────────────────────────────────────────────
            planner_step, plan = await self.planner.run(task, context)
            all_steps.append(planner_step)
            yield sse("plan", {
                "step": planner_step.model_dump(mode="json"),
                "plan": [p.model_dump() for p in plan],
            })

            if not plan or planner_step.status == AgentStatus.FAILED:
                yield sse("error", {"message": "PlannerAgent failed to create a plan."})
                return

            # ── EXECUTE + DEBUG ───────────────────────────────────────────────
            previous_outputs: list[str] = []

            for plan_step in plan:
                # Execute
                exec_step = await self.executor.run(
                    step=plan_step,
                    task=task,
                    previous_outputs=previous_outputs,
                )
                all_steps.append(exec_step)
                yield sse("agent_step", {"step": exec_step.model_dump(mode="json")})

                if exec_step.status == AgentStatus.FAILED:
                    continue

                # Debug
                debug_step = await self.debugger.run(
                    step_number=plan_step.step_number,
                    step_description=plan_step.description,
                    executor_output=exec_step.output,
                    task=task,
                )
                all_steps.append(debug_step)
                yield sse("agent_step", {"step": debug_step.model_dump(mode="json")})

                cleaned = debug_step.metadata.get("cleaned_output", exec_step.output)
                previous_outputs.append(cleaned)

                # Small pause between steps so the UI renders smoothly
                await asyncio.sleep(0.05)

            # ── REVIEW ────────────────────────────────────────────────────────
            review_step = await self.reviewer.run(task=task, all_steps=all_steps)
            all_steps.append(review_step)
            yield sse("review", {"step": review_step.model_dump(mode="json")})

            # ── COMPLETE ──────────────────────────────────────────────────────
            total_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

            # Save to memory
            agent_memory.add_message(session_id, "user", task)
            agent_memory.add_message(session_id, "assistant", review_step.output)

            yield sse("complete", {
                "final_output": review_step.output,
                "total_duration_ms": total_ms,
                "step_count": len(all_steps),
            })

        except Exception as e:
            logger.error("Orchestrator stream error", error=str(e))
            yield sse("error", {"message": str(e)})


# ── Singleton ─────────────────────────────────────────────────────────────────
orchestrator = AgentOrchestrator()
