from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient


_SYSTEM = """You are a cloud architecture consultant. Your job is to ask the MINIMUM number of questions
needed to confidently fill the 7 architecture analysis blocks for the user's application.

You already have the business requirement (user_input) and scope signals (app_type, domain, stack, scale_hint).
From these you can already infer many fields with confidence.

FIELDS YOU SHOULD NEVER ASK ABOUT:
- Anything directly stated in user_input (stack, framework, domain, app type)
- Network CIDRs, VPC design — always auto-defaults
- team_ssh_access — always true
- encryption_at_rest / encryption_in_transit — always true
- bastion_required — derivable from public_facing

FIELDS YOU MUST ALWAYS ASK (if not already clear):
1. Scale — "How many users do you expect at peak?" (drives sizing, gateway, LB)
2. Visibility — "Will this be public or internal?" (drives WAF, gateway, compliance scope)
3. Uptime — "What is your uptime requirement?" (drives replicas, backups, DR)

FIELDS TO ASK ONLY IF UNCERTAIN from user_input:
4. Sensitive data / compliance — only if domain is healthcare/fintech OR user_input mentions payments/health/PII
5. Expected growth — only if no startup/growth signal in user_input
6. Budget — only if architecture complexity makes cost decisions non-obvious
7. Background processing — only if async/notification/email patterns are unclear

RULES:
- Minimum 3 questions, maximum 7 questions total
- Questions MUST be in plain English — no cloud/infra jargon
- Each question must directly map to a block field decision
- Always ask scale, visibility, uptime first (in that order)
- Use select/multiselect for closed choices, text for numbers, boolean for yes/no

Return ONLY a valid JSON object:
{
  "title": "A few quick questions about your project",
  "description": "One sentence explaining what these questions will help determine",
  "questions": [
    {
      "id": "unique_snake_case_id",
      "text": "The question shown to the user",
      "why": "One sentence: which architecture decision this drives",
      "type": "text|select|multiselect|boolean|number",
      "placeholder": "example or hint",
      "options": [],
      "required": true
    }
  ]
}

For the uptime question, always use these exact options:
["99% — some downtime acceptable", "99.9% — a few hours/year", "99.99% — near zero downtime", "99.999% — mission critical"]

For the visibility question, always use these exact options:
["Public internet", "Internal only (employees/company network)", "Both public and internal"]

For sensitive data, use these options:
["Payment card data", "Health / medical records", "Personal info (PII)", "Financial data", "None of the above"]"""


class SmartGuidedAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(
        self,
        user_input: str,
        scope: dict[str, Any],
    ) -> dict[str, Any]:
        context = (
            f"User's business requirement: {user_input}\n"
            f"App type detected: {scope.get('app_type')}\n"
            f"Domain: {scope.get('domain')}\n"
            f"Stack detected: {scope.get('stack')}\n"
            f"Scale hint: {scope.get('scale_hint')}\n"
            f"Detected signals: {scope.get('detected_signals')}\n"
            f"Confidence score: {scope.get('confidence_score')}"
        )
        raw = await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=(
                "Based on this context, generate the minimum questions needed to fill "
                "the architecture analysis blocks. Always include scale, visibility, and uptime.\n\n"
                f"{context}"
            ),
            max_tokens=1200,
        )
        return {
            "title": raw.get("title", "A few quick questions about your project"),
            "description": raw.get("description", "Your answers will shape the architecture recommendation."),
            "questions": raw.get("questions", _default_questions()),
        }


def _default_questions() -> list[dict]:
    return [
        {
            "id": "users_count",
            "text": "How many people will use this at the same time at peak?",
            "why": "Determines compute sizing, whether a load balancer or API gateway is needed",
            "type": "text",
            "placeholder": "e.g. 100, 5,000, 1 million",
            "options": [],
            "required": True,
        },
        {
            "id": "visibility",
            "text": "Who will be able to access this application?",
            "why": "Determines public network exposure, WAF, and security posture",
            "type": "select",
            "placeholder": "",
            "options": ["Public internet", "Internal only (employees/company network)", "Both public and internal"],
            "required": True,
        },
        {
            "id": "uptime",
            "text": "How much downtime can your business tolerate?",
            "why": "Determines redundancy, backups, and disaster recovery requirements",
            "type": "select",
            "placeholder": "",
            "options": [
                "99% — some downtime acceptable",
                "99.9% — a few hours/year",
                "99.99% — near zero downtime",
                "99.999% — mission critical",
            ],
            "required": True,
        },
    ]
