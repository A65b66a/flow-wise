import json
from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient

_SCHEMA = """{
  "analysis_block_1_application_identity": {
    "app_type": "web_application | api_service | data_pipeline | ml_model | ecommerce | real_time | devops_tool | other",
    "app_name": "string (slug)",
    "frontend_framework": "react | vue | angular | nextjs | nuxt | svelte | other | null",
    "framework": "django | laravel | nodejs | spring_boot | fastapi | rails | nextjs | other | null",
    "language": "python | php | javascript | java | go | ruby | typescript | other | null",
    "database_required": "true | false",
    "database_engine": "postgresql | mysql | mongodb | redis | elasticsearch | influxdb | clickhouse | sqlite | null",
    "domain": "healthcare | fintech | ecommerce | media | devops | general | other"
  },
  "analysis_block_2_architecture_pattern": {
    "pattern": "single_vm | two_tier | three_tier | microservices | event_driven | data_pipeline | ml_pipeline",
    "separate_frontend_backend": "true | false",
    "multiple_services": "true | false",
    "api_gateway_required": "true | false",
    "load_balancer_required": "true | false",
    "message_queue_required": "true | false",
    "message_queue_engine": "rabbitmq | kafka | none",
    "cache_required": "true | false",
    "cache_engine": "redis | memcached | none"
  },
  "analysis_block_3_network_design": {
    "network_mode": "auto | manual",
    "vpc_cidr": "10.0.0.0/16",
    "public_subnet_cidr": "10.0.1.0/24",
    "private_subnet_cidr": "10.0.2.0/24",
    "db_subnet_cidr": "10.0.3.0/24",
    "nat_gateway": "true | false",
    "admin_cidr_blocks": "[]"
  },
  "analysis_block_4_traffic_and_scale": {
    "concurrent_users_band": "under_100 | 100_to_1k | 1k_to_10k | 10k_to_100k | 100k_plus",
    "data_storage_band": "small_under_10gb | medium_10_to_500gb | large_500gb_plus",
    "traffic_pattern": "steady | spiky_events | scheduled_batch | realtime_continuous",
    "expected_growth": "true | false",
    "resolved_scale": "small | medium | large"
  },
  "analysis_block_5_availability": {
    "downtime_impact": "casual_acceptable | serious_issue | business_critical",
    "single_server_failure_tolerance": "true | false",
    "disaster_recovery_required": "true | false",
    "sla_target": "best_effort | 99.9 | 99.99",
    "web_vm_count": "1 | 2 | 3",
    "app_vm_count": "1 | 2 | 3",
    "db_replica": "true | false",
    "multi_az": "true | false",
    "backup_policy": "none | daily | hourly"
  },
  "analysis_block_6_access_and_security": {
    "public_facing": "true | false",
    "team_ssh_access": "true | false",
    "compliance_requirements": ["HIPAA | PCI-DSS | GDPR | SOC2 | none"],
    "handles_sensitive_data": "true | false",
    "sensitive_data_types": ["payments | health_records | financial_data | pii | none"],
    "bastion_required": "true | false",
    "waf_required": "true | false",
    "encryption_at_rest": "true | false",
    "encryption_in_transit": "true | false",
    "audit_log_required": "true | false",
    "tls_version": "1.2 | 1.3"
  },
  "analysis_block_7_resource_sizing_and_budget": {
    "vm_size_preference": "small_2vcpu_4gb | medium_4vcpu_8gb | large_8vcpu_16gb | xlarge_16vcpu_32gb | auto_recommend",
    "monthly_budget_ceiling_usd": "number | null",
    "environment": "development | staging | production",
    "web_vm_type": "small | medium | large | xlarge",
    "app_vm_type": "small | medium | large | xlarge",
    "db_vm_type": "small | medium | large | xlarge",
    "db_storage_gb": "20 | 50 | 100 | 200 | 500 | 1000",
    "cost_estimate_monthly_inr": "number | null",
    "cost_optimised_variant_available": "true | false"
  }
}"""

