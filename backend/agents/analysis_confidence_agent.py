from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient
from backend.agents.analysis_blocks_agent import AnalysisBlocksAgent


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
    ) -> dict[str, Any]:
        answers = answers or {}

        # Step 1: produce valid 7-blocks via the existing analysis block agent prompt
        blocks_agent = AnalysisBlocksAgent(self.client)
        blocks = await blocks_agent.run(user_input=user_input, scope=scope, previous_answers=answers)

        # Step 2: compute confidence as a separate strict JSON-only call
        ctx = {"user_input": user_input, "scope": scope, "answers": answers, "analysis_blocks": blocks}
        confidence = await self.client.generate_json(
            system_prompt=_CONF_SYSTEM,
            user_message=f"Score confidence from this context:\n\n{ctx}",
            max_tokens=400,
        )

        return {**blocks, "confidence": confidence}

