"""The web API seam: each route calls one JarvisService method and serializes its result to JSON.

Driven by a faked service (the same pattern as the Flet controller tests) through FastAPI's
TestClient - no real LLM, store, or network. Covers serialization of the awkward types (datetime,
Decimal, nested dataclasses) and the redaction trust rule (an error must never leak a secret).
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from jarvis.api.app import create_app
from jarvis.calendar.client import CalendarEvent
from jarvis.finance.transaction import Account, BudgetStatus
from jarvis.results import (
    AgendaResult,
    AskResult,
    CompanyNews,
    CompanyView,
    GoalFeed,
    GoalFeedItem,
    NewsItem,
    Quote,
    SymbolMatch,
)
from jarvis.stores.structured import Goal, Suggestion, Watch


class _FakeService:
    """Returns the real value objects the facade returns, so we exercise actual serialization."""

    def __init__(self):
        self.asked: list[str] = []
        self.added_goals: list[str] = []
        self.completed: list[int] = []
        self.added_watch: list[tuple[str, str]] = []
        self.removed_watch: list[tuple[str, str]] = []
        self.quotes_args: object = "unset"
        self.searched_symbol: str | None = None
        self.files: list[tuple[str, str, bool]] = []
        self.folders: list[str] = []

    def briefing(self) -> str:
        return "today: markets up, 2 events"

    def ask(self, text: str) -> AskResult:
        self.asked.append(text)
        return AskResult(text="the answer", grounded=True, cached=True)

    def agenda(self) -> AgendaResult:
        event = CalendarEvent(
            id="e1",
            summary="Standup",
            start=datetime(2026, 6, 4, 9, 30, tzinfo=UTC),
            end=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
            location="Zoom",
            all_day=False,
        )
        return AgendaResult(events=[event], connected=True)

    def finance_answer(self, question: str) -> str:
        self.asked.append(question)
        return "You spent $42.50 this month."

    def budget_status(self) -> list[BudgetStatus]:
        return [
            BudgetStatus(
                category="dining",
                limit=Decimal("200.00"),
                actual=Decimal("250.00"),
                remaining=Decimal("-50.00"),
                over=True,
            )
        ]

    def accounts(self) -> list[Account]:
        return [Account(id="a1", name="Checking", type="checking", balance=Decimal("1234.56"))]

    def list_goals(self) -> list[Goal]:
        return [
            Goal(
                id=1,
                description="learn rust",
                status="active",
                progress=0.0,
                priority="medium",
                deadline=None,
                created_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
            )
        ]

    def add_goal(self, text: str) -> Goal:
        self.added_goals.append(text)
        return Goal(
            id=7,
            description=text,
            status="active",
            progress=0.0,
            priority="medium",
            deadline=None,
            created_at=datetime(2026, 6, 4, 8, 0, tzinfo=UTC),
        )

    def complete_goal(self, goal_id: int) -> Goal:
        self.completed.append(goal_id)
        return Goal(
            id=goal_id,
            description="learn rust",
            status="done",
            progress=1.0,
            priority="medium",
            deadline=None,
            created_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        )

    def watchlist(self) -> list[Watch]:
        return [Watch(kind="symbol", value="NVDA")]

    def add_watch(self, kind: str, value: str) -> Watch:
        if kind not in ("symbol", "topic"):
            raise ValueError("watch kind must be 'symbol' or 'topic'")
        self.added_watch.append((kind, value))
        return Watch(kind=kind, value=value.upper() if kind == "symbol" else value)

    def remove_watch(self, kind: str, value: str) -> None:
        self.removed_watch.append((kind, value))

    def quotes(self, symbols=None):
        self.quotes_args = symbols
        return [Quote(symbol="NVDA", price=120.0, change=2.93, change_pct=2.5, prev_close=117.07)]

    def symbol_search(self, q):
        self.searched_symbol = q
        return [SymbolMatch(symbol="AAPL", description="Apple Inc")]

    def company(self, query):
        self.company_query = query
        return CompanyView(
            symbol="AAPL",
            name="Apple Inc",
            industry="Technology",
            exchange="NASDAQ",
            market_cap="$4.58T",
            metrics={"pe_ttm": 37.35, "net_margin_ttm": 27.15},
            recommendation="strong buy 12, buy 20, hold 8, sell 1, strong sell 0",
            news=[CompanyNews(title="Apple unveils new chip", source="Reuters", url="https://r/1")],
            sources=["Finnhub"],
        )

    def news(self, query=None):
        self.news_query = query
        return [
            NewsItem(
                title="Border talks resume",
                source="reuters.com",
                url="https://r/news1",
                country="United States",
                published="2026-06-04",
                image="https://img/1.jpg",
            ),
            NewsItem(title="No-country wire", source="ap.org", url="https://r/news2"),
        ]

    def goal_feed(self):
        return [
            GoalFeed(
                goal_id=1,
                goal="learn rust",
                items=[
                    GoalFeedItem(
                        title="Rust 2.0 released",
                        detail="big news",
                        why="relates to goal #1: learn rust (matched 'rust')",
                        source="news",
                        kind="news",
                        url="https://example.test/rust",
                    )
                ],
            )
        ]

    def list_dir(self, path=None):
        return {
            "path": path or "/home/<user>",
            "entries": [{"name": "docs", "kind": "folder"}, {"name": "a.txt", "kind": "file"}],
        }

    def create_file(self, path, content="", *, overwrite=False):
        if not path.strip():
            raise ValueError("path is required")
        self.files.append((path, content, overwrite))
        return {"path": path, "kind": "file", "created": True, "bytes": len(content.encode())}

    def create_folder(self, path):
        self.folders.append(path)
        return {"path": path, "kind": "folder", "created": True}

    def suggestions(self) -> list[Suggestion]:
        return [
            Suggestion(
                id="s1",
                created_at=datetime(2026, 6, 4, 8, 0, tzinfo=UTC),
                candidate_type="market_move",
                entity_key="AAPL",
                content="AAPL reports earnings tomorrow.",
                why="you watch AAPL; urgency 0.8",
                source_ids=["watch:AAPL"],
                topics=["AAPL", "earnings"],
                features={"goal": 0.0, "urgency": 0.8},
                score=1.4,
                surfaced=True,
                channel="feed",
            )
        ]


@pytest.fixture
def client():
    return TestClient(create_app(_FakeService()))


def test_health_reports_web_source(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "name": "jarvis", "source": "web"}


def test_briefing_returns_text(client):
    assert client.get("/api/briefing").json() == {"text": "today: markets up, 2 events"}


def test_ask_serializes_askresult_flags(client):
    body = client.post("/api/ask", json={"text": "what is up"}).json()
    assert body == {"text": "the answer", "grounded": True, "cached": True}


def test_agenda_serializes_nested_events_and_datetimes(client):
    body = client.get("/api/agenda").json()
    assert body["connected"] is True
    event = body["events"][0]
    assert event["summary"] == "Standup"
    assert event["start"] == "2026-06-04T09:30:00+00:00"  # tz-aware ISO, not a datetime object
    assert event["all_day"] is False


def test_finance_ask_returns_text(client):
    body = client.post("/api/finance/ask", json={"question": "how much this month"}).json()
    assert body == {"text": "You spent $42.50 this month."}


def test_budgets_serialize_decimals_as_strings(client):
    budget = client.get("/api/finance/budgets").json()["budgets"][0]
    assert budget["limit"] == "200.00"  # Decimal -> exact string, never a lossy float
    assert budget["remaining"] == "-50.00"
    assert budget["over"] is True


def test_accounts_serialize_decimal_balance(client):
    account = client.get("/api/finance/accounts").json()["accounts"][0]
    assert account["balance"] == "1234.56"


def test_goals_list_and_nullable_deadline(client):
    goal = client.get("/api/goals").json()["goals"][0]
    assert goal["description"] == "learn rust"
    assert goal["deadline"] is None
    assert goal["created_at"] == "2026-06-01T12:00:00+00:00"


def test_add_goal_passes_text_and_returns_goal(client):
    service = _FakeService()
    local = TestClient(create_app(service))
    body = local.post("/api/goals", json={"text": "ship the HUD"}).json()
    assert service.added_goals == ["ship the HUD"]
    assert body["id"] == 7 and body["status"] == "active"


def test_complete_goal_marks_done(client):
    body = client.post("/api/goals/3/complete").json()
    assert body["id"] == 3 and body["status"] == "done" and body["progress"] == 1.0


def test_watchlist_and_add_remove(client):
    listed = client.get("/api/watchlist").json()["watchlist"]
    assert listed[0] == {"kind": "symbol", "value": "NVDA"}
    added = client.post("/api/watch", json={"kind": "symbol", "value": "tsla"}).json()
    assert added == {"kind": "symbol", "value": "TSLA"}  # symbols upper-cased by the facade
    assert client.post("/api/watch/remove", json={"kind": "symbol", "value": "TSLA"}).json() == {
        "ok": True
    }


def test_bad_watch_kind_is_400(client):
    response = client.post("/api/watch", json={"kind": "bogus", "value": "x"})
    assert response.status_code == 400  # ValueError -> 400, not a 500 traceback


def test_suggestions_serialize_full_card(client):
    suggestion = client.get("/api/suggestions").json()["suggestions"][0]
    assert suggestion["content"] == "AAPL reports earnings tomorrow."
    assert suggestion["why"] == "you watch AAPL; urgency 0.8"
    assert suggestion["features"] == {"goal": 0.0, "urgency": 0.8}


def test_quotes_default_serializes_quote_grid(client):
    body = client.get("/api/quotes").json()
    assert body["quotes"][0] == {
        "symbol": "NVDA",
        "price": 120.0,
        "change": 2.93,
        "change_pct": 2.5,
        "prev_close": 117.07,
        "currency": "USD",
    }


def test_quotes_passes_symbols_query_param():
    service = _FakeService()
    local = TestClient(create_app(service))
    local.get("/api/quotes?symbols=NVDA,AMD")
    assert service.quotes_args == ["NVDA", "AMD"]  # comma list -> list


def test_quotes_default_has_no_symbols_filter():
    service = _FakeService()
    local = TestClient(create_app(service))
    local.get("/api/quotes")
    assert service.quotes_args is None  # None -> the facade uses the watchlist


def test_symbol_search_serializes_matches():
    service = _FakeService()
    local = TestClient(create_app(service))
    body = local.get("/api/symbol-search?q=apple").json()
    assert service.searched_symbol == "apple"
    assert body["matches"][0] == {"symbol": "AAPL", "description": "Apple Inc"}


def test_company_route_serializes_view_and_nested_news():
    service = _FakeService()
    local = TestClient(create_app(service))
    body = local.get("/api/company/AAPL").json()
    assert service.company_query == "AAPL"
    assert body["name"] == "Apple Inc" and body["market_cap"] == "$4.58T"
    assert body["metrics"]["pe_ttm"] == 37.35
    assert body["news"][0] == {
        "title": "Apple unveils new chip",
        "source": "Reuters",
        "url": "https://r/1",
    }


def test_news_route_serializes_items_and_passes_query():
    service = _FakeService()
    local = TestClient(create_app(service))
    body = local.get("/api/news?q=ukraine").json()
    assert service.news_query == "ukraine"
    assert body["items"][0]["country"] == "United States"
    assert body["items"][1]["country"] is None  # GNews-style item, no globe pin


def test_news_route_default_query_is_none():
    service = _FakeService()
    TestClient(create_app(service)).get("/api/news")
    assert service.news_query is None


def test_goal_feed_route_serializes_nested_items(client):
    body = client.get("/api/goal-feed").json()
    feed = body["feed"][0]
    assert feed["goal_id"] == 1 and feed["goal"] == "learn rust"
    item = feed["items"][0]
    assert item["source"] == "news"
    assert item["why"].startswith("relates to goal #1")


def test_goal_feed_route_is_token_gated():
    c = TestClient(create_app(_FakeService(), token="s3cret"))
    assert c.get("/api/goal-feed").status_code == 401
    assert c.get("/api/goal-feed", headers={"X-Jarvis-Token": "s3cret"}).status_code == 200


def test_no_token_means_routes_are_open():
    # Default (no token) keeps the localhost-only behavior - no auth on any route.
    client = TestClient(create_app(_FakeService()))
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/goals").status_code == 200


def test_token_gate_blocks_unauthenticated_data_routes():
    client = TestClient(create_app(_FakeService(), token="s3cret"))
    assert client.get("/api/goals").status_code == 401  # no header
    assert client.get("/api/goals", headers={"X-Jarvis-Token": "wrong"}).status_code == 401
    assert client.get("/api/goals", headers={"X-Jarvis-Token": "s3cret"}).status_code == 200


def test_token_gate_leaves_health_open():
    # /health must stay reachable so the SPA can check connectivity before it has the token.
    client = TestClient(create_app(_FakeService(), token="s3cret"))
    assert client.get("/api/health").status_code == 200


def test_token_gate_protects_post_routes():
    client = TestClient(create_app(_FakeService(), token="s3cret"))
    assert client.post("/api/goals", json={"text": "x"}).status_code == 401
    ok = client.post("/api/goals", json={"text": "x"}, headers={"X-Jarvis-Token": "s3cret"})
    assert ok.status_code == 200


def test_backend_failure_is_redacted_500_not_a_traceback():
    class _LeakyService:
        def briefing(self):
            raise RuntimeError("connect failed for https://x?token=SECRET123")

    client = TestClient(create_app(_LeakyService()), raise_server_exceptions=False)
    response = client.get("/api/briefing")
    assert response.status_code == 500
    body = response.json()
    assert "SECRET123" not in body["error"]
    assert "token=***" in body["error"]


def test_fs_list_returns_entries(client):
    body = client.get("/api/fs/list", params={"path": "/tmp"}).json()
    assert {"name": "docs", "kind": "folder"} in body["entries"]


def test_fs_create_file_passes_args():
    service = _FakeService()
    local = TestClient(create_app(service))
    body = local.post("/api/fs/file", json={"path": "/tmp/x.txt", "content": "hi"}).json()
    assert service.files == [("/tmp/x.txt", "hi", False)]
    assert body["created"] is True and body["kind"] == "file"


def test_fs_create_folder_passes_path():
    service = _FakeService()
    local = TestClient(create_app(service))
    local.post("/api/fs/folder", json={"path": "/tmp/newdir"})
    assert service.folders == ["/tmp/newdir"]


def test_fs_blank_path_is_400(client):
    assert client.post("/api/fs/file", json={"path": "   "}).status_code == 400


def test_fs_oversized_content_is_rejected(client):
    big = "x" * 1_000_001  # over the 1 MB write cap -> Pydantic 422 before any disk touch
    resp = client.post("/api/fs/file", json={"path": "/tmp/x.txt", "content": big})
    assert resp.status_code == 422


def test_fs_all_ops_refused_off_loopback_without_token():
    # No token + off-localhost: every fs route refuses - listing disk is a recon primitive too.
    client = TestClient(create_app(_FakeService(), loopback=False), raise_server_exceptions=False)
    assert client.post("/api/fs/file", json={"path": "/tmp/x.txt"}).status_code == 503
    assert client.post("/api/fs/folder", json={"path": "/tmp/d"}).status_code == 503
    assert client.get("/api/fs/list", params={"path": "/tmp"}).status_code == 503


def test_fs_allowed_off_loopback_with_token():
    client = TestClient(create_app(_FakeService(), token="s3cret", loopback=False))
    ok = client.post(
        "/api/fs/file", json={"path": "/tmp/x.txt"}, headers={"X-Jarvis-Token": "s3cret"}
    )
    assert ok.status_code == 200


def test_fs_open_on_loopback_without_token():
    client = TestClient(create_app(_FakeService()))  # loopback default True -> full reach, no token
    assert client.post("/api/fs/file", json={"path": "/tmp/x.txt"}).status_code == 200


def test_fs_echoed_path_redacts_home_username():
    class _LeakyFs(_FakeService):
        def create_folder(self, path):
            return {"path": "/home/dhruv/secretproj", "kind": "folder", "created": True}

    client = TestClient(create_app(_LeakyFs()))
    body = client.post("/api/fs/folder", json={"path": "x"}).json()
    assert "dhruv" not in body["path"] and "***" in body["path"]


def test_redact_scrubs_home_dir_username():
    from jarvis.redact import redact

    assert "dhruv" not in redact(r"could not write C:\Users\dhruv\x.txt")
    assert "dhruv" not in redact("could not write C:/Users/dhruv/x.txt")  # forward-slash form
    assert "alice" not in redact("PermissionError at /home/alice/secret")
    assert "token=***" in redact("connect failed for https://x?token=SECRET123")  # existing rule


def test_redact_preserves_lowercase_users_url_path():
    from jarvis.redact import redact

    # A REST `/users/<id>` URL path must NOT be scrubbed - only real home dirs (capital /Users/,
    # lowercase /home/, or a Windows drive) leak a username. Regression for over-redaction.
    assert redact("https://api.github.com/users/octocat/repos") == (
        "https://api.github.com/users/octocat/repos"
    )
    assert "dhruv" not in redact(r"could not write c:\users\dhruv\x.txt")  # Windows, either case
