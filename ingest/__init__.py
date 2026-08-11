"""Civic Ledger ingest package.

Raw government-source data → validate → SQLite → deterministic JSON export.
No LLM anywhere in this package (enforced structurally by checks/no_llm.py).
"""
