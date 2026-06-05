"""Architecture boundary guards: keep backend specifics behind their seams.

These turn the project's invariants into automated tests:
  - raw SQL only in sqlite_store.py and sqlite_cache.py
  - chromadb imported only in chroma_store.py
  - httpx (outbound HTTP) imported only under connectors/
  - the Google client libs imported only under calendar/
  - the Flet UI toolkit imported only under ui/
  - the local voice libs (STT/TTS/audio) imported only under voice/
  - the finance source libs (ofxtools/plaid) imported only under finance/
  - connectors do not import one another
  - declared runtime dependencies stay within the approved set
"""

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_JARVIS = _ROOT / "jarvis"
_APPROVED_RUNTIME_DEPS = {
    "python-dotenv",
    "ollama",
    "chromadb",
    "httpx",
    "google-api-python-client",
    "google-auth-oauthlib",
    "google-auth-httplib2",
    "flet",
    "fastapi",
    "uvicorn",
    "faster-whisper",
    "sounddevice",
    "numpy",
    "piper-tts",
    "ofxtools",
    "plaid-python",
    "anthropic",
}
_SQL_ALLOWED = {"sqlite_store.py", "sqlite_cache.py"}

# Raw SQL in this repo is written UPPERCASE by convention. Matching case-sensitively keeps the
# tripwire on real SQL while ignoring the English word "update" and method calls like .update().
_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|PRAGMA)\b")
_CHROMA_IMPORT = re.compile(r"^\s*(import chromadb|from chromadb)", re.MULTILINE)
_HTTPX_IMPORT = re.compile(r"^\s*(import httpx|from httpx)", re.MULTILINE)
# google\w* (not \bgoogle\b) so underscore packages like google_auth_httplib2 are also caught -
# a \b between "google" and "_" would let that approved dep be imported anywhere undetected.
_GOOGLE_IMPORT = re.compile(r"^\s*(import|from)\s+google\w*", re.MULTILINE)
_FLET_IMPORT = re.compile(r"^\s*(import|from)\s+flet\b", re.MULTILINE)
# The web toolkit (FastAPI + uvicorn) stays under api/ so the HTTP transport is swappable and the
# web front-end stays thin - exactly the seam the Flet guard enforces for the desktop GUI.
_API_IMPORT = re.compile(r"^\s*(import|from)\s+(fastapi|uvicorn)\b", re.MULTILINE)
# Local audio/voice toolkits stay under voice/ so audio + transcripts never leak elsewhere.
# numpy is general-purpose and intentionally not restricted.
_VOICE_IMPORT = re.compile(
    r"^\s*(import|from)\s+(faster_whisper|sounddevice|piper)\b", re.MULTILINE
)
# The OFX parser (and later the Plaid client) stay under finance/ - the source seam, so the engine
# and the rest of the app never depend on a parsing/aggregator lib.
_FINANCE_SOURCE_IMPORT = re.compile(r"^\s*(import|from)\s+(ofxtools|plaid)\b", re.MULTILINE)
# The Anthropic SDK stays under router/ - the Tier-2 Model Router is the ONLY seam allowed to reach
# the cloud (and only after redaction). Making this structural enforces the trust boundary.
_ANTHROPIC_IMPORT = re.compile(r"^\s*(import|from)\s+anthropic\b", re.MULTILINE)


def _py_files_excluding(name: str) -> list[Path]:
    return [path for path in _JARVIS.rglob("*.py") if path.name != name]


