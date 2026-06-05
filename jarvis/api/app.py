"""The FastAPI app - the ONLY module (with server.py) that imports the web toolkit.

Thin by design: each route calls one JarvisService capability and returns its structured result as
JSON (via to_jsonable). No capability logic lives here - the facade still owns it and still emits
one signal per call (source="web"). Exceptions are caught and REDACTED before they reach the client,
the same trust rule the CLI/Flet surfaces follow (an error string must never leak a secret). When a
built frontend exists at frontend/dist it is served at / so `python -m jarvis serve` opens the app.
"""

from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jarvis.api.serialize import to_jsonable
from jarvis.redact import redact
from jarvis.service import JarvisService

# jarvis/api/app.py -> parents: [0]=api, [1]=jarvis, [2]=repo root. The web build lands here.
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class _AskBody(BaseModel):
    text: str


class _GoalBody(BaseModel):
    text: str


class _FinanceBody(BaseModel):
    question: str


class _WatchBody(BaseModel):
    kind: str
    value: str


class _FileBody(BaseModel):
    # Caps bound the request: a 1 MB write ceiling prevents a trivial disk-fill / event-loop-stall
    # DoS (the route runs sync write_text on the loop thread), and a path-length cap rejects abuse.
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field("", max_length=1_000_000)
    overwrite: bool = False


