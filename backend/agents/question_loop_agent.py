from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient


_SYSTEM = """You are a cloud architecture question agent.
Your job is to decide whether to ask the user one more question or stop.
Output ONLY valid JSON. No markdown, no comments, no explanation.

You will receive:
- user_input: original requirement
- answers: already captured answers (do NOT ask these again)
- analysis_blocks: current filled 7 blocks
- confidence: { overall, low_confidence_fields, reasoning }
- question_count
- max_questions

Decision rules:
- If confidence.overall == "high" -> {"action":"stop"}
- If question_count >= max_questions -> {"action":"stop"}
- Else -> {"action":"ask","question":{...}}

When asking:
- Pick the single most impactful field from confidence.low_confidence_fields.
- If low_confidence_fields is empty but overall != high, pick the most impactful missing critical field.
- Never ask about a field that is already present in answers.
- Ask in plain language, no cloud jargon.

Priority order (highest to lowest impact):
1) analysis_block_4_traffic_and_scale.concurrent_users_band
2) analysis_block_6_access_and_security.public_facing
3) analysis_block_5_availability.sla_target
4) analysis_block_1_application_identity.database_engine
5) analysis_block_6_access_and_security.compliance_requirements
6) analysis_block_2_architecture_pattern.message_queue_required
7) analysis_block_4_traffic_and_scale.expected_growth

Question format:
{"action":"ask","question":{"field":"<field path>","text":"<question>","type":"single_choice|multi_choice|number|text","options":[... or null]}}

Use these standard options where possible:
- sla_target:
  ["99% — some downtime acceptable","99.9% — a few hours/year","99.99% — near zero downtime"]
- public_facing:
  ["Internal only (employees/company network)","Public internet","Both public and internal"]
- concurrent_users_band:
  ask as number (type=number) and let the analysis engine normalize.
- compliance:
  ["None","Health / medical records (HIPAA)","Payment card data (PCI-DSS)","EU users / GDPR","SOC2 requirement"]
"""


class QuestionLoopAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(
        self,
        *,
        user_input: str,
        answers: dict[str, Any],
        analysis_blocks: dict[str, Any],
        confidence: dict[str, Any],
        question_count: int,
        max_questions: int,
    ) -> dict[str, Any]:
        context = {
            "user_input": user_input,
            "answers": answers,
            "analysis_blocks": analysis_blocks,
            "confidence": confidence,
            "question_count": question_count,
            "max_questions": max_questions,
        }
        return await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=f"Decide stop vs ask from this context:\n\n{context}",
            max_tokens=600,
        )

