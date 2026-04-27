from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient

_SYSTEM = """You are a senior cloud architect. Convert minimal user inputs into a structured business requirements specification.

Given scope analysis, confirmed detections, and quick inputs (users/visibility/uptime), produce a full requirements JSON.

Return ONLY a valid JSON object:
{
  "app_type": "string",
  "scale": {
    "concurrent_users": 0,
    "requests_per_second": 0,
    "storage_tb": 0.0,
    "growth_rate": "steady|growing|spiky"
  },
  "availability": {
    "uptime_requirement": "99.9%",
    "rto_minutes": 60,
    "rpo_minutes": 30,
    "multi_az": true
  },
  "network": {
    "internet_facing": true,
    "cdn_required": false,
    "multi_region": false
  },
  "security": {
    "authentication": true,
    "data_classification": "public|internal|confidential|restricted",
    "compliance": []
  },
  "budget": {
    "tier": "startup|growing|enterprise",
    "monthly_estimate_usd": 0,
    "cost_optimization": "aggressive|balanced|performance-first"
  },
  "stack": [],
  "derived_requirements": ["list of requirements inferred from inputs"]
}

Derivation rules:
- 99.99%+ uptime → multi_az=true, rto_minutes<=15
- public + >10k users → cdn_required=true
- healthcare/fintech domain → compliance=["HIPAA"/"PCI-DSS"], data_classification="confidential"
- e-commerce → authentication=true, consider CDN
- requests_per_second ≈ concurrent_users / 10 (rough estimate)"""


class BusinessRequirementAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(
        self,
        user_input: str,
        scope: dict,
        auto_pilot_init: dict,
        quick_inputs: dict,
    ) -> dict:
        context = f"""User Input: {user_input}
App Type: {scope.get('app_type')}
Domain: {scope.get('domain')}
Scale Hint: {scope.get('scale_hint')}
Stack: {scope.get('stack')}
Architecture Pattern: {auto_pilot_init.get('confirmed_detections', {}).get('architecture_pattern')}

Quick Inputs from User:
- Expected Users: {quick_inputs.get('users')}
- Visibility: {quick_inputs.get('visibility')}
- Uptime Required: {quick_inputs.get('uptime')}"""

        raw = await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=f"Generate requirements from:\n\n{context}",
            max_tokens=2048,
        )

        return _normalize_requirements(raw, scope, quick_inputs)


def _normalize_requirements(raw: dict, scope: dict, quick_inputs: dict) -> dict:
    scale = raw.get("scale", {})
    availability = raw.get("availability", {})
    network = raw.get("network", {})
    security = raw.get("security", {})
    budget = raw.get("budget", {})
    return {
        "app_type": raw.get("app_type", scope.get("app_type", "web")),
        "scale": {
            "concurrent_users": int(scale.get("concurrent_users", 0)),
            "requests_per_second": int(scale.get("requests_per_second", 0)),
            "storage_tb": float(scale.get("storage_tb", 0.0)),
            "growth_rate": scale.get("growth_rate", "steady"),
        },
        "availability": {
            "uptime_requirement": availability.get("uptime_requirement", quick_inputs.get("uptime", "99.9%")),
            "rto_minutes": int(availability.get("rto_minutes", 60)),
            "rpo_minutes": int(availability.get("rpo_minutes", 30)),
            "multi_az": bool(availability.get("multi_az", True)),
        },
        "network": {
            "internet_facing": bool(network.get("internet_facing", True)),
            "cdn_required": bool(network.get("cdn_required", False)),
            "multi_region": bool(network.get("multi_region", False)),
        },
        "security": {
            "authentication": bool(security.get("authentication", True)),
            "data_classification": security.get("data_classification", "internal"),
            "compliance": security.get("compliance", []),
        },
        "budget": {
            "tier": budget.get("tier", "growing"),
            "monthly_estimate_usd": int(budget.get("monthly_estimate_usd", 0)),
            "cost_optimization": budget.get("cost_optimization", "balanced"),
        },
        "stack": raw.get("stack", scope.get("stack", [])),
        "derived_requirements": raw.get("derived_requirements", []),
    }
