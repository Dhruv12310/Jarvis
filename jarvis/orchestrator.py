"""The Phase 0 orchestrator: text in, local model out. Deliberately thin.

No tools, no routing, no cloud, no memory. It exists so later phases have a single place to grow
the conductor (Tier 1) without the CLI reaching into the model directly.
"""

from __future__ import annotations

from jarvis.llm.client import LLMClient


class Orchestrator:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def chat(self, text: str) -> str:
        return self._llm.generate(text)
