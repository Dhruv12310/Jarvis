"""JarvisService.company_deepdive(): Tier-2 escalation with graceful local fallback. Offline."""

from jarvis.connectors.base import ConnectorResult, Item, Source
from jarvis.results import CompanyView
from jarvis.service import JarvisService, _company_block


def _profile_items():
    return [
        Item(
            title="Apple Inc",
            detail="Technology; market cap $4.58T",
            url=None,
            extra={
                "kind": "profile",
                "symbol": "AAPL",
                "name": "Apple Inc",
                "industry": "Technology",
                "market_cap": "$4.58T",
            },
        ),
        Item(
            title="Financials",
            detail="P/E 37.4",
            url=None,
            extra={"kind": "financials", "symbol": "AAPL", "pe_ttm": 37.35},
        ),
    ]


class _FakeFundamentals:
    name = "fundamentals"
    description = "f"

    def __init__(self, items):
        self._items = items

    def fetch(self, query):
        return ConnectorResult(source=Source(name="Finnhub"), items=self._items, query=query)


class _Signals:
    def __init__(self):
        self.emitted = []

    def emit(self, kind, payload):
        self.emitted.append((kind, payload))


class _FakeRouter:
    def __init__(self, available=True, reply="DEEP DIVE"):
        self._available = available
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    @property
    def available(self):
        return self._available

    def deepdive(self, block, instruction):
        self.calls.append((block, instruction))
        return self.reply


def _service(items, router):
    return JarvisService(
        orchestrator=None,
        knowledge=None,
        store=None,
        memory=None,
        signals=_Signals(),
        source="test",
        connectors={"fundamentals": _FakeFundamentals(items)},
        model_router=router,
    )


def test_deepdive_escalates_and_returns_report():
    router = _FakeRouter(reply="full analyst report")
    svc = _service(_profile_items(), router)

    result = svc.company_deepdive("AAPL")

    assert result["escalated"] is True
    assert result["report"] == "full analyst report"
    assert result["note"] is None
    block, _instruction = router.calls[0]
    assert "Apple Inc" in block and "$4.58T" in block  # deterministic view fed to the cloud


def test_deepdive_disabled_without_router():
    svc = _service(_profile_items(), None)
    result = svc.company_deepdive("AAPL")
    assert result["escalated"] is False and result["report"] is None
    assert "ANTHROPIC_API_KEY" in result["note"]


def test_deepdive_disabled_when_router_unavailable():
    svc = _service(_profile_items(), _FakeRouter(available=False))
    result = svc.company_deepdive("AAPL")
    assert result["escalated"] is False and result["report"] is None


def test_deepdive_skips_cloud_when_no_company_data():
    router = _FakeRouter()
    svc = _service([], router)  # empty -> no name -> nothing to analyze
    result = svc.company_deepdive("ZZZZ")
    assert result["escalated"] is False and result["report"] is None
    assert router.calls == []  # no cloud tokens spent on an empty view


def test_deepdive_survives_cloud_failure():
    class _Boom(_FakeRouter):
        def deepdive(self, block, instruction):
            raise RuntimeError("anthropic 500")

    svc = _service(_profile_items(), _Boom())
    result = svc.company_deepdive("AAPL")
    assert result["escalated"] is False and result["report"] is None
    assert "failed" in result["note"].lower()


def test_deepdive_emits_one_signal():
    router = _FakeRouter()
    svc = _service(_profile_items(), router)
    svc._signals = _Signals()
    svc.company_deepdive("AAPL")
    kinds = [k for k, _ in svc._signals.emitted]
    assert kinds == ["company_deepdive"]
    assert svc._signals.emitted[0][1]["escalated"] is True


def test_company_block_is_public_text():
    view = CompanyView(
        symbol="AAPL",
        name="Apple Inc",
        industry="Technology",
        market_cap="$4.58T",
        metrics={"pe_ttm": 37.35},
        recommendation="strong buy 12",
    )
    block = _company_block(view)
    assert "Apple Inc (AAPL)" in block
    assert "pe_ttm: 37.35" in block
    assert "strong buy 12" in block
