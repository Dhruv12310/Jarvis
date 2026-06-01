"""Architecture boundary guards (SPEC.md DoD #6): keep backend specifics behind their seams.

These turn the spec's rules into automated tests:
  - raw SQL only in sqlite_store.py
  - chromadb imported only in chroma_store.py
  - declared runtime dependencies stay within the approved set
"""

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_JARVIS = _ROOT / "jarvis"
_APPROVED_RUNTIME_DEPS = {"python-dotenv", "ollama", "chromadb"}

_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|PRAGMA)\b", re.IGNORECASE)
_CHROMA_IMPORT = re.compile(r"^\s*(import chromadb|from chromadb)", re.MULTILINE)


def _py_files_excluding(name: str) -> list[Path]:
    return [path for path in _JARVIS.rglob("*.py") if path.name != name]


def test_no_raw_sql_outside_sqlite_store():
    offenders = [
        path.name
        for path in _py_files_excluding("sqlite_store.py")
        if _SQL.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"raw SQL found outside sqlite_store.py: {offenders}"


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
