"""Thin wrapper around the Azure OpenAI data plane (embeddings + chat).

Mirrors the ingestion layer's `client.py` pattern: the SDK client is
injectable for tests, configuration arrives via settings (ADR-0008), and
callers never touch the `openai` SDK response shapes beyond this module.
"""

import time

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI, RateLimitError

from legal_rag.rag.config import RagSettings

# The configured deployment's token-per-minute allowance is modest.  Eight
# legal passages remain comfortably below its per-request token budget while
# avoiding a retry loop on long, page-dense corpus releases.
_EMBED_BATCH_SIZE = 8
_MAX_RATE_LIMIT_RETRIES = 5
_RATE_LIMIT_WAIT_SECONDS = 30.0


class AzureOpenAIClient:
    def __init__(self, settings: RagSettings, *, sdk_client: AzureOpenAI | None = None) -> None:
        self._settings = settings
        if sdk_client is not None:
            self._sdk_client = sdk_client
        elif settings.azure_openai_auth_mode == "managed_identity":
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            )
            self._sdk_client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version=settings.azure_openai_api_version,
            )
        else:
            if settings.azure_openai_api_key is None:
                raise RuntimeError("API-key authentication was selected without an API key")
            self._sdk_client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key.get_secret_value(),
                api_version=settings.azure_openai_api_version,
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, preserving input order.

        Retries on 429 with a fixed wait: Azure OpenAI rate limits are
        per-minute token buckets, so waiting out the window is the correct
        (and Azure-documented) recovery.
        """
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[start : start + _EMBED_BATCH_SIZE]
            for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
                try:
                    response = self._sdk_client.embeddings.create(
                        model=self._settings.azure_openai_embedding_deployment,
                        input=batch,
                    )
                    break
                except RateLimitError:
                    if attempt == _MAX_RATE_LIMIT_RETRIES:
                        raise
                    time.sleep(_RATE_LIMIT_WAIT_SECONDS)
            # API may return out of input order; sort by index to be safe.
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
        return vectors

    def complete(self, *, system: str, user: str) -> str:
        """Run one chat completion and return the assistant text.

        gpt-5-mini is a reasoning model: it consumes hidden reasoning tokens
        from the same completion budget (observed live: 64 reasoning tokens
        for a one-word answer), so `max_completion_tokens` must be generous.
        Temperature is deliberately not set — reasoning deployments reject it.
        """
        response = self._sdk_client.chat.completions.create(
            model=self._settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=self._settings.answer_max_completion_tokens,
        )
        return response.choices[0].message.content or ""
