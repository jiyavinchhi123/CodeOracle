import json
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from app.config import Settings


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 4096) -> str:
        ...


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._timeout = float(settings.llm_timeout_seconds)

    async def complete(self, system: str, user: str, max_tokens: int = 4096) -> str:
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class HeuristicProvider(LLMProvider):
    """Rule-based fallback when no LLM API key is configured."""

    async def complete(self, system: str, user: str, max_tokens: int = 4096) -> str:
        return ""


def get_llm_provider(settings: Settings) -> tuple[LLMProvider, str]:
    if settings.llm_configured:
        return OpenAICompatibleProvider(settings), "llm"
    return HeuristicProvider(), "heuristic"


def extract_json_block(text: str) -> Optional[dict[str, Any]]:
    """Extract JSON object from LLM response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None
