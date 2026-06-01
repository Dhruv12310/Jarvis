"""Architecture boundary guards: keep backend specifics behind their seams.

These turn the project's invariants into automated tests:
  - raw SQL only in sqlite_store.py and sqlite_cache.py
  - chromadb imported only in chroma_store.py
  - httpx (outbound HTTP) imported only under connectors/
  - connectors do not import one another
  - declared runtime dependencies stay within the approved set
"""

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_JARVIS = _ROOT / "jarvis"
_APPROVED_RUNTIME_DEPS = {"python-dotenv", "ollama", "chromadb", "httpx"}
_SQL_ALLOWED = {"sqlite_store.py", "sqlite_cache.py"}

_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|PRAGMA)\b", re.IGNORECASE)
_CHROMA_IMPORT = re.compile(r"^\s*(import chromadb|from chromadb)", re.MULTILINE)
_HTTPX_IMPORT = re.compile(r"^\s*(import httpx|from httpx)", re.MULTILINE)


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
