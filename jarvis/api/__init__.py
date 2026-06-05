"""HTTP API seam: a thin FastAPI wrapper over JarvisService (the web front-end's transport).

This package is to the web cockpit what jarvis/ui is to the Flet GUI: the ONLY place the web
toolkit (fastapi/uvicorn) is imported, kept behind this seam so the front-end stays swappable and
thin. It adds NO capability logic - every route calls a JarvisService method and serializes the
structured result to JSON. Signal capture still happens inside the facade (source="web").
"""

from __future__ import annotations

from jarvis.api.app import create_app
from jarvis.api.server import serve

__all__ = ["create_app", "serve"]
