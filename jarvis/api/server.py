"""Bootstrap for `python -m jarvis serve`: build the real facade and run the web cockpit.

Mirrors the Flet `launch(service)` lifecycle - it composes the same JarvisService (source="web")
via the shared cli.build_service, runs uvicorn, and closes the store on shutdown. Host/port/token
read from the environment here (a process-launch concern, like __main__ reading argv):

  JARVIS_API_HOST   defaults to 127.0.0.1 (localhost only). Set it to your Tailscale IP / 0.0.0.0 to
                    reach the cockpit from another device on the private mesh.
  JARVIS_API_PORT   defaults to 8765.
  JARVIS_API_TOKEN  optional shared secret. When set, every /api data route requires it (the SPA
                    picks it up once from http://<host>:<port>/?token=<token>). REQUIRED in practice
                    for any off-localhost bind - without it those routes are unauthenticated on the
                    network. Nothing private leaves the machine either way (no outbound push).
"""

from __future__ import annotations

import os

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def serve() -> int:
    import uvicorn

    from jarvis.api.app import create_app
    from jarvis.cli import build_service

    host = os.environ.get("JARVIS_API_HOST", "127.0.0.1")
    port = int(os.environ.get("JARVIS_API_PORT", "8765"))
    token = os.environ.get("JARVIS_API_TOKEN", "").strip() or None

    if host not in _LOOPBACK and token is None:
        # Refuse, don't warn: binding off-loopback with no token would leave EVERY /api route -
        # including file writes anywhere on disk - unauthenticated on the network. A mandatory
        # a mandatory token off-loopback makes the custom-header CSRF defense load-bearing.
        raise SystemExit(
            f"Refusing to bind off-loopback (host={host}) without JARVIS_API_TOKEN: it would "
            "leave every /api route - including file operations anywhere on disk - unauthenticated "
            f"on the network. Set JARVIS_API_TOKEN, then open it once at "
            f"http://{host}:{port}/?token=<your token>."
        )

    service, store = build_service(source="web")
    app = create_app(service, token=token, loopback=host in _LOOPBACK)
    print(f"Jarvis cockpit on http://{host}:{port}  (Ctrl+C to stop)")
    if token:
        print(f"Token auth ON. Open it once at: http://{host}:{port}/?token=<your token>")
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        store.close()
    return 0
