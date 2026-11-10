"""Local evidence storage for analyzed matches (no network access).

``frcstack.data.store`` holds the SQLite evidence store. Names are resolved
lazily so importing this package stays cheap and has no side effects.
"""
from __future__ import annotations

__all__ = ["EvidenceRecord", "EvidenceStore", "UnsupportedProgramError", "default_db_path"]


def __getattr__(name: str):
    if name in __all__:
        from frcstack.data import store

        return getattr(store, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
