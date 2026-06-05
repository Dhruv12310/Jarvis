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
# Home-dir paths leak the OS username on a network-reachable surface: C:\Users\<name>\,
# C:/Users/<name>/, /home/<name>/, /Users/<name>/  ->  collapse the username to ***. Both Windows
# separators are matched because pathlib emits backslashes that some surfaces normalize to slashes.
# Deliberately NOT case-insensitive: real homes are capitalized `/Users/` (macOS) or lowercase
# `/home/` (Linux), so matching case-sensitively avoids mangling an unrelated URL path such as a
# REST `/users/<id>` segment. Only the Windows drive form tolerates either case (C:\Users).
_HOME_PATH = re.compile(r"((?:[A-Za-z]:[\\/][Uu]sers[\\/]|/home/|/Users/))[^\\/\s\"']+")


def redact(text: str) -> str:
    text = _SECRET_PARAM.sub(r"\1=***", text)
    text = _SECRET_FIELD.sub(r"\1***", text)
    return _HOME_PATH.sub(r"\1***", text)
