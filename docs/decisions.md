# decisions.md — ADR log

Spec-level decisions (D1–D18) live in `IMPLEMENTATION.md` §2 and are not
re-opened. This file records **builder** decisions made during construction:
one dated line each, per the handoff contract (§0.1c), plus the concrete
version pins §3 requires recording at INC-0.

## Version pins (recorded at INC-0, 2026-08-11)

Resolved and locked in `uv.lock` (Python) and `site/package-lock.json` (Node).

**Python** — managed 3.12.13 via uv (`.python-version` = 3.12):

| Package | Spec pin | Locked |
|---------|----------|--------|
| pydantic | ^2.7 | 2.13.4 |
| httpx | ^0.27 | 0.27.2 |
| tenacity | ^9 | 9.1.4 |
| PyYAML | ^6 | 6.0.3 |
| Flask | ^3 | 3.1.3 (curation only) |
| pytest | ^8 | 8.4.2 |
| ruff | latest | 0.16.2 |

**Node** — engine 22 LTS in CI (see 2026-08-11 deviation below):

| Package | Spec pin | Locked |
|---------|----------|--------|
| astro | ^5 | 5.18.2 |
| @astrojs/preact | — | 4.1.3 |
| preact | ^10 | 10.29.8 |
| tailwindcss | ^4 | 4.3.3 |
| @tailwindcss/vite | ^4 | 4.3.3 |
| fflate | ^0.8 | 0.8.3 |
| wrangler | ^4 | added with `worker/` at INC-16 (not needed until then) |

## Builder ADRs

- **2026-08-11 — uv installed via `pip install --user uv` (0.12.3).** The dev
  box had no uv; the standalone installer and winget were not used to keep the
  install auditable from the Python already present. uv added to user PATH.
- **2026-08-11 — Local Node is 24; CI pins Node 22 LTS (§3).** The build is
  Node-version-agnostic for Astro 5; CI uses the spec-pinned 22 for
  reproducibility. Local 24 is a tolerated dev deviation, not a project pin.
- **2026-08-11 — Tailwind v4 via `@tailwindcss/vite`, not `@astrojs/tailwind`.**
  The legacy Astro integration targets Tailwind v3; v4's Vite plugin is the
  supported path and matches the §3 pin.
- **2026-08-11 — `checks` entrypoint runs banned_words + no_llm at INC-0.** The
  data-dependent checks (symmetry, archive_links, integrity, Tier-3 guard) are
  no-ops on an empty dataset and are wired into `ingest/checks/run.py` as each
  increment implements real logic. This keeps `uv run checks` honest and green
  now without pretending checks exist that have no data to act on.
- **2026-08-11 — `no_llm.py` self-match defended two ways.** Endpoint fragments
  are assembled from concatenated string parts and the guard's own file is
  excluded from its scan; `tests/test_bootstrap.py` asserts the real scan over
  the real tree returns clean, so the guard cannot ship broken.
- **2026-08-11 — CI orders `astro build` before `uv run checks`.** §6.4 scans
  `site/dist/**`; that tree only exists after the build. Local acceptance runs
  checks before build (per the INC-0 acceptance string) where dist is simply
  absent and skipped-with-note; CI scans the real built output.
