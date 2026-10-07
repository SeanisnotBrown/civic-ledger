# Contributing

This repository is the entire client and the entire published dataset. Every
fact the site renders has a public commit history here. Contributions are
welcome under the constraints below — they are not style preferences, they are
the reason the project can be trusted.

## Read these first

1. **`MISSION.md`** — what the site is and why. Before any action, ask whether
   the change serves the mission. If it does not, it does not happen.
2. **`IMPLEMENTATIONv3.md`** — the only spec. §1 is the ground rules every
   contribution is held to; §2 is the ratified decisions a contribution applies
   rather than reopens; §5 is the phase order.
3. **`STATUS.md`** — the live state: the current phase, whether a local data
   pull is running, and what a human owes.

Older specs, plans and progress logs are archived under `docs/archive/` and are
not read before work.

## The rules that block a merge

The full text is `IMPLEMENTATIONv3.md` §1. The ones a contributor trips over
most:

- **Never publish something false or falsely framed** (rule 0). A true number
  in a false frame is false. Site copy that describes the system counts: copy
  flips in the same commit as the feature that makes it true.
- **Ask the owner when unsure** (rule 1), in plain non-technical language.
  Always required for anything evaluative — what counts as good or poor, where
  a cutoff sits, how a grade is worded. A contributor never authors a political
  judgment.
- **Evaluative constants are ratified before they publish** (rule 5). Every
  threshold, weight, grade cutoff and grade label is proposed, picked by the
  owner, then committed to `data/config/thresholds.yaml` with the reason and
  the date.
- **The site states facts, never motive** (rule 6). A grade says what was
  measured ("voted against 6 of 9 stated priorities"), never why.
- **AI-written text is labeled and human-approved before it publishes**
  (rule 7, §4.6). AI is allowed in the publishing path; unlabeled or
  unreviewed AI text is not. Phase 3 adds `data/config/ai.yaml` (model id and
  prompt version per task) and `ingest/ai.py`, the one module every AI call
  goes through. Neither exists yet.
- **Raw API responses are cached to disk before parsing** (rule 4). Never
  hammer a government API; re-parse from `data/raw/` when the cached payload
  already has what is needed.
- **Secrets come from `.env`** (rule 10). Never hardcoded, never committed.
- **Both gates run before every push** (rule 9): `uv run ruff check .` and the
  full pytest line recorded in `STATUS.md`, then the site build and its
  `test:*` scripts.

## Blocking CI checks

- **Banned words** (`ingest/checks/banned_words.py`): no motive-or-character
  framing (`liar`, `hypocrisy`, ...) in `data/**`, `site/src/**`, or
  `site/dist/**`. This is the mechanical edge of rule 6. Extend the list only
  by PR so extensions are diffable.
- **Symmetry** (`ingest/checks/symmetry.py`): every member is treated by the
  same formula, or is listed in the exceptions with a mechanical reason.
- **Classification**, **integrity**, **ms**: dataset guards. All run from
  `uv run checks`.
- **Grade labels** and **link/file-count/a11y** checks: the `test:*` scripts in
  `site/package.json`.

## Development

- Dev environment: Python 3.12 via `uv`; Node 22 LTS for the Astro site.
- Python: `uv run checks`, `uv run pytest`.
- Site: `cd site && npm run build`.
- Corrections are normal commits, never force-pushes.
- Commit at every passing phase acceptance, with the message `P<N>: <what>`.

## Data is public record

Everything under `data/` is published. Treat it as the historical record: a
correction is a new commit referencing the issue, never a silent edit. The
process is `docs/correction-process.md`.

**A dirty `git status` under `data/` is often a running local data pull, not
abandoned work.** Read `STATUS.md` before cleaning or committing anything
there.
