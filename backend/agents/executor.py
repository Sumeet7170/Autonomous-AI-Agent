"""
Executor Agent — Performs the actual work for each planned step.

This is the "workhorse" agent. It receives one step at a time and
executes it — writing code, creating content, generating answers, etc.

The Executor always has access to:
  - The original task (for context)
  - The step description (what specifically to do)
  - Previous steps' outputs (accumulated context)
"""
from datetime import datetime
from core.llm import llm_client
from core.logger import get_logger
from models.schemas import AgentName, AgentStatus, AgentStep, PlanStep

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are the ExecutorAgent — a highly skilled AI software engineer and problem solver.

Your job is to perform the specific step assigned to you with high quality output.

Rules:
1. Focus ONLY on the current step — don't skip ahead or do other steps
2. Be specific and thorough — provide complete, working output
3. If writing code, include imports and make it runnable
4. If doing analysis, be detailed and structured
5. Reference previous steps' context when relevant
6. End your response with a clear "RESULT:" section summarizing what you produced"""


class ExecutorAgent:
    """
    Executes a single planned step.
    Called once per step in the orchestration loop.
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    async def run(
        self,
        step: PlanStep,
        task: str,
        previous_outputs: list[str],
    ) -> AgentStep:
        """
        Execute one step of the plan.

        Args:
            step:             The PlanStep to execute
            task:             The original user task (for context)
            previous_outputs: Outputs from all prior steps

        Returns:
            AgentStep with the result of this step's execution
        """
        start = datetime.utcnow()
        self.logger.info(
            "Executing step",
            step=step.step_number,
            description=step.description[:100],
        )

        # Build context from previous outputs
        context_str = ""
        if previous_outputs:
            context_str = "\n\n--- PREVIOUS STEPS CONTEXT ---\n"
            context_str += "\n\n".join(
                f"[Step {i+1} output]: {out[:500]}"
                for i, out in enumerate(previous_outputs)
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"ORIGINAL TASK: {task}\n\n"
                    f"YOUR CURRENT STEP ({step.step_number}): {step.description}\n"
                    f"EXPECTED OUTPUT: {step.expected_output}\n"
                    f"{context_str}\n\n"
                    "Execute this step now. Be thorough and provide complete output."
                ),
            },
        ]

        try:
            output = await llm_client.complete(messages, temperature=0.5, max_tokens=2048)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)

            self.logger.info(
                "Step executed",
                step=step.step_number,
                output_len=len(output),
                duration_ms=duration,
            )

            return AgentStep(
                agent=AgentName.EXECUTOR,
                step_number=step.step_number,
                input=step.description,
                output=output,
                status=AgentStatus.SUCCESS,
                duration_ms=duration,
                metadata={"expected_output": step.expected_output},
            )

        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            self.logger.error("Execution failed", step=step.step_number, error=str(e))
            return AgentStep(
                agent=AgentName.EXECUTOR,
                step_number=step.step_number,
                input=step.description,
                output="",
                status=AgentStatus.FAILED,
                error=str(e),
                duration_ms=duration,
            )