class _FolderBody(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class _FsForbidden(Exception):
    """Raised when a filesystem op is attempted off-loopback with no token configured."""


def create_app(
    service: JarvisService, *, token: str | None = None, loopback: bool = True
) -> FastAPI:
    """Build the app over an injected service (a fake in tests; the real facade in serve).

    When `token` is set, every /api data route (all but /api/health) requires an `X-Jarvis-Token`
    header matching it. This is the gate for off-localhost (Tailscale) binds: it authenticates the
    caller AND defeats browser CSRF / DNS-rebinding, because a custom header forces a CORS preflight
    the server never grants cross-origin. Default (no token) keeps the localhost-only behavior.
    """
    app = FastAPI(title="Jarvis", docs_url="/api/docs", openapi_url="/api/openapi.json")

    if token:

        @app.middleware("http")
        async def _require_token(request: Request, call_next):
            path = request.url.path
            if path.startswith("/api") and path != "/api/health":
                provided = request.headers.get("x-jarvis-token", "")
                if not hmac.compare_digest(provided, token):  # constant-time compare
                    return JSONResponse(status_code=401, content={"error": "unauthorized"})
            return await call_next(request)

    # fs guard: honor "anywhere on disk" while protecting an off-loopback (Tailscale) bind. The
    # token middleware above gates EVERY /api route when a token is set, and server.py refuses to
    # start off-loopback without one - this is defense in depth on top. Off-loopback with no token
    # -> ALL filesystem routes (read + write) refuse with 503 (a full-disk lister is a recon
    # primitive too, not just writes). Localhost stays fully open - the user's full-reach choice.
    _fs_open = loopback or token is not None

    def _guard_fs() -> None:
        if not _fs_open:
            raise _FsForbidden()

    def _redact_path(result: dict) -> dict:
        # Echoed result carries the resolved absolute path; scrub the home-dir username before it
        # leaves the box (an exposed surface should not leak the OS account name).
        return {**result, "path": redact(result["path"])} if "path" in result else result

    # --- redacted error handling: no raw traceback or secret ever reaches the client ---------
    def _error(status: int, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": redact(str(exc))})

    @app.exception_handler(ValueError)
    async def _bad_request(_request: Request, exc: ValueError) -> JSONResponse:
        return _error(400, exc)  # e.g. add_watch / set_budget rejecting bad input

    @app.exception_handler(LookupError)
    async def _not_found(_request: Request, exc: LookupError) -> JSONResponse:
        return _error(404, exc)  # e.g. complete_goal on a missing id

    @app.exception_handler(Exception)
    async def _server_error(_request: Request, exc: Exception) -> JSONResponse:
        return _error(500, exc)  # backend down (e.g. Ollama) -> redacted 500, never a traceback

    @app.exception_handler(_FsForbidden)
    async def _fs_forbidden(_request: Request, _exc: _FsForbidden) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "file operations are disabled on a non-loopback bind; "
                "set JARVIS_API_TOKEN to enable them"
            },
        )

    # --- capabilities (one route per JarvisService method; the facade emits the signal) ------
    # Handlers are async ON PURPOSE: FastAPI then runs them on the event-loop thread instead of a
    # worker-thread pool, so every JarvisService/SQLite call happens on the same thread the store
    # was created on (serve() builds it before uvicorn.run on this thread). Sync `def` routes would
    # be offloaded to arbitrary pool threads -> "SQLite objects created in a thread can only be used
    # in that same thread." Single-user local cockpit, so serializing on the loop is fine.
    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "name": "jarvis", "source": "web"}

    @app.get("/api/briefing")
    async def briefing() -> dict:
        return {"text": service.briefing()}

    @app.post("/api/ask")
    async def ask(body: _AskBody) -> dict:
        return to_jsonable(service.ask(body.text))

    @app.get("/api/agenda")
    async def agenda() -> dict:
        return to_jsonable(service.agenda())

    @app.post("/api/finance/ask")
    async def finance_ask(body: _FinanceBody) -> dict:
        return {"text": service.finance_answer(body.question)}

    @app.get("/api/finance/budgets")
    async def budgets() -> dict:
        return {"budgets": to_jsonable(service.budget_status())}

    @app.get("/api/finance/accounts")
    async def accounts() -> dict:
        return {"accounts": to_jsonable(service.accounts())}

    @app.get("/api/goals")
    async def goals() -> dict:
        return {"goals": to_jsonable(service.list_goals())}

    @app.post("/api/goals")
    async def add_goal(body: _GoalBody) -> dict:
        return to_jsonable(service.add_goal(body.text))

    @app.post("/api/goals/{goal_id}/complete")
    async def complete_goal(goal_id: int) -> dict:
        return to_jsonable(service.complete_goal(goal_id))

    @app.get("/api/watchlist")
    async def watchlist() -> dict:
        return {"watchlist": to_jsonable(service.watchlist())}

    @app.get("/api/quotes")
    async def quotes(symbols: str | None = None) -> dict:
        # Default (no param) = the watched symbols; ?symbols=NVDA,AMD = an ad-hoc grid. Pure read.
        requested = [s for s in symbols.split(",") if s.strip()] if symbols else None
        return {"quotes": to_jsonable(service.quotes(requested))}

    @app.get("/api/symbol-search")
    async def symbol_search(q: str = "") -> dict:
        # Resolve a typed company name/ticker to candidate symbols ("track any company").
        return {"matches": to_jsonable(service.symbol_search(q))}

    @app.get("/api/news")
    async def news(q: str | None = None) -> dict:
        # World news for the News view + globe (GDELT keyless + GNews). Pure read; emits no signal.
        return {"items": to_jsonable(service.news(q))}

    @app.get("/api/company/{symbol}")
    async def company(symbol: str) -> dict:
        # Deterministic company depth (fundamentals/financials/analyst/news). Pure read.
        return to_jsonable(service.company(symbol))

    @app.post("/api/company/{symbol}/deepdive")
    async def company_deepdive(symbol: str) -> dict:
        # Tier-2 cloud escalation (opt-in): analyst synthesis over the deterministic view. Returns
        # {report, note, escalated}; disabled gracefully (report=None) when no ANTHROPIC_API_KEY.
        return to_jsonable(service.company_deepdive(symbol))

    @app.post("/api/watch")
    async def add_watch(body: _WatchBody) -> dict:
        return to_jsonable(service.add_watch(body.kind, body.value))

    @app.post("/api/watch/remove")
    async def remove_watch(body: _WatchBody) -> dict:
        service.remove_watch(body.kind, body.value)
        return {"ok": True}

    @app.get("/api/suggestions")
    async def suggestions() -> dict:
        return {"suggestions": to_jsonable(service.suggestions())}

    @app.get("/api/goal-feed")
    async def goal_feed() -> dict:
        # The PULL view: per active goal, deterministic relevant public info with a WHY.
        return {"feed": to_jsonable(service.goal_feed())}

    # --- file operations (cockpit shortcut bar): full-disk reach, off-loopback guard above ----
    @app.get("/api/fs/list")
    async def fs_list(path: str | None = None) -> dict:
        _guard_fs()
        return _redact_path(service.list_dir(path))

    @app.post("/api/fs/file")
    async def fs_file(body: _FileBody) -> dict:
        _guard_fs()
        return _redact_path(service.create_file(body.path, body.content, overwrite=body.overwrite))

    @app.post("/api/fs/folder")
    async def fs_folder(body: _FolderBody) -> dict:
        _guard_fs()
        return _redact_path(service.create_folder(body.path))

    # --- serve the built React cockpit (added LAST so it never shadows /api routes) ----------
    if _FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")

    return app
