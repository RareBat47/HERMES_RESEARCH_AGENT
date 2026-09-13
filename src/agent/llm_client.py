import json
from typing import Any, Dict, List, Optional
import httpx
from src.common.exceptions import AgentError
from src.common.logging import setup_logger
from src.config.settings import get_settings

logger = setup_logger("hermes.agent.llm")


class LLMClient:
    """Async OpenAI-compatible LLM client targeting agentrouter.org or any standard endpoint."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.LLM_BASE_URL.rstrip("/")
        self.api_key = self.settings.LLM_API_KEY
        self.default_model = self.settings.LLM_MODEL

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: int = 4000,
    ) -> str:
        """Call chat completion endpoint and return response content."""
        target_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"LLM API error ({res.status_code}): {res.text}")
                    raise AgentError(f"LLM API error ({res.status_code}): {res.text[:200]}")
        except Exception as e:
            logger.warning(f"LLM call to {self.base_url} failed: {e}")
            raise AgentError(f"LLM invocation failed: {e}") from e
