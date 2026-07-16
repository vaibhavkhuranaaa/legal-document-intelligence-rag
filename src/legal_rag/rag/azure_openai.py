"""Thin wrapper around the Azure OpenAI data plane (embeddings + chat).

Mirrors the ingestion layer's `client.py` pattern: the SDK client is
injectable for tests, configuration arrives via settings (ADR-0008), and
callers never touch the `openai` SDK response shapes beyond this module.
"""

import time
from collections.abc import Callable

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import APIConnectionError, APITimeoutError, AzureOpenAI, RateLimitError

from legal_rag.rag.config import RagSettings

# Eight legal passages remain comfortably below the deployment's per-request
# token budget. Larger batches were an unverified response to malformed SEC
# payloads and are deliberately not part of the release path.
_EMBED_BATCH_SIZE = 8
_MAX_RATE_LIMIT_RETRIES = 5
_RATE_LIMIT_WAIT_SECONDS = 30.0
_CONNECTION_RETRY_WAIT_SECONDS = 5.0
_REQUEST_TIMEOUT_SECONDS = 60.0


def _rate_limit_wait_seconds(error: RateLimitError) -> float:
    """Prefer Azure's server-provided retry window over a guessed delay."""
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    retry_after_ms = headers.get("retry-after-ms")
    if retry_after_ms:
        try:
            return max(1.0, float(retry_after_ms) / 1000)
        except ValueError:
            pass
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            pass
    return _RATE_LIMIT_WAIT_SECONDS


def _connection_retry_wait_seconds(attempt: int) -> float:
    """Bound retry delay for a transient transport disconnect."""
    return min(_RATE_LIMIT_WAIT_SECONDS, _CONNECTION_RETRY_WAIT_SECONDS * (2**attempt))


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
                timeout=_REQUEST_TIMEOUT_SECONDS,
                max_retries=0,
            )
        else:
            if settings.azure_openai_api_key is None:
                raise RuntimeError("API-key authentication was selected without an API key")
            self._sdk_client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key.get_secret_value(),
                api_version=settings.azure_openai_api_version,
                timeout=_REQUEST_TIMEOUT_SECONDS,
                max_retries=0,
            )

    def embed(
        self,
        texts: list[str],
        *,
        initial_vectors: list[list[float]] | None = None,
        on_batch_complete: Callable[[list[list[float]]], None] | None = None,
    ) -> list[list[float]]:
        """Embed a batch of texts, preserving input order.

        Retries rate limits using Azure's window and transient connection
        drops with bounded backoff. A corpus release can run long enough for
        either condition; neither should discard completed prior batches.
        """
        vectors = list(initial_vectors or [])
        if len(vectors) > len(texts):
            raise ValueError("initial_vectors cannot be longer than texts")

        for start in range(len(vectors), len(texts), _EMBED_BATCH_SIZE):
            batch = texts[start : start + _EMBED_BATCH_SIZE]
            for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
                try:
                    response = self._sdk_client.embeddings.create(
                        model=self._settings.azure_openai_embedding_deployment,
                        input=batch,
                    )
                    break
                except RateLimitError as error:
                    if attempt == _MAX_RATE_LIMIT_RETRIES:
                        raise
                    time.sleep(_rate_limit_wait_seconds(error))
                except (APIConnectionError, APITimeoutError):
                    if attempt == _MAX_RATE_LIMIT_RETRIES:
                        raise
                    time.sleep(_connection_retry_wait_seconds(attempt))
            # API may return out of input order; sort by index to be safe.
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)
            if on_batch_complete is not None:
                on_batch_complete(vectors)
        return vectors

    def complete(
        self, *, system: str, user: str, max_completion_tokens: int | None = None
    ) -> str:
        """Run one chat completion and return the assistant text.

        gpt-5-mini is a reasoning model: it consumes hidden reasoning tokens
        from the same completion budget (observed live: 64 reasoning tokens
        for a one-word answer), so `max_completion_tokens` must be generous.
        Temperature is deliberately not set — reasoning deployments reject it.
        """
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            try:
                response = self._sdk_client.chat.completions.create(
                    model=self._settings.azure_openai_chat_deployment,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_completion_tokens=(
                        max_completion_tokens
                        if max_completion_tokens is not None
                        else self._settings.answer_max_completion_tokens
                    ),
                )
                break
            except RateLimitError as error:
                if attempt == _MAX_RATE_LIMIT_RETRIES:
                    raise
                time.sleep(_rate_limit_wait_seconds(error))
            except (APIConnectionError, APITimeoutError):
                if attempt == _MAX_RATE_LIMIT_RETRIES:
                    raise
                time.sleep(_connection_retry_wait_seconds(attempt))
        return response.choices[0].message.content or ""
