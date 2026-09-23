# Contributing

This repository is the entire client and the entire published dataset. Every
fact the site renders has a public commit history here. Contributions are
welcome under the constraints below — they are not style preferences, they are
the reason the project can be trusted.

## No LLM in the publishing path (policy)

**No LLM output appears anywhere in the publishing path.** No large-language-model
SDK may be added to any lockfile, and no source file under `ingest/`, `site/`,
or `worker/` may call an LLM API endpoint. This is enforced structurally in CI
by `ingest/checks/no_llm.py` (§6.6 of `IMPLEMENTATIONv2.md`): an LLM call cannot
merge.

Concretely, a contribution **must not**:

- add `anthropic`, `openai`, `google-genai`/`generativeai`, `mistralai`,
  `cohere`, `ollama`, `litellm`, `langchain*`, or `llama-index*` to any
  dependency lockfile;
- call any LLM inference endpoint from build, ingest, curation, or site code;
- generate, summarize, classify, or paraphrase political content that publishes
  as fact. Where the spec says "curated" or "manual," the data comes from the
  owner via the curation tools. UI chrome text is fine; political content is not.

## The four load-bearing values (priority order, amended 2026-08-13)

1. Never publish something false or falsely framed.
2. Evaluative labels — ranks, grades, "poor attendance" — are publishable only
   under the disclosure standard: a formula published on `/methods`, applied
   identically to every member and party, with inputs and denominator visible.
   The site still never asserts motive, intent, or character.
3. Collect only what the product needs, and the site may read what it
   collects (amended 2026-09-23, SD-32); every stored table is listed on
   `/privacy` before it exists; never sold; population trends only via
   K-anonymous aggregates; deletion deletes; anonymous use stays available
   forever.
4. Ship partial value early.

When they conflict, the earlier value wins. Full detail, including what
changed from the original four values and why: `IMPLEMENTATIONv2.md` §0.4.

## Other blocking CI checks

- **Banned words** (`ingest/checks/banned_words.py`, §6.4): no motive-or-
  character framing (`liar`, `hypocrisy`, ...) in `data/**`, `site/src/**`, or
  `site/dist/**`. Extend the list only by PR so extensions are diffable.
- **Symmetry** (§6.5), **archive links** (§6.9), **Tier-3 disclosure guard**
  (§6.8), **a11y** — come online in their increments; all can fail the build.

## Development

- Dev environment: Python 3.12 via `uv`; Node 22 LTS for the Astro site.
- Python: `uv run checks`, `uv run pytest`.
- Site: `cd site && npm run build`.
- Corrections are normal commits, never force-pushes (§9, brief 5.12).

## Data is public record

Everything under `data/` is published. Treat it as the historical record: a
correction is a new commit referencing the issue, never a silent edit.
