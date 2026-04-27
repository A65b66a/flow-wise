from backend.agents.base import BaseAgent
from backend.llm.claude_client import ClaudeClient

_SYSTEM = """You are a cloud architecture consultant. Based on scope analysis, determine the best interaction mode.

Modes:
- AUTO: User is non-technical or wants quick results with minimal questions. Few technical terms in description. Wants fast output.
- GUIDED: User has domain knowledge, comfortable answering structured questions about their business needs.
- EXPERT: User explicitly mentions infra terms (CIDR, VPC, replicas, sharding, SLA), wants full control.

Return ONLY a valid JSON object:
{
  "recommended_mode": "AUTO|GUIDED|EXPERT",
  "reasoning": "1-2 sentence explanation visible to user",
  "confidence": 0.0,
  "mode_signals": {
    "auto_score": 0.0,
    "guided_score": 0.0,
    "expert_score": 0.0
  }
}

Score each from 0.0-1.0. Scores should sum to ~1.0."""


class ModeSelectionAgent(BaseAgent):
    def __init__(self, client: ClaudeClient) -> None:
        super().__init__(client)

    async def run(self, user_input: str, scope: dict) -> dict:
        context = (
            f"User Input: {user_input}\n"
            f"App Type: {scope.get('app_type')}\n"
            f"Stack: {scope.get('stack')}\n"
            f"Scale Hint: {scope.get('scale_hint')}\n"
            f"Domain: {scope.get('domain')}\n"
            f"Reasoning: {scope.get('reasoning')}\n"
            f"Confidence Score: {scope.get('confidence_score')}"
        )
        raw = await self.client.generate_json(
            system_prompt=_SYSTEM,
            user_message=f"Determine the best interaction mode:\n\n{context}",
        )
        scores = raw.get("mode_signals", {})
        return {
            "recommended_mode": raw.get("recommended_mode", "GUIDED"),
            "reasoning": raw.get("reasoning", ""),
            "confidence": float(raw.get("confidence", 0.7)),
            "mode_signals": {
                "auto_score": float(scores.get("auto_score", 0.33)),
                "guided_score": float(scores.get("guided_score", 0.34)),
                "expert_score": float(scores.get("expert_score", 0.33)),
            },
        }
