"""Explicit public boundary for extracted Relic core modules.

This package starts as a thin compatibility layer over the existing
`relic.*` implementation. Future extraction work should move logic here
module by module while keeping the import surface stable.
"""

__all__ = [
    "db",
    "inbox",
    "portrait",
    "question_engine",
    "synthesizer",
]
