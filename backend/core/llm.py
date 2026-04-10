"""
LLM Client Abstraction Layer.

Supports OpenAI, Groq, and Ollama through a single unified interface.
All agents use this class — never call OpenAI/Groq directly.

To switch providers: change LLM_PROVIDER in .env. That's it.
"""
from typing import AsyncIterator
from .config import settings
from .logger import get_logger
from .retry import llm_retry

logger = get_logger(__name__)


class LLMClient:
    """
    Unified async LLM client.

    Methods:
        complete(messages) → str          — single response (used by agents for structured output)
        stream(messages)   → AsyncIter   — streaming response (used by chat UI via SSE)
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self._client = self._init_client()
        logger.info("LLM client ready", provider=self.provider, model=self.model)

    def _init_client(self):
        """Instantiate the correct async client based on provider."""
        if self.provider == "openai":
            from openai import AsyncOpenAI
            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "LLM_PROVIDER=openai but OPENAI_API_KEY is not set in .env"
                )
            return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        elif self.provider == "groq":
            from groq import AsyncGroq
            if not settings.GROQ_API_KEY:
                raise ValueError(
                    "LLM_PROVIDER=groq but GROQ_API_KEY is not set in .env\n"
                    "Get a free key at: https://console.groq.com"
                )
            return AsyncGroq(api_key=settings.GROQ_API_KEY)

        elif self.provider == "ollama":
            # Ollama exposes an OpenAI-compatible REST API at /v1
            from openai import AsyncOpenAI
            return AsyncOpenAI(
                base_url=f"{settings.OLLAMA_BASE_URL}/v1",
                api_key="ollama",  # Ollama ignores this, but the SDK requires it
            )

        raise ValueError(
            f"Unknown LLM_PROVIDER: '{self.provider}'. "
            "Supported values: openai | groq | ollama"
        )

    @property
    def model(self) -> str:
        """Active model name, driven by config."""
        return {
            "openai": settings.OPENAI_MODEL,
            "groq": settings.GROQ_MODEL,
            "ollama": settings.OLLAMA_MODEL,
        }[self.provider]

    @llm_retry
    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Non-streaming completion — returns a single string.
        Used by agents that need structured JSON output before continuing their workflow.

        Args:
            messages: OpenAI-format message list [{"role": "...", "content": "..."}]
            temperature: Higher = more creative, Lower = more deterministic
            max_tokens: Maximum response length

        Returns:
            The assistant's response as a plain string.
        """
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        logger.debug(
            "LLM complete",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )
        return content

    @llm_retry
    async def stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Streaming completion — yields text chunks as they arrive from the LLM.
        Used by the chat API endpoint to push Server-Sent Events to the frontend.

        Usage:
            async for chunk in llm_client.stream(messages):
                yield f"data: {chunk}\\n\\n"
        """
        stream_response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream_response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── Global singleton — import this everywhere ─────────────────────────────────
# Initialized once at startup; shared across all requests (thread-safe for async)
llm_client = LLMClient()