def test_no_raw_sql_outside_allowed_modules():
    offenders = [
        path.name
        for path in _JARVIS.rglob("*.py")
        if path.name not in _SQL_ALLOWED and _SQL.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"raw SQL found outside {_SQL_ALLOWED}: {offenders}"


def test_no_chromadb_import_outside_chroma_store():
    offenders = [
        path.name
        for path in _py_files_excluding("chroma_store.py")
        if _CHROMA_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"chromadb imported outside chroma_store.py: {offenders}"


def test_declared_runtime_deps_are_within_the_approved_set():
    data = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = data["project"]["dependencies"]
    names = {re.split(r"[<>=!~ \[]", dep, maxsplit=1)[0].strip().lower() for dep in declared}
    unexpected = names - _APPROVED_RUNTIME_DEPS

    assert names <= _APPROVED_RUNTIME_DEPS, f"unexpected runtime deps: {unexpected}"


def test_httpx_imported_only_under_connectors():
    # Outbound HTTP is the trust boundary: only Collectors (connectors/) may cross it.
    offenders = [
        str(path.relative_to(_JARVIS))
        for path in _JARVIS.rglob("*.py")
        if path.parent.name != "connectors"
        and _HTTPX_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"httpx imported outside connectors/: {offenders}"


def test_google_libs_imported_only_under_calendar():
    # The calendar is the first private-data integration; its Google deps stay behind that seam.
    offenders = [
        str(path.relative_to(_JARVIS))
        for path in _JARVIS.rglob("*.py")
        if path.parent.name != "calendar"
        and _GOOGLE_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"google libs imported outside calendar/: {offenders}"


def test_google_guard_catches_underscore_packages():
    # Regression: a \bgoogle\b pattern would miss these approved underscore deps, so the guard
    # must match all three official libraries' import forms (incl. google_auth_httplib2).
    for line in (
        "import googleapiclient.discovery",
        "from google.oauth2.credentials import Credentials",
        "from google_auth_oauthlib.flow import InstalledAppFlow",
        "import google_auth_httplib2",
    ):
        assert _GOOGLE_IMPORT.search(line), f"guard failed to flag: {line!r}"


def test_flet_imported_only_under_ui():
    # The UI toolkit stays behind the ui/ seam so it is swappable (and front-ends stay thin).
    offenders = [
        str(path.relative_to(_JARVIS))
        for path in _JARVIS.rglob("*.py")
        if path.parent.name != "ui" and _FLET_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"flet imported outside ui/: {offenders}"


def test_api_libs_imported_only_under_api():
    # The web toolkit stays behind the api/ seam so the HTTP transport is swappable (and the web
    # front-end stays thin) - the same rule the Flet guard enforces for the desktop GUI.
    offenders = [
        str(path.relative_to(_JARVIS))
        for path in _JARVIS.rglob("*.py")
        if path.parent.name != "api" and _API_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"web API libs imported outside api/: {offenders}"


def test_voice_libs_imported_only_under_voice():
    # Local STT/TTS/audio stay behind the voice/ seam: audio + transcripts never leak elsewhere.
    offenders = [
        str(path.relative_to(_JARVIS))
        for path in _JARVIS.rglob("*.py")
        if path.parent.name != "voice" and _VOICE_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"voice libs imported outside voice/: {offenders}"


def test_voice_guard_catches_all_three_libs():
    # Pin the regex itself (not just its current effect): dropping a lib from it must fail a test.
    for line in (
        "import faster_whisper",
        "import sounddevice as sd",
        "from piper import PiperVoice",
    ):
        assert _VOICE_IMPORT.search(line), f"guard failed to flag: {line!r}"
    assert not _VOICE_IMPORT.search("import numpy as np")  # numpy is intentionally unrestricted


def test_finance_source_libs_imported_only_under_finance():
    # ofxtools/plaid stay behind the TransactionSource seam (under finance/), so the engine never
    # depends on a parsing or third-party aggregator lib.
    offenders = [
        str(rel)
        for path in _JARVIS.rglob("*.py")
        if "finance" not in (rel := path.relative_to(_JARVIS)).parts
        and _FINANCE_SOURCE_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"finance source libs imported outside finance/: {offenders}"


def test_anthropic_imported_only_under_router():
    # Tier 2 is the controlled exception: only the Model Router (router/) may reach the cloud, and
    # only after redaction. Confining the SDK makes "nothing private leaves except via the router"
    # structural rather than a convention.
    offenders = [
        str(path.relative_to(_JARVIS))
        for path in _JARVIS.rglob("*.py")
        if path.parent.name != "router"
        and _ANTHROPIC_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"anthropic imported outside router/: {offenders}"


def test_anthropic_guard_catches_import_forms():
    # Pin the regex: both import forms (including the lazy, indented one) must be flagged.
    for line in ("import anthropic", "    import anthropic", "from anthropic import Anthropic"):
        assert _ANTHROPIC_IMPORT.search(line), f"guard failed to flag: {line!r}"


def test_finance_engine_imports_no_llm():
    # The absolute Phase 4 rule, made structural: the deterministic engine never imports the LLM, so
    # it cannot possibly compute, estimate, or infer a financial figure via a model.
    engine = (_JARVIS / "finance" / "engine.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+.*\b(llm|ollama)\b", engine, re.MULTILINE), (
        "the finance engine must not import the LLM - every figure is deterministic code"
    )


def test_proactivity_deterministic_modules_import_no_llm():
    # Phase 5 §8: the trigger/weights/context/user-model math is deterministic - a model can never
    # compute a trigger, a confidence, or a score. (reflect.py is the one allowed LLM caller.)
    for name in (
        "trigger_weights.py",
        "trigger.py",
        "context.py",
        "user_model.py",
        "candidate.py",
        "generators.py",
        "goal_terms.py",
        "features.py",
        "rank.py",
        "feedback.py",
        "bandit.py",
    ):
        path = _JARVIS / "proactivity" / name
        if not path.exists():
            continue  # built across slices
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+.*\b(llm|ollama)\b", text, re.MULTILINE), (
            f"proactivity/{name} must not import the LLM - reflection math is deterministic"
        )


def test_connectors_do_not_import_each_other():
    connectors_dir = _JARVIS / "connectors"
    modules = {
        p.stem for p in connectors_dir.glob("*.py") if p.stem not in {"__init__", "base", "caching"}
    }
    offenders = []
    for path in connectors_dir.glob("*.py"):
        if path.stem not in modules:
            continue
        text = path.read_text(encoding="utf-8")
        for other in modules - {path.stem}:
            if re.search(rf"jarvis\.connectors\.{other}\b", text):
                offenders.append(f"{path.name} -> {other}")

    assert offenders == [], f"connectors must stay independent: {offenders}"
