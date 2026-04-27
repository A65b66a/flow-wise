from anthropic import AsyncAnthropic
from backend.config import CLAUDE_API_KEY, CLAUDE_MODEL
from backend.utils.json_utils import extract_json


class ClaudeClient:
    def __init__(self) -> None:
        if not CLAUDE_API_KEY:
            raise RuntimeError(
                "CLAUDE_API_KEY is not set. Add it to your .env file before starting the server."
            )
        self._client = AsyncAnthropic(api_key=CLAUDE_API_KEY)

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        temperature: float = 1.0,
    ) -> str:
        message = await self._client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
    ) -> dict:
        full_prompt = (
            user_message
            + "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no explanation, no code fences."
        )
        # temperature=0 for deterministic, consistent structured output
        text = await self.generate(system_prompt, full_prompt, max_tokens, temperature=0)
        return extract_json(text)
