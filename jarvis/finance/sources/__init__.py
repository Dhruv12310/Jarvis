"""Transaction sources. `source_for(path)` picks the importer by file extension."""

from __future__ import annotations

from pathlib import Path

from jarvis.finance.sources.base import TransactionSource
from jarvis.finance.sources.csv_source import CsvSource
from jarvis.finance.sources.ofx_source import OfxSource


def source_for(path: Path | str) -> TransactionSource:
    ext = Path(path).suffix.lower()
    if ext in (".ofx", ".qfx"):
        return OfxSource(path)
    if ext == ".csv":
        return CsvSource(path)
    raise ValueError(f"unsupported file type: {ext or path!r} (use .csv, .ofx, or .qfx)")
