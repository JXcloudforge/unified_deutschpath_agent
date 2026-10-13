import os
from typing import Protocol

import httpx
import app.config  # noqa: F401 - importing the configuration module loads project .env once.

class LLMClient(Protocol):
    def answer(self, prompt: str) -> str: ...


class FakeLLM:
    """Offline test provider; deliberately exposes its received prompt."""
    def __init__(self, response: str = "Offline Stage 2 response") -> None:
        self.response, self.last_prompt = response, ""

    def answer(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


class DeepSeekLLM:
    """Small OpenAI-compatible adapter derived from the 01_agent provider boundary."""
    def __init__(self, api_key: str, *, base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat", timeout: float = 60.0) -> None:
        self.api_key, self.base_url, self.model = api_key, base_url.rstrip("/"), model
        self.client = httpx.Client(timeout=timeout)

    def answer(self, prompt: str) -> str:
        response = self.client.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "messages": [{"role": "system", "content": "You are a helpful German-learning assistant."}, {"role": "user", "content": prompt}]})
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM returned an empty answer")
        return content.strip()


def build_llm() -> LLMClient:
    """Offline-safe default; real DeepSeek is enabled only with an API key."""
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    return DeepSeekLLM(key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"), model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat")) if key else FakeLLM("AI provider is not configured. File parsing, RAG retrieval, and prompt construction are available offline.")
