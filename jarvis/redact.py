"""Redact secrets from text before it reaches a user surface (terminal, GUI card, printed error).

Shared by every front-end so an exception string can never leak an API key, whichever surface
renders it. Defense in depth: the keyed connectors return empty on a non-200 rather than raising,
but a future change must not leak a key.
"""

from __future__ import annotations

import re

_SECRET_PARAM = re.compile(r"(token|apikey)=[^&\s]+", re.IGNORECASE)


def redact(text: str) -> str:
    return _SECRET_PARAM.sub(r"\1=***", text)
