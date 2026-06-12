"""Provider-agnostic LLM client.

AutoPilot can talk to either Anthropic Claude or OpenAI ChatGPT. Both the
Kubernetes diagnoser and the Jenkins analyser go through this single module so
that switching providers is a one-line config change (LLM_PROVIDER) rather than
a code change.

The active provider and model are resolved from ``runtime_config`` on every
call, which means they can be flipped at runtime via the /settings/config
endpoint without restarting the agent. The underlying SDK clients are created
lazily and cached, so unused providers are never imported or instantiated.
"""

from __future__ import annotations

import structlog

from config.settings import runtime_config, settings

logger = structlog.get_logger(__name__)

ANTHROPIC = "anthropic"
OPENAI = "openai"
SUPPORTED_PROVIDERS = (ANTHROPIC, OPENAI)


class LLMConfigError(RuntimeError):
    """Raised when the selected provider is missing required configuration."""


class LLMClient:
    """Unified async chat client across Anthropic and OpenAI.

    Use :func:`get_llm_client` to obtain the shared singleton rather than
    constructing this directly.
    """

    def __init__(self) -> None:
        self._anthropic = None  # anthropic.AsyncAnthropic
        self._openai = None  # openai.AsyncOpenAI

    # ------------------------------------------------------------------
    # Lazy SDK clients
    # ------------------------------------------------------------------
    def _get_anthropic(self):
        if self._anthropic is None:
            import anthropic

            if not settings.ANTHROPIC_API_KEY:
                raise LLMConfigError(
                    "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set"
                )
            self._anthropic = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._anthropic

    def _get_openai(self):
        if self._openai is None:
            from openai import AsyncOpenAI

            if not settings.OPENAI_API_KEY:
                raise LLMConfigError(
                    "LLM_PROVIDER=openai but OPENAI_API_KEY is not set"
                )
            self._openai = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL or None,
            )
        return self._openai

    # ------------------------------------------------------------------
    # Active provider / model (resolved per-call from runtime config)
    # ------------------------------------------------------------------
    @staticmethod
    def active_provider() -> str:
        provider = str(
            runtime_config.get("LLM_PROVIDER", settings.LLM_PROVIDER)
        ).strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise LLMConfigError(
                f"Unknown LLM_PROVIDER '{provider}' (expected one of {SUPPORTED_PROVIDERS})"
            )
        return provider

    @staticmethod
    def active_model() -> str:
        if LLMClient.active_provider() == OPENAI:
            return str(runtime_config.get("OPENAI_MODEL", settings.OPENAI_MODEL))
        return str(runtime_config.get("CLAUDE_MODEL", settings.CLAUDE_MODEL))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        """Send a single-turn (system + user) request and return raw text.

        ``json_mode`` enables provider-native JSON enforcement where available
        (OpenAI's ``response_format``). Anthropic relies on the system prompt to
        request JSON, so the flag is a no-op there.
        """
        provider = self.active_provider()
        if provider == OPENAI:
            return await self._complete_openai(system, prompt, max_tokens, json_mode)
        return await self._complete_anthropic(system, prompt, max_tokens)

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------
    async def _complete_anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        client = self._get_anthropic()
        message = await client.messages.create(
            model=self.active_model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text if message.content else ""

    async def _complete_openai(
        self, system: str, prompt: str, max_tokens: int, json_mode: bool
    ) -> str:
        client = self._get_openai()
        kwargs: dict = {
            "model": self.active_model(),
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        if json_mode:
            # Requires the word "json" to appear in the prompt; our system
            # prompts already instruct the model to return JSON only.
            kwargs["response_format"] = {"type": "json_object"}
        completion = await client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content or ""


# Shared singleton -----------------------------------------------------------
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return the process-wide shared :class:`LLMClient`."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
        logger.info(
            "LLM client initialised",
            provider=LLMClient.active_provider(),
            model=LLMClient.active_model(),
        )
    return _llm_client