_SYSTEM = f"""You are a Senior Cloud Architect conducting a structured infrastructure discovery interview with an expert user.

TASKS:
1. Parse the conversation history and extract all available information
2. Fill the analysis blocks JSON with known and reasonably-inferred values
3. Identify which CRITICAL fields are still missing or null
4. Generate targeted, expert-level questions to fill only the remaining gaps
5. Set is_complete=true only when ALL critical fields are filled

CRITICAL FIELDS (all must be non-null before is_complete=true):
- analysis_block_1_application_identity.app_type
- analysis_block_2_architecture_pattern.pattern
- analysis_block_4_traffic_and_scale.concurrent_users_band
- analysis_block_5_availability.sla_target
- analysis_block_6_access_and_security.public_facing
- analysis_block_7_resource_sizing_and_budget.environment

QUESTION RULES:
- Use expert cloud infrastructure terminology (VPC, CIDR, SLA, RTO/RPO, multi-AZ, NAT gateway, horizontal scaling, etc.)
- Round 1: generate 5-7 comprehensive questions spanning ALL 7 analysis blocks
- Subsequent rounds: generate only questions for unfilled critical fields (minimum 3 if any gaps remain)
- Combine multiple related fields into one question when logical (e.g. "SLA + multi-AZ + backup policy")
- Never repeat a question already asked in the conversation history

RETURN exactly this JSON (no markdown, no extra text):
{{
  "analysis_blocks": {{
    "analysis_block_1_application_identity": {{}},
    "analysis_block_2_architecture_pattern": {{}},
    "analysis_block_3_network_design": {{}},
    "analysis_block_4_traffic_and_scale": {{}},
    "analysis_block_5_availability": {{}},
    "analysis_block_6_access_and_security": {{}},
    "analysis_block_7_resource_sizing_and_budget": {{}}
  }},
  "is_complete": false,
  "blocks_filled_count": 0,
  "missing_critical_fields": [],
  "questions": [
    {{
      "id": "snake_case_id",
      "text": "Expert question using cloud architecture terminology",
      "why": "Fills block.field_name",
      "type": "text|select|multiselect|boolean",
      "placeholder": "technical example or hint",
      "options": [],
      "block_ref": "analysis_block_N_name"
    }}
  ]
}}

ANALYSIS BLOCKS SCHEMA:
{_SCHEMA}"""


class ExpertAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(
        self,
        user_input: str,
        scope: dict,
        round: int,
        conversation_history: list[dict],
        analysis_blocks: dict,
    ) -> dict:
        history_text = ""
        if conversation_history:
            history_text = "\n\nCONVERSATION HISTORY:\n"
            for turn in conversation_history:
                history_text += f"\n--- Round {turn.get('round', '?')} ---\n"
                for qa in turn.get("qa_pairs", []):
                    history_text += f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}\n"

        blocks_text = ""
        if analysis_blocks:
            blocks_text = f"\n\nCURRENTLY FILLED BLOCKS:\n{json.dumps(analysis_blocks, indent=2)}"

        user_message = (
            f"Application description: {user_input}\n"
            f"Detected scope — app_type: {scope.get('app_type')}, domain: {scope.get('domain')}, "
            f"stack: {scope.get('stack')}, scale_hint: {scope.get('scale_hint')}\n"
            f"Current interview round: {round}"
            f"{history_text}"
            f"{blocks_text}"
        )

        raw = await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=user_message,
            max_tokens=2048,
        )

        llm_questions = raw.get("questions") or []
        source = "llm" if llm_questions else "fallback"

        return {
            "round": round,
            "questions": llm_questions if llm_questions else _fallback_questions(round),
            "analysis_blocks": raw.get("analysis_blocks") or analysis_blocks or {},
            "is_complete": raw.get("is_complete", False),
            "blocks_filled_count": raw.get("blocks_filled_count", 0),
            "missing_critical_fields": raw.get("missing_critical_fields", []),
            "source": source,
        }


