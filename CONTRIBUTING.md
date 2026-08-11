# Contributing

This repository is the entire client and the entire published dataset. Every
fact the site renders has a public commit history here. Contributions are
welcome under the constraints below — they are not style preferences, they are
the reason the project can be trusted.

## No LLM in the publishing path (policy)

**No LLM output appears anywhere in the publishing path.** No large-language-model
SDK may be added to any lockfile, and no source file under `ingest/`, `site/`,
or `worker/` may call an LLM API endpoint. This is enforced structurally in CI
by `ingest/checks/no_llm.py` (§6.6 of `IMPLEMENTATION.md`): an LLM call cannot
merge.

Concretely, a contribution **must not**:

- add `anthropic`, `openai`, `google-genai`/`generativeai`, `mistralai`,
  `cohere`, `ollama`, `litellm`, `langchain*`, or `llama-index*` to any
  dependency lockfile;
- call any LLM inference endpoint from build, ingest, curation, or site code;
- generate, summarize, classify, or paraphrase political content that publishes
  as fact. Where the spec says "curated" or "manual," the data comes from the
  owner via the curation tools. UI chrome text is fine; political content is not.

## The four load-bearing values (priority order)

1. Never publish something false or falsely framed.
2. Never render partisan lean (symmetry; banned words; no spectrum).
3. Never collect what a subpoena could use (privacy architecture).
4. Ship partial value early.

When they conflict, the earlier value wins.

## Other blocking CI checks

- **Banned words** (`ingest/checks/banned_words.py`, §6.4): no partisan-lean
  framing in `data/**`, `site/src/**`, or `site/dist/**`. Extend the list only
  by PR so extensions are diffable.
- **Symmetry** (§6.5), **archive links** (§6.11), **Tier-3 guard**, **a11y** —
  come online in their increments; all can fail the build.

## Development

- Dev environment: Python 3.12 via `uv`; Node 22 LTS for the Astro site.
- Python: `uv run checks`, `uv run pytest`.
- Site: `cd site && npm run build`.
- Corrections are normal commits, never force-pushes (§9, brief 5.12).

## Data is public record

Everything under `data/` is published. Treat it as the historical record: a
correction is a new commit referencing the issue, never a silent edit.
