"""
Debug Agent — Validates and fixes the Executor's output.

After each ExecutorAgent step, the DebugAgent:
1. Reviews the output for errors, bugs, and issues
2. If issues are found, corrects them and returns the fixed version
3. If all is good, passes the output through unchanged

This agent acts as a "quality gate" — it ensures each step's output
is correct before the Reviewer does the final pass.
"""
import json
from datetime import datetime
from core.llm import llm_client
from core.logger import get_logger
from models.schemas import AgentName, AgentStatus, AgentStep

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are the DebugAgent — an expert AI code reviewer and quality assurance engineer.

Your job is to review the output from the ExecutorAgent and fix any issues.

What to check:
1. CODE: Syntax errors, logical bugs, missing imports, incorrect logic
2. CONTENT: Factual errors, incomplete sections, contradictions
3. STRUCTURE: Missing required sections, wrong format, unclear output
4. COMPLETENESS: Does the output actually fulfill the step's requirement?

Response format (strict JSON):
{
  "has_issues": true/false,
  "issues_found": ["list of specific issues found, or empty list"],
  "fixed_output": "The corrected and improved output. If no issues, copy the original output unchanged.",
  "summary": "One sentence describing what you checked and what you did."
}

Output ONLY the JSON object. No markdown, no explanations outside the JSON."""


class DebugAgent:
    """
    Reviews and optionally fixes the ExecutorAgent's output.
    Called after every ExecutorAgent step.
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    async def run(
        self,
        step_number: int,
        step_description: str,
        executor_output: str,
        task: str,
    ) -> AgentStep:
        """
        Debug and optionally fix the executor's output.

        Args:
            step_number:       Which step we're debugging
            step_description:  What the step was supposed to do
            executor_output:   The raw output from the ExecutorAgent
            task:              The original user task (for context)

        Returns:
            AgentStep with the validated/fixed output
        """
        start = datetime.utcnow()
        self.logger.info("Debugging step", step=step_number)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"ORIGINAL TASK: {task}\n\n"
                    f"STEP {step_number} DESCRIPTION: {step_description}\n\n"
                    f"EXECUTOR OUTPUT TO REVIEW:\n{executor_output}\n\n"
                    "Review this output and return your JSON response."
                ),
            },
        ]

        try:
            raw = await llm_client.complete(messages, temperature=0.2, max_tokens=2048)
            raw = raw.strip().strip("```json").strip("```").strip()
            result = json.loads(raw)

            has_issues = result.get("has_issues", False)
            issues = result.get("issues_found", [])
            fixed = result.get("fixed_output", executor_output)
            summary = result.get("summary", "No issues found.")

            duration = int((datetime.utcnow() - start).total_seconds() * 1000)

            if has_issues:
                self.logger.warning(
                    "Issues found and fixed",
                    step=step_number,
                    issues=issues,
                    duration_ms=duration,
                )
                output_text = (
                    f"🔧 Issues fixed: {', '.join(issues)}\n\n"
                    f"✅ Summary: {summary}\n\n"
                    f"--- FIXED OUTPUT ---\n{fixed}"
                )
            else:
                self.logger.info("Step validated — no issues", step=step_number)
                output_text = f"✅ {summary}\n\n--- VALIDATED OUTPUT ---\n{fixed}"

            return AgentStep(
                agent=AgentName.DEBUGGER,
                step_number=step_number,
                input=f"Review step {step_number}: {step_description[:100]}",
                output=output_text,
                status=AgentStatus.SUCCESS,
                duration_ms=duration,
                metadata={
                    "has_issues": has_issues,
                    "issues_found": issues,
                    "cleaned_output": fixed,
                },
            )

        except (json.JSONDecodeError, KeyError) as e:
            # If debug agent itself fails, don't block — pass the original output through
            self.logger.error("Debug agent parsing failed", error=str(e))
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return AgentStep(
                agent=AgentName.DEBUGGER,
                step_number=step_number,
                input=f"Review step {step_number}",
                output=f"⚠️ Debug agent encountered a parsing error. Original output passed through.\n\n{executor_output}",
                status=AgentStatus.SUCCESS,  # Don't fail — just warn
                duration_ms=duration,
                metadata={"has_issues": False, "cleaned_output": executor_output},
            )
