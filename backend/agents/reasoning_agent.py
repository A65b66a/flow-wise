from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient

_SYSTEM = """You are a senior cloud architect explaining architectural decisions to a technical audience.

Given the selected template, configuration, and business requirements, produce a comprehensive reasoning log.

Return ONLY a valid JSON object:
{
  "template_selection": "2-3 sentences explaining why this architecture pattern was chosen",
  "component_choices": [
    "Reason for load balancer: ...",
    "Reason for auto-scaling: ...",
    "Reason for database choice: ...",
    "Reason for caching layer: ..."
  ],
  "trade_offs": [
    "Trade-off 1: ...",
    "Trade-off 2: ..."
  ],
  "alternatives_considered": [
    "Alternative: [name] - rejected because ...",
    "Alternative: [name] - rejected because ..."
  ],
  "budget_flags": [],
  "inferred_assumptions": [],
  "summary": {
    "architecture_type": "human-readable architecture name",
    "components": ["component1", "component2"],
    "estimated_monthly_cost": "$X - $Y/month",
    "deployment_complexity": "Low|Medium|High",
    "key_highlights": ["highlight1", "highlight2", "highlight3"]
  }
}

COMPONENT JUSTIFICATION (CRITICAL)
Every entry in component_choices must follow the format:
  "Reason for [component name]: [one sentence why it is included, referencing a specific requirement]"
If you cannot state a clear reason for a component, do not include it in component_choices
and consider whether it should be in the architecture at all.
Never list a component without a justification.

BUDGET CONSTRAINT CHECK (CRITICAL)
If requirements.budget.monthly_estimate_usd > 0 and requirements.budget.tier is known:
  - Compare estimated_monthly_cost range against the stated budget ceiling.
  - If the low end of the estimated cost exceeds the ceiling, add a budget_flags entry:
    "Estimated cost ($X/month) may exceed stated budget ceiling ($Y/month). Consider downsizing [component]."
  - If the architecture was already downsized to fit the budget, note it:
    "Architecture sized down from [original] to fit within $Y/month budget."
  - budget_flags must be a JSON array of strings (empty array if no flags).

INFERRED VS STATED (CRITICAL)
If requirements contains inferred_fields (a list of field paths that were assumed, not stated by the user):
  - For each inferred field that meaningfully affects the architecture, add an entry to inferred_assumptions:
    "Assumed [field] = [value] because [brief reason]. You can update this in the questionnaire."
  - inferred_assumptions must be a JSON array of strings (empty array if nothing was inferred).
  - Never present an inferred value as if the user stated it.

Be specific and reference actual business requirements (users, uptime, domain) in your reasoning.
estimated_monthly_cost should be a realistic range based on the scale requirements."""


class ReasoningAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(self, template_result: dict, requirements: dict) -> dict:
        import json

        context = (
            f"Selected Template: {template_result.get('template_name')}\n"
            f"Template ID: {template_result.get('template_id')}\n"
            f"Configuration Variables: {json.dumps(template_result.get('configuration', {}).get('variables', {}), indent=2)}\n\n"
            f"Business Requirements:\n{json.dumps(requirements, indent=2)}"
        )

        raw = await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=f"Generate architecture reasoning:\n\n{context}",
            max_tokens=2048,
        )

        summary = raw.get("summary", {})
        return {
            "reasoning": {
                "template_selection": raw.get("template_selection", ""),
                "component_choices": raw.get("component_choices", []),
                "trade_offs": raw.get("trade_offs", []),
                "alternatives_considered": raw.get("alternatives_considered", []),
            },
            "summary": {
                "architecture_type": summary.get("architecture_type", template_result.get("template_name", "")),
                "components": summary.get("components", []),
                "estimated_monthly_cost": summary.get("estimated_monthly_cost", "Estimate unavailable"),
                "deployment_complexity": summary.get("deployment_complexity", "Medium"),
                "key_highlights": summary.get("key_highlights", []),
            },
        }
