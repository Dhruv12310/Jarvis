"""JarvisService.project_deepdive(): Tier-2 goal research brief with graceful fallback. Offline.

Critically asserts the trust boundary: the raw goal description (private text) never crosses to the
cloud - only public derived terms + public item titles do.
"""


from jarvis.connectors.base import ConnectorResult, Item, Source
from jarvis.proactivity.goal_terms import GoalTerms
from jarvis.service import JarvisService, _project_block

GOAL_DESC = "Build a personal finance budgeting app for couples"


class _Goal:
    def __init__(self, id, description, status="active"):
        self.id = id
        self.description = description
        self.status = status


class _FakeConnector:
    def __init__(self, name, items):
        self.name = name
        self.description = name
        self._items = items

    def fetch(self, query):
        return ConnectorResult(source=Source(name=self.name), items=self._items, query=query)


class _Store:
    def __init__(self, goals):
        self._goals = goals

    def get_goals(self, status=None):
        return [g for g in self._goals if status is None or g.status == status]

    def get_recent_suggestions(self, since=None):
        return []


class _Signals:
    def __init__(self):
        self.emitted = []

    def emit(self, kind, payload):
        self.emitted.append((kind, payload))


class _FakeRouter:
    def __init__(self, available=True, reply="BRIEF"):
        self._available = available
        self.reply = reply
        self.blocks = []

    @property
    def available(self):
        return self._available

    def deepdive(self, block, instruction):
        self.blocks.append(block)
        return self.reply


def _service(router, goals=None):
    goals = goals if goals is not None else [_Goal(1, GOAL_DESC)]
    paper = Item(
        title="Personal Finance Planning with Reinforcement Learning",
        detail="A. Researcher et al., 2026-06-01",
        url="http://arxiv.org/abs/1",
        extra={"kind": "paper", "abstract": "We model budgets."},
    )
    news = Item(
        title="Fintech budgeting startups raise funding",
        detail="reuters.com, 2026-06-02",
        url="https://r/1",
        extra={"kind": "news", "source": "reuters.com"},
    )
    connectors = {
        "arxiv": _FakeConnector("arxiv", [paper]),
        "news": _FakeConnector("news", [news]),
    }
    return JarvisService(
        orchestrator=None,
        knowledge=None,  # _feed_knowledge guards on the AttributeError -> no snippet
        store=_Store(goals),
        memory=None,
        signals=_Signals(),
        source="test",
        connectors=connectors,
        model_router=router,
    )


def test_escalates_and_returns_brief():
    router = _FakeRouter(reply="full research brief")
    svc = _service(router)
    result = svc.project_deepdive(1)

    assert result["escalated"] is True
    assert result["report"] == "full research brief"
    assert result["note"] is None


def test_block_is_public_and_omits_raw_goal_text():
    # THE trust-boundary test: the private goal description must not cross to the cloud.
    router = _FakeRouter()
    svc = _service(router)
    svc.project_deepdive(1)

    block = router.blocks[0]
    assert GOAL_DESC not in block  # raw goal description never sent
    assert "couples" not in block  # nor any private token unique to the description
    assert "personal finance" in block.lower()  # public derived topic is present
    assert "Personal Finance Planning with Reinforcement Learning" in block  # public paper title


def test_disabled_without_router():
    result = _service(None).project_deepdive(1)
    assert result["escalated"] is False and result["report"] is None
    assert "ANTHROPIC_API_KEY" in result["note"]


def test_disabled_when_router_unavailable():
    result = _service(_FakeRouter(available=False)).project_deepdive(1)
    assert result["escalated"] is False and result["report"] is None


def test_unknown_goal_is_graceful():
    result = _service(_FakeRouter()).project_deepdive(999)
    assert result["escalated"] is False and result["report"] is None
    assert "Unknown" in result["note"]


def test_survives_cloud_failure():
    class _Boom(_FakeRouter):
        def deepdive(self, block, instruction):
            raise RuntimeError("anthropic 500")

    result = _service(_Boom()).project_deepdive(1)
    assert result["escalated"] is False and result["report"] is None
    assert "failed" in result["note"].lower()


def test_emits_exactly_one_signal():
    svc = _service(_FakeRouter())
    svc.project_deepdive(1)
    kinds = [k for k, _ in svc._signals.emitted]
    assert kinds == ["project_deepdive"]
    assert svc._signals.emitted[0][1]["goal_id"] == 1


def test_project_block_excludes_description_directly():
    terms = GoalTerms(symbols=["AAPL"], topics=["personal finance"])
    items = [
        type("I", (), {"title": "Paper One", "kind": "paper"})(),
        type("I", (), {"title": "News One", "kind": "news"})(),
    ]
    block = _project_block(terms, items)
    assert "personal finance" in block and "AAPL" in block
    assert "Paper One" in block and "News One" in block
