from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient

_BLOCK_META = {
    1: ("Application Identity", "Understand what the application does and who it serves"),
    2: ("Architecture Pattern", "Determine how the system components should be organized"),
    3: ("Network Design", "Define how the application connects to users and the internet"),
    4: ("Traffic & Scale", "Understand load patterns and data volume"),
    5: ("Availability", "Define reliability and recovery requirements"),
    6: ("Security", "Identify data sensitivity and protection needs"),
    7: ("Budget & Priorities", "Set cost expectations and optimization goals"),
}

_SYSTEM = """You are a cloud architecture consultant conducting a structured discovery.
Generate 3-4 questions for the specified block. Questions MUST be problem-based (not infra-terms).

Return ONLY a valid JSON object:
{
  "block": 1,
  "title": "Block Title",
  "description": "Short description of what this block covers",
  "questions": [
    {
      "id": "unique_snake_case_id",
      "text": "The question as shown to the user",
      "why": "One sentence: why this information matters for architecture",
      "type": "text|select|multiselect|boolean|number",
      "placeholder": "example or hint",
      "options": [],
      "required": false
    }
  ]
}

Block guidance:
Block 1 - Identity: app purpose, target users, primary goal, existing systems to integrate
Block 2 - Pattern: real-time needs, independent vs unified codebase, external APIs, job processing
Block 3 - Network: internet vs internal, geographic reach, mobile clients, static assets
Block 4 - Scale: concurrent users, daily transactions, data generated per day, growth timeline
Block 5 - Availability: acceptable downtime, business impact of outage, backup requirements
Block 6 - Security: handles personal data, regulatory requirements, who needs access
Block 7 - Budget: monthly budget, cost priority vs performance, team size for ops

Use plain English. Never use technical jargon like VPC, CIDR, replica, shard, etc."""


class GuidedAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def get_block_questions(
        self, block: int, user_input: str, scope: dict, previous_answers: dict
    ) -> dict:
        title, description = _BLOCK_META.get(block, (f"Block {block}", ""))
        context = (
            f"Application: {user_input}\n"
            f"App Type: {scope.get('app_type')}, Domain: {scope.get('domain')}\n"
            f"Stack: {scope.get('stack')}\n"
            f"Previous answers: {previous_answers or 'none yet'}"
        )
        raw = await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=(
                f"Generate questions for Block {block}: {title}\n"
                f"Context:\n{context}"
            ),
            max_tokens=1024,
        )
        return {
            "block": block,
            "title": raw.get("title", title),
            "description": raw.get("description", description),
            "questions": raw.get("questions", _fallback_questions(block)),
        }

    async def run(self, **kwargs) -> dict:
        return await self.get_block_questions(**kwargs)


def _fallback_questions(block: int) -> list[dict]:
    fallbacks = {
        1: [
            {"id": "app_purpose", "text": "What problem does your application solve?", "why": "Defines core architecture needs", "type": "text", "placeholder": "e.g., connects buyers and sellers", "options": [], "required": False},
            {"id": "target_users", "text": "Who will use this application?", "why": "Affects access patterns and security model", "type": "text", "placeholder": "e.g., customers, employees, developers", "options": [], "required": False},
        ],
        2: [
            {"id": "realtime", "text": "Do users need to see updates instantly without refreshing?", "why": "Determines if event-driven/WebSocket architecture is needed", "type": "boolean", "placeholder": "", "options": ["yes", "no"], "required": False},
        ],
        3: [
            {"id": "internet_access", "text": "Will this app be reachable from the internet?", "why": "Determines public vs private network topology", "type": "select", "placeholder": "", "options": ["Yes, public", "Internal only", "Both"], "required": False},
        ],
        4: [
            {"id": "users_count", "text": "How many people will use it at the same time at peak?", "why": "Determines compute and database sizing", "type": "text", "placeholder": "e.g., 100, 5000, 1 million", "options": [], "required": False},
        ],
        5: [
            {"id": "downtime_tolerance", "text": "If the app goes down, how long can your business tolerate the outage?", "why": "Maps to RTO and multi-AZ requirements", "type": "select", "placeholder": "", "options": ["Hours", "30 minutes", "Minutes", "Cannot tolerate"], "required": False},
        ],
        6: [
            {"id": "sensitive_data", "text": "Will your app store personal information, health data, or payment details?", "why": "Drives encryption, compliance, and access control requirements", "type": "multiselect", "placeholder": "", "options": ["Personal info (PII)", "Health data", "Payment data", "None"], "required": False},
        ],
        7: [
            {"id": "monthly_budget", "text": "What is your monthly infrastructure budget range?", "why": "Determines instance types, redundancy levels, and service tiers", "type": "select", "placeholder": "", "options": ["<$100", "$100-$500", "$500-$2000", "$2000-$10000", ">$10000"], "required": False},
        ],
    }
    return fallbacks.get(block, [{"id": "open", "text": "Any additional details?", "why": "More context improves architecture accuracy", "type": "text", "placeholder": "", "options": [], "required": False}])
