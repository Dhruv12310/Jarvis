"""TransactionSource seam: where transactions come from, so the engine doesn't care.

Pluggable like `Connector`. CSV/OFX are fully local; Plaid (the only outbound source) sits behind
the same contract so the deterministic engine is identical regardless of source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from jarvis.finance.transaction import Account, Transaction


class TransactionSource(ABC):
    @abstractmethod
    def load(self) -> tuple[list[Transaction], list[Account]]:
        """Return normalized transactions + accounts (Decimal amounts, signs normalized)."""
