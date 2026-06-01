"""Grounded answerer: the LLM summarizes ONLY the fetched data, citing sources.

If there is no data, it must say it could not find current information rather than answering from
model memory. Deterministic code builds the DATA block; the LLM only phrases it.
"""

from __future__ import annotations

from jarvis.connectors.base import ConnectorResult
from jarvis.llm.client import LLMClient

_INSTRUCTION = (
    "You are Jarvis answering from live data only. Use ONLY the DATA below to answer the question. "
    "Cite the source name(s). If the DATA is empty or does not address the question, say you could "
    "not find current information. Do NOT use prior knowledge or invent facts.\n\n"
)


class Answerer:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def answer(self, question: str, results: list[ConnectorResult]) -> str:
        prompt = f"{_INSTRUCTION}QUESTION: {question}\n\nDATA:\n{self._format(results)}"
        return self._llm.generate(prompt).strip()

    @staticmethod
    def _format(results: list[ConnectorResult]) -> str:
        blocks = []
        for result in results:
            if not result.items:
                continue
            header = f"Source: {result.source.name}"
            if result.source.url:
                header += f" ({result.source.url})"
            lines = [header]
            for item in result.items:
                line = f"- {item.title} | {item.detail}"
                if item.url:
                    line += f" | {item.url}"
                lines.append(line)
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks) if blocks else "(no data found)"
