"""JarvisService.company(): deterministic assembly of fundamentals into a CompanyView. Offline."""

from jarvis.connectors.base import ConnectorResult, Item, Source
from jarvis.results import CompanyView
from jarvis.service import _assemble_company


class _FakeFundamentals:
    name = "fundamentals"
    description = "fundamentals"

    def __init__(self, items):
        self._items = items
        self.queried: list[str] = []

    def fetch(self, query):
        self.queried.append(query)
        return ConnectorResult(source=Source(name="Finnhub"), items=self._items, query=query)


def _items():
    return [
        Item(
            title="Apple Inc",
            detail="Technology; market cap $4.58T",
            url="https://www.apple.com/",
            extra={
                "kind": "profile",
                "symbol": "AAPL",
                "name": "Apple Inc",
                "industry": "Technology",
                "exchange": "NASDAQ",
                "ipo": "1980-12-12",
                "market_cap": "$4.58T",
                "weburl": "https://www.apple.com/",
            },
        ),
        Item(
            title="Financials",
            detail="P/E 37.4, net margin 27.1%",
            url=None,
            extra={
                "kind": "financials",
                "symbol": "AAPL",
                "pe_ttm": 37.35,
                "net_margin_ttm": 27.15,
            },
        ),
        Item(
            title="Analyst recommendation",
            detail="strong buy 12, buy 20, hold 8, sell 1, strong sell 0 (as of 2026-06-01)",
            url=None,
            extra={"kind": "recommendation", "symbol": "AAPL", "strongBuy": 12},
        ),
        Item(
            title="Apple unveils new chip",
            detail="Reuters",
            url="https://r/1",
            extra={"kind": "news", "symbol": "AAPL", "source": "Reuters"},
        ),
    ]


def _service(items):
    # Build a JarvisService with only the pieces company() touches; the rest stays unused.
    from jarvis.service import JarvisService

    class _Signals:
        def __init__(self):
            self.emitted = []

        def emit(self, kind, payload):
            self.emitted.append((kind, payload))

    connector = _FakeFundamentals(items)
    signals = _Signals()
    svc = JarvisService(
        orchestrator=None,
        knowledge=None,
        store=None,
        memory=None,
        signals=signals,
        source="test",
        connectors={"fundamentals": connector},
    )
    return svc, connector, signals


def test_assemble_company_folds_all_facets():
    view = _assemble_company("AAPL", _items())

    assert isinstance(view, CompanyView)
    assert view.name == "Apple Inc" and view.symbol == "AAPL"
    assert view.industry == "Technology" and view.market_cap == "$4.58T"
    assert view.metrics["pe_ttm"] == 37.35
    assert "kind" not in view.metrics and "symbol" not in view.metrics  # stripped
    assert view.recommendation.startswith("strong buy 12")
    assert [n.title for n in view.news] == ["Apple unveils new chip"]
    assert view.sources == ["Finnhub"]
    assert view.note is None


def test_no_items_yields_explanatory_note():
    view = _assemble_company("ZZZZ", [])
    assert view.symbol == "ZZZZ" and view.name is None
    assert view.note and "No company data" in view.note


def test_partial_facets_leave_empty_fields():
    # Only a financials facet survived (e.g. profile/news endpoints failed upstream).
    only_fin = [i for i in _items() if i.extra["kind"] == "financials"]
    view = _assemble_company("AAPL", only_fin)
    assert view.metrics["pe_ttm"] == 37.35
    assert view.name is None and view.market_cap is None and view.news == []


def test_company_emits_one_signal_and_passes_resolved_symbol():
    svc, connector, signals = _service(_items())
    view = svc.company("AAPL")

    assert view.name == "Apple Inc"
    assert connector.queried == ["AAPL"]  # bare ticker passes straight through
    kinds = [kind for kind, _ in signals.emitted]
    assert kinds == ["company"]  # exactly one signal
    assert signals.emitted[0][1]["symbol"] == "AAPL"


def test_company_resolves_name_via_symbol_search(monkeypatch):
    svc, connector, _ = _service(_items())
    from jarvis.results import SymbolMatch

    monkeypatch.setattr(
        svc, "symbol_search", lambda q: [SymbolMatch(symbol="AAPL", description="Apple Inc")]
    )
    svc.company("apple")
    assert connector.queried == ["AAPL"]  # name -> ticker before the fundamentals fetch


def test_company_never_raises_on_connector_failure():
    class _Boom:
        name = "fundamentals"
        description = "x"

        def fetch(self, query):
            raise RuntimeError("finnhub down")

    svc, _, _ = _service(_items())
    svc._connectors = {"fundamentals": _Boom()}
    view = svc.company("AAPL")
    assert view.note and view.name is None  # degrades to the no-data view, never raises
