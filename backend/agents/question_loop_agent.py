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
- min_questions
- max_questions

Decision rules:
- If question_count < min_questions -> always {"action":"ask","question":{...}}
- Else if confidence.overall == "high" -> {"action":"stop"}
- If question_count >= max_questions -> {"action":"stop"}
- Else -> {"action":"ask","question":{...}}

When asking:
- Pick the single most impactful field from confidence.low_confidence_fields.
- If low_confidence_fields is empty but overall != high, pick the most impactful missing critical field.
- Never ask about a field that is already present in answers.
- Ask in plain language, no cloud jargon.

EXPERT / MANY-QUESTION MODE:
- If min_questions is large (>=20) and question_count < min_questions, you MUST keep asking even if confidence is high.
- In that case, expand beyond the "Priority order" list by selecting additional fields from this field bank,
  always skipping anything already present in answers:
  - analysis_block_1_application_identity.app_type
  - analysis_block_1_application_identity.domain
  - analysis_block_1_application_identity.database_required
  - analysis_block_1_application_identity.database_engine
  - analysis_block_2_architecture_pattern.pattern
  - analysis_block_2_architecture_pattern.separate_frontend_backend
  - analysis_block_2_architecture_pattern.multiple_services
  - analysis_block_2_architecture_pattern.api_gateway_required
  - analysis_block_2_architecture_pattern.load_balancer_required
  - analysis_block_2_architecture_pattern.message_queue_required
  - analysis_block_2_architecture_pattern.message_queue_engine
  - analysis_block_2_architecture_pattern.cache_required
  - analysis_block_2_architecture_pattern.cache_engine
  - analysis_block_4_traffic_and_scale.concurrent_users_band
  - analysis_block_4_traffic_and_scale.traffic_pattern
  - analysis_block_4_traffic_and_scale.data_storage_band
  - analysis_block_4_traffic_and_scale.expected_growth
  - analysis_block_5_availability.sla_target
  - analysis_block_5_availability.backup_policy
  - analysis_block_5_availability.multi_az
  - analysis_block_5_availability.disaster_recovery_required
  - analysis_block_6_access_and_security.public_facing
  - analysis_block_6_access_and_security.handles_sensitive_data
  - analysis_block_6_access_and_security.sensitive_data_types
  - analysis_block_6_access_and_security.compliance_requirements
  - analysis_block_6_access_and_security.waf_required
  - analysis_block_6_access_and_security.audit_log_required
  - analysis_block_7_resource_sizing_and_budget.environment
  - analysis_block_7_resource_sizing_and_budget.monthly_budget_ceiling_usd
  - analysis_block_7_resource_sizing_and_budget.vm_size_preference
  - analysis_block_7_resource_sizing_and_budget.db_storage_gb

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
        min_questions: int = 0,
        max_questions: int,
    ) -> dict[str, Any]:
        context = {
            "user_input": user_input,
            "answers": answers,
            "analysis_blocks": analysis_blocks,
            "confidence": confidence,
            "question_count": question_count,
            "min_questions": min_questions,
            "max_questions": max_questions,
        }
        return await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=f"Decide stop vs ask from this context:\n\n{context}",
            max_tokens=600,
        )

