from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient
from backend.utils.template_loader import get_all_templates, get_template_by_id

_SYSTEM = """You are a cloud architect selecting the best architecture template for requirements.

Given business requirements and available templates, return ONLY a valid JSON:
{
  "template_id": "selected template id",
  "confidence": 0.0,
  "selection_reasoning": "2-3 sentence explanation of why this template fits",
  "configuration": {
    "variables": {
      "instance_type": "...",
      "db_instance_class": "...",
      "min_instances": 1,
      "max_instances": 4,
      "enable_cdn": false,
      "enable_waf": false,
      "enable_multi_az": true,
      "db_engine": "...",
      "cache_enabled": false
    },
    "overrides": {}
  }
}

Template selection rules:
- microservices → use microservices template if >3 independent services mentioned
- event/queue/async → event-driven template
- simple web/SaaS with DB → three-tier web
- mobile backend / simple API → two-tier
- Always choose the simplest template that meets requirements (avoid over-engineering)

COMPONENT SYNC (CRITICAL)
The selected template's cytoscape_elements must include nodes for every enabled component in the analysis blocks:
- message_queue_required=true → there must be a queue node (Kafka, RabbitMQ, or generic queue)
- cache_required=true → there must be a cache node (Redis/Memcached)
- api_gateway_required=true → there must be an API gateway node
- load_balancer_required=true → there must be a load balancer node
- db_replica=true → there must be a replica/standby DB node
- waf_required=true → there must be a WAF node
- bastion_required=true → there must be a bastion host node
- disaster_recovery_required=true → there must be a DR/secondary region node
When choosing between templates, prefer the one whose diagram already includes all required components.
Set configuration variables (enable_cdn, enable_waf, cache_enabled, etc.) to reflect every enabled block field.

CLIENT TYPE IN DIAGRAM (CRITICAL)
The entry point into the architecture must reflect the actual client type from requirements.app_type:
- web_application / ecommerce / saas → entry node should be "Web Browser" or "User (Browser)"
- mobile_app → entry node should be "Mobile App (iOS/Android)"
- api_service / backend_service → entry node should be "Third-party API Consumer" or "External Client"
- cli_tool → entry node should be "CLI User"
- data_pipeline / ml_model → entry node should be "Data Source" or "Upstream System"
Set configuration.overrides.client_type to the appropriate label so the diagram generation layer can use it."""


class TemplateAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(self, requirements: dict) -> dict:
        templates = get_all_templates()
        template_summaries = [
            {
                "id": t["id"],
                "name": t["name"],
                "description": t["description"],
                "use_cases": t.get("use_cases", []),
                "keywords": t.get("keywords", []),
                "scale": t.get("scale", []),
            }
            for t in templates
        ]

        context = (
            f"Requirements:\n{_fmt(requirements)}\n\n"
            f"Available Templates:\n{_fmt(template_summaries)}"
        )

        raw = await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=f"Select the best template:\n\n{context}",
            max_tokens=1024,
        )

        template_id = raw.get("template_id", "three-tier-web")
        template = get_template_by_id(template_id) or get_template_by_id("three-tier-web") or templates[0]

        config = raw.get("configuration", {})
        variables = config.get("variables", {})
        _apply_requirement_rules(variables, requirements)

        return {
            "template_id": template["id"],
            "template_name": template["name"],
            "template": template,
            "confidence": float(raw.get("confidence", 0.8)),
            "selection_reasoning": raw.get("selection_reasoning", ""),
            "configuration": {
                "resources": template.get("resources", {}),
                "network_schema": template.get("network_schema", {}),
                "security_rules": template.get("security_rules", []),
                "variables": variables,
                "overrides": config.get("overrides", {}),
            },
            "cytoscape_elements": template.get("cytoscape_elements", {"nodes": [], "edges": []}),
        }


def _apply_requirement_rules(variables: dict, req: dict) -> None:
    availability = req.get("availability", {})
    network = req.get("network", {})
    security = req.get("security", {})
    scale = req.get("scale", {})

    if availability.get("multi_az"):
        variables.setdefault("enable_multi_az", True)
        variables.setdefault("min_instances", 2)

    if network.get("cdn_required"):
        variables["enable_cdn"] = True

    if security.get("data_classification") in ("confidential", "restricted"):
        variables["enable_waf"] = True

    users = scale.get("concurrent_users", 0)
    if users > 10000:
        variables.setdefault("max_instances", 8)
    elif users > 1000:
        variables.setdefault("max_instances", 4)
    else:
        variables.setdefault("max_instances", 2)


def _fmt(obj) -> str:
    import json
    return json.dumps(obj, indent=2)