def _fallback_questions(round: int) -> list[dict]:
    if round == 1:
        return [
            {
                "id": "app_type_stack",
                "text": "What is the application type and primary tech stack? (language, framework, database engine)",
                "why": "Fills block_1: app_type, language, framework, database_engine",
                "type": "text",
                "placeholder": "e.g., web_application — Python / FastAPI / PostgreSQL",
                "options": [],
                "block_ref": "analysis_block_1_application_identity",
            },
            {
                "id": "architecture_pattern",
                "text": "What deployment architecture pattern are you targeting? Do you require a load balancer, API gateway, or message queue (RabbitMQ / Kafka)?",
                "why": "Fills block_2: pattern, load_balancer_required, api_gateway_required, message_queue_engine",
                "type": "select",
                "placeholder": "",
                "options": ["single_vm", "two_tier", "three_tier", "microservices", "event_driven"],
                "block_ref": "analysis_block_2_architecture_pattern",
            },
            {
                "id": "network_topology",
                "text": "Should VPC/subnet CIDRs be auto-assigned or manually specified? Is a NAT gateway required for private-subnet egress?",
                "why": "Fills block_3: network_mode, vpc_cidr, nat_gateway",
                "type": "select",
                "placeholder": "",
                "options": ["auto (recommended)", "manual — I'll specify CIDRs"],
                "block_ref": "analysis_block_3_network_design",
            },
            {
                "id": "traffic_scale",
                "text": "What is the expected peak concurrent user load band and traffic pattern?",
                "why": "Fills block_4: concurrent_users_band, traffic_pattern",
                "type": "select",
                "placeholder": "",
                "options": ["under_100", "100_to_1k", "1k_to_10k", "10k_to_100k", "100k_plus"],
                "block_ref": "analysis_block_4_traffic_and_scale",
            },
            {
                "id": "sla_availability",
                "text": "What is the SLA target and downtime impact? Is multi-AZ failover and DB replication required? What backup policy (none / daily / hourly)?",
                "why": "Fills block_5: sla_target, multi_az, db_replica, backup_policy",
                "type": "select",
                "placeholder": "",
                "options": ["best_effort (dev/internal)", "99.9% (standard production)", "99.99% (business-critical)"],
                "block_ref": "analysis_block_5_availability",
            },
            {
                "id": "security_compliance",
                "text": "Is the application internet-facing? What compliance frameworks apply (HIPAA / PCI-DSS / GDPR / SOC2 / none)? Are WAF, bastion host, or audit logs required?",
                "why": "Fills block_6: public_facing, compliance_requirements, waf_required, bastion_required",
                "type": "multiselect",
                "placeholder": "",
                "options": ["HIPAA", "PCI-DSS", "GDPR", "SOC2", "none"],
                "block_ref": "analysis_block_6_access_and_security",
            },
            {
                "id": "budget_environment",
                "text": "What is the target environment and monthly infrastructure budget ceiling (USD)? What VM size tier do you prefer?",
                "why": "Fills block_7: environment, monthly_budget_ceiling_usd, vm_size_preference",
                "type": "select",
                "placeholder": "e.g., production — $2 000/month — medium",
                "options": ["development", "staging", "production"],
                "block_ref": "analysis_block_7_resource_sizing_and_budget",
            },
        ]
    return [
        {
            "id": "remaining_details",
            "text": "Please supply any remaining infrastructure details (e.g. specific CIDR ranges, VM types, storage size, compliance scope).",
            "why": "Fills remaining unfilled fields across all analysis blocks",
            "type": "text",
            "placeholder": "e.g., VPC 10.0.0.0/16, app tier: medium (4 vCPU / 8 GB), 200 GB DB storage",
            "options": [],
            "block_ref": "analysis_block_1_application_identity",
        }
    ]
