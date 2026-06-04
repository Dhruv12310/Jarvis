"""Redact secrets from text before it reaches a user surface (terminal, GUI card, printed error).

Shared by every front-end so an exception string can never leak an API key, whichever surface
renders it. Defense in depth: the keyed connectors return empty on a non-200 rather than raising,
but a future change must not leak a key.
"""

from __future__ import annotations

import re

# URL query form: token=... / apikey=...
_SECRET_PARAM = re.compile(r"(token|apikey)=[^&\s]+", re.IGNORECASE)
# JSON/assignment form for the finance + auth secrets: "secret": "...", access_token=..., etc.
_SECRET_FIELD = re.compile(
    r'("?(?:secret|access_token|client_id|client_secret|api_key)"?\s*[:=]\s*"?)[^"\s,}]+',
    re.IGNORECASE,
)


def redact(text: str) -> str:
    text = _SECRET_PARAM.sub(r"\1=***", text)
    return _SECRET_FIELD.sub(r"\1***", text)
