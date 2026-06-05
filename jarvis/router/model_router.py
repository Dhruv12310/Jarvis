"""Model Router: the single seam that may escalate to a cloud LLM (Tier 2).

Architecture invariant (Core): "Only the Model Router (after PII stripping) ... may cross to the
cloud." Everything else stays local. So this module - and only this module (the boundary test pins
it) - imports the Anthropic SDK, and it ALWAYS runs `redact()` over the outbound text first as
defense in depth. Cloud use is the controlled exception: a missing key is not an error, it just
means escalation is unavailable (`available` is False) and callers fall back to the local path.

The Anthropic client is injectable so tests run fully offline; in production it is built lazily from
the key, so importing this module never requires the SDK to be installed or a key to be present.
"""

from __future__ import annotations

from jarvis.config import config
from jarvis.redact import redact

_MAX_TOKENS = 2000


class CloudUnavailable(RuntimeError):
    """Raised when a cloud escalation is requested but no API key / client is configured."""


class ModelRouter:
    def __init__(
        self, *, api_key: str | None = None, model: str | None = None, client=None
    ) -> None:
        self._api_key = api_key if api_key is not None else config.anthropic_api_key
        self._model = model or config.cloud_model
        self._client = client  # injected fake in tests; built lazily from the key otherwise

    @property
    def available(self) -> bool:
        """True when a cloud call can be made (a key is set, or a client was injected)."""
        return bool(self._api_key) or self._client is not None

    def deepdive(self, data_block: str, instruction: str) -> str:
        """Escalate: synthesize prose from `instruction` over `data_block` using the cloud model.
        The block is REDACTED before it leaves the machine (defense in depth - the caller is meant
        to pass public data already). Raises CloudUnavailable when no key/client is configured."""
        if not self.available:
            raise CloudUnavailable("no ANTHROPIC_API_KEY configured")
        safe_block = redact(data_block)
        client = self._client or self._build_client()
        message = client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": f"{instruction}\n\nDATA:\n{safe_block}"}],
        )
        return _text_of(message)

    def _build_client(self):
        import anthropic  # lazy: only needed when a real escalation actually fires

        return anthropic.Anthropic(api_key=self._api_key)


def _text_of(message) -> str:
    """Join the text blocks of an Anthropic Message into one string (robust to the block shape)."""
    blocks = getattr(message, "content", None) or []
    texts = [getattr(block, "text", "") or "" for block in blocks]
    return "\n".join(text for text in texts if text).strip()
