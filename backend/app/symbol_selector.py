from __future__ import annotations


class SymbolSelector:
    """Reserved extension point for future dynamic symbol selection."""

    def select(self, configured_symbols: list[str]) -> list[str]:
        return configured_symbols

