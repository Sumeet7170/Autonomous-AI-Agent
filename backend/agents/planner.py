"""
Planner Agent — Breaks a user's task into clear, ordered, executable steps.

Input:  A natural language task description
Output: A structured list of PlanStep objects

Example:
    Input:  "Fix my Python Flask API that crashes on startup"
    Output: [
        PlanStep(step_number=1, description="Read the error logs", agent=EXECUTOR),
        PlanStep(step_number=2, description="Identify the root cause", agent=EXECUTOR),
        PlanStep(step_number=3, description="Write a fix", agent=EXECUTOR),
        PlanStep(step_number=4, description="Test the fix", agent=DEBUGGER),
        PlanStep(step_number=5, description="Validate quality", agent=REVIEWER),
    ]
"""
import json
from datetime import datetime
from core.llm import llm_client
from core.logger import get_logger
from models.schemas import AgentName, AgentStatus, AgentStep, PlanStep

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are the PlannerAgent — an expert AI project manager.

Your only job is to take a user's task and break it into a clear, ordered, numbered list of sub-steps.

Rules:
1. Each step must be SPECIFIC and ACTIONABLE — not vague like "do the work"
2. Assign the correct agent to each step:
   - ExecutorAgent: writing code, creating content, performing actions
   - DebugAgent: testing, finding bugs, validating logic
   - ReviewerAgent: final review, quality check, summarization
3. Output ONLY valid JSON — no markdown fences, no explanations, no text before or after
4. Keep steps between 3 and 8 — don't over-engineer simple tasks

Output format (strict JSON array):
[
  {
    "step_number": 1,
    "description": "Describe what this step does",
    "agent": "ExecutorAgent",
    "expected_output": "What the output of this step should look like"
  }
]"""


class PlannerAgent:
    """
    Decomposes a user task into an ordered execution plan.
    Always runs FIRST in the agent orchestration pipeline.
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    async def run(self, task: str, context: dict = {}) -> tuple[AgentStep, list[PlanStep]]:
        """
        Run the planner on a task.

        Returns:
            agent_step: The recorded AgentStep for this agent's work
            plan:       List of PlanStep objects for the orchestrator to execute
        """
        start = datetime.utcnow()
        self.logger.info("Planning task", task=task[:100])

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Task: {task}\n\n"
                    f"Additional context: {json.dumps(context) if context else 'None'}\n\n"
                    "Create the execution plan as a JSON array."
                )
            }
        ]

        try:
            raw = await llm_client.complete(messages, temperature=0.3, max_tokens=1024)
            # Strip any accidental markdown code fences
            raw = raw.strip().strip("```json").strip("```").strip()
            plan_data = json.loads(raw)

            plan = [
                PlanStep(
                    step_number=s["step_number"],
                    description=s["description"],
                    agent=AgentName(s.get("agent", "ExecutorAgent")),
                    expected_output=s.get("expected_output", ""),
                )
                for s in plan_data
            ]

            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            self.logger.info("Plan created", steps=len(plan), duration_ms=duration)

            agent_step = AgentStep(
                agent=AgentName.PLANNER,
                step_number=0,
                input=task,
                output=f"Created {len(plan)}-step plan:\n" + "\n".join(
                    f"  {s.step_number}. [{s.agent.value}] {s.description}"
                    for s in plan
                ),
                status=AgentStatus.SUCCESS,
                duration_ms=duration,
                metadata={"step_count": len(plan)},
            )
            return agent_step, plan

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error("Plan parsing failed", error=str(e), raw=raw[:200])
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            agent_step = AgentStep(
                agent=AgentName.PLANNER,
                step_number=0,
                input=task,
                output="",
                status=AgentStatus.FAILED,
                error=f"Failed to parse plan: {e}",
                duration_ms=duration,
            )
            return agent_step, []
