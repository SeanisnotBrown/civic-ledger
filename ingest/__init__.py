"""Civic Ledger ingest package.

Raw government-source data → validate → SQLite → deterministic JSON export.

Spec: `IMPLEMENTATIONv3.md` (ground rules in §1). AI is allowed in the
publishing path as of 2026-10-07, under rule 7: anything it writes is labeled
and human-approved before it publishes. Phase 3 adds `data/config/ai.yaml`
(model id and prompt version per task) and `ingest/ai.py`, the one module every
AI call goes through; neither exists yet.
"""
