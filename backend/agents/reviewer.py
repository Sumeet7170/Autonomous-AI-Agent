"""
Reviewer Agent — Final quality validation and synthesis.

This is the LAST agent in the pipeline. It:
1. Reviews ALL completed steps together (not just the last one)
2. Synthesizes them into a clean, final answer
3. Assigns a quality score and actionable feedback
4. Returns the polished final output to the user

Think of this agent as the "senior engineer doing the final PR review".
"""
from datetime import datetime
from core.llm import llm_client
from core.logger import get_logger
from models.schemas import AgentName, AgentStatus, AgentStep

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are the ReviewerAgent — a senior AI engineer doing final quality review.

You will receive the original task and ALL completed steps from the team.
Your job is to synthesize everything into a clean, final deliverable.

Your response MUST include:
1. **FINAL ANSWER** — The complete, polished response/solution/output the user needs
2. **QUALITY ASSESSMENT** — Rate each step (Excellent / Good / Needs Improvement)
3. **SUMMARY** — 2-3 sentences describing what was accomplished
4. **NEXT STEPS** — Optional recommendations for the user

Format your response in clear markdown with headers.
Be concise but complete. The user sees this output directly."""


class ReviewerAgent:
    """
    Produces the final, synthesized output after all steps are complete.
    Always runs LAST in the orchestration pipeline.
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    async def run(
        self,
        task: str,
        all_steps: list[AgentStep],
    ) -> AgentStep:
        """
        Review all completed steps and produce the final output.

        Args:
            task:       Original user task
            all_steps:  All AgentStep objects from Executor + Debug agents

        Returns:
            Final AgentStep with the synthesized, polished output
        """
        start = datetime.utcnow()
        self.logger.info("Starting final review", total_steps=len(all_steps))

        # Build a summary of all completed work
        steps_summary = "\n\n".join(
            f"=== STEP {s.step_number} ({s.agent.value}) ===\n"
            f"INPUT: {s.input[:200]}\n"
            f"OUTPUT: {s.output[:800]}"
            for s in all_steps
            if s.status == AgentStatus.SUCCESS
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"ORIGINAL USER TASK:\n{task}\n\n"
                    f"COMPLETED WORK BY THE TEAM:\n\n{steps_summary}\n\n"
                    "Now produce your final review and synthesized output."
                ),
            },
        ]

        try:
            output = await llm_client.complete(messages, temperature=0.4, max_tokens=3000)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)

            self.logger.info(
                "Review complete",
                output_len=len(output),
                duration_ms=duration,
            )

            return AgentStep(
                agent=AgentName.REVIEWER,
                step_number=999,  # Reviewer is always last
                input=f"Final review of {len(all_steps)}-step task: {task[:100]}",
                output=output,
                status=AgentStatus.SUCCESS,
                duration_ms=duration,
                metadata={"steps_reviewed": len(all_steps)},
            )

        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            self.logger.error("Reviewer failed", error=str(e))
            return AgentStep(
                agent=AgentName.REVIEWER,
                step_number=999,
                input=task,
                output="",
                status=AgentStatus.FAILED,
                error=str(e),
                duration_ms=duration,
            )
