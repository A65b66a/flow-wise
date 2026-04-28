from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient
from backend.agents.analysis_blocks_agent import AnalysisBlocksAgent
from backend.models.schemas import GuidedAnalysisBlocks
from pydantic import ValidationError


_CONF_SYSTEM = """You are a strict confidence scorer for a 7-block cloud architecture analysis.
Output ONLY valid JSON. No markdown, no comments, no explanation.

You will receive:
- user_input
- scope
- answers (may be partial)
- analysis_blocks (already filled)

Return exactly:
{
  "overall": "high|medium|low",
  "low_confidence_fields": ["..."],
  "reasoning": "one short sentence"
}

Critical fields:
- analysis_block_4_traffic_and_scale.concurrent_users_band
- analysis_block_6_access_and_security.public_facing
- analysis_block_5_availability.sla_target
- analysis_block_1_application_identity.database_engine
- analysis_block_6_access_and_security.compliance_requirements

Scoring:
- overall="high" if all critical fields are explicitly supported by user_input or answers (not just defaults).
- overall="medium" if 1-2 critical fields are defaulted or weakly inferred.
- overall="low" if 3+ critical fields are defaulted or weakly inferred, or user_input is very vague.

low_confidence_fields must contain field paths that were defaulted/guessed.
reasoning must be one short sentence.
"""


class AnalysisConfidenceAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(
        self,
        user_input: str,
        scope: dict[str, Any],
        answers: dict[str, Any] | None = None,
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        answers = answers or {}

        # Step 1: produce valid 7-blocks and validate via Pydantic.
        # If validation fails, retry with the validation error so the LLM can correct enums/types.
        blocks_agent = AnalysisBlocksAgent(self.client)
        last_err: Exception | None = None
        raw_blocks: dict[str, Any] = {}
        prev_answers = answers
        for _attempt in range(max_attempts):
            raw_blocks = await blocks_agent.run(
                user_input=user_input,
                scope=scope,
                previous_answers=prev_answers,
            )
            try:
                blocks_model = GuidedAnalysisBlocks(**raw_blocks)
                blocks = blocks_model.model_dump()
                last_err = None
                break
            except ValidationError as exc:
                last_err = exc
                prev_answers = {
                    **(prev_answers or {}),
                    "_validation_error": str(exc),
                    "_instructions": "Your previous JSON failed schema validation. Output corrected JSON ONLY, using allowed enum values and correct types.",
                    "_previous_json": raw_blocks,
                }
        else:
            # If we exhausted retries, surface the validation error to caller.
            raise ValidationError.from_exception_data(
                title="GuidedAnalysisBlocksValidationFailed",
                line_errors=getattr(last_err, "errors", lambda: [])(),
            )

        # Step 2: compute confidence as a separate strict JSON-only call
        # If we have no captured answers yet, force at least one question in guided-loop flows.
        # Otherwise a very detailed user_input can result in overall="high" immediately,
        # which causes the question agent to stop without asking anything.
        if not answers:
            confidence = {
                "overall": "low",
                "low_confidence_fields": [
                    "analysis_block_4_traffic_and_scale.concurrent_users_band",
                    "analysis_block_6_access_and_security.public_facing",
                    "analysis_block_5_availability.sla_target",
                    "analysis_block_1_application_identity.database_engine",
                    "analysis_block_6_access_and_security.compliance_requirements",
                ],
                "reasoning": "No user answers have been collected yet.",
            }
        else:
            ctx = {"user_input": user_input, "scope": scope, "answers": answers, "analysis_blocks": blocks}
            confidence = await self.client.generate_json(
                system_prompt=_CONF_SYSTEM,
                user_message=f"Score confidence from this context:\n\n{ctx}",
                max_tokens=400,
            )

        return {**blocks, "confidence": confidence}

