"""Phase 0 Definition-of-Done self-test.

Exercises the whole stack: one generation, a structured note round-trip, and an embed then
similarity-read round-trip over seeded, clearly-distinct notes. Injecting fakes makes the
orchestration verifiable offline; the defaults use a live Ollama. Prints PASS or a diagnostic FAIL.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from jarvis.llm.client import LLMClient, OllamaClient
from jarvis.llm.embedder import Embedder, OllamaEmbedder
from jarvis.orchestrator import Orchestrator
from jarvis.stores.chroma_store import ChromaVectorStore
from jarvis.stores.sqlite_store import SQLiteStructuredStore

# Three deliberately unrelated notes; the query is a sub-phrase of the first, so it is
# unambiguously the closest hit for both a real embedder and the deterministic test fake.
_SEED_NOTES = [
    "the dentist appointment is on friday morning",
    "rebalance the retirement investment portfolio next quarter",
    "the bread recipe needs flour water salt and yeast",
]
_QUERY = "dentist appointment friday"


@dataclass
class SelfTestResult:
    passed: bool
    checks: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        header = "PASS" if self.passed else "FAIL"
        return "\n".join([f"Phase 0 self-test: {header}", *self.checks])


def run_selftest(llm: LLMClient | None = None, embedder: Embedder | None = None) -> SelfTestResult:
    """Run the DoD checks. Pass fakes for an offline check; defaults talk to Ollama.

    Any backend failure (for example Ollama unreachable) is reported as a clean FAIL.
    """
    checks: list[str] = []
    try:
        orchestrator = Orchestrator(llm or OllamaClient())
        reply = orchestrator.chat("Reply with a short greeting.")
        if not reply.strip():
            return SelfTestResult(False, [*checks, "[x] model returned an empty response"])
        checks.append(f"[ok] model responded ({len(reply.strip())} chars)")

        active_embedder = embedder or OllamaEmbedder()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)

            store = SQLiteStructuredStore(tmp_path / "jarvis.db")
            saved = store.save_note("selftest note")
            fetched = store.get_notes()
            store.close()
            if not any(note.id == saved.id and note.content == "selftest note" for note in fetched):
                return SelfTestResult(False, [*checks, "[x] structured note did not round-trip"])
            checks.append(f"[ok] structured store round-trip (note #{saved.id})")

            vector = ChromaVectorStore(tmp_path / "chroma")
            for index, text in enumerate(_SEED_NOTES):
                vector.add(id=str(index), text=text, embedding=active_embedder.embed(text))
            hits = vector.query(active_embedder.embed(_QUERY), k=1)
            if not hits or hits[0].text != _SEED_NOTES[0]:
                got = hits[0].text if hits else "(no hits)"
                return SelfTestResult(
                    False, [*checks, f"[x] similarity miss: expected seed 0, got {got!r}"]
                )
            checks.append(f"[ok] vector similarity-read (top: {hits[0].text!r})")
    except Exception as exc:  # any backend failure becomes a clean diagnostic, not a crash
        return SelfTestResult(False, [*checks, f"[x] error: {type(exc).__name__}: {exc}"])

    return SelfTestResult(True, checks)


def main() -> int:
    result = run_selftest()
    print(result)
    return 0 if result.passed else 1
