# Banned-words check: a faster scan (copilot call, not reviewed by Sean)

**Status: copilot call, not reviewed by Sean.** Built overnight 2026-11-26 on branch
`checks-banned-words-narrow` under his standing grant of 2026-11-25 23:38 CT. **Not merged.**
The existing check stays in force on `master` until he says yes.
(STATUS.md "Owner decisions pending" 1; `owner-questions-2026-11-17.md` Q4.)

## For Sean (plain language)

**What was slow.** The check looks for 12 banned words and phrases in everything a reader
can see. It did that by running all 12 searches against every single line of every file:
about 84,000 files in `data/` plus the built site. That is why one test takes 16 to 21
minutes. On a sample of 5,521 files (75.6 MB), 97% of the time was those 12 searches
repeated per line. Reading the files was about 3%.

**What changed.** Nothing about what is checked. The check now first asks one quick
question of each file: "could any banned word possibly be in here?" Almost every file
plainly cannot, so it is cleared in one fast pass. Any file that might contain one still
gets the original line-by-line check, unchanged, so a real hit is reported exactly as
before (same file, same line, same word, same message). On the sample it went from about
17 to 19 seconds down to about 1.6 to 1.9 seconds, about 9 to 11 times faster. Whether the
same gain holds on the whole repo is the separate timing turn (table below, still TBD).

**What is still scanned.** Everything that was scanned before, nothing less:
- `data/**` (every published record, including `statements/` and `absences/`),
- `site/src/**` (site source and copy),
- `site/dist/**` (the built pages).
Same file types, same single allowlisted glossary page, same excluded folders (raw
captures, the absence review queue). Every file is still opened and read in full.

**What no longer happens.** The 12 line-by-line searches are no longer run on files that
provably contain none of the words. That is the only thing dropped. It is repeated work
on clean text, not a reader-visible surface.

**Why no published coverage is lost (3 lines).**
1. The quick question can only say "maybe" or "definitely not", and it is built so it never says "definitely not" about a file the old check would flag; a file with a "maybe" gets the full old check.
2. Tests plant each banned word in each kind of published file and require a failure; an equivalence test requires the same results, in the same order, as the old method on a tricky fixture set; I deliberately broke the new code two ways and the tests failed both times.
3. The banned-word list and its exceptions were not touched.

**The one decision for you: merge it or not.** Merging makes the check faster and no
weaker. Not merging leaves things as they are (slow, and it crashed once on 2026-10-29).
Nothing else is waiting on this.

**Separate thing I noticed, not changed (your call, optional).** The check looks only at
file types `.json .yaml .yml .md .astro .ts .tsx .js .jsx .html .css .txt`. The built
site also holds `.xml` files (2,695 in the build I looked at, including `feed.xml`). Those
are not scanned today and are not scanned after this change either. If a reader can see
the feed text, you may want `.xml` added. That would be stricter than today, so I did not
do it without you.

---

## Technical detail

### Where the time goes (sample, not the full repo)

Sample: first 639 members, 2,000 absences, 2,000 bills, 300 votes, 500 state files,
80 legislation files, `data/events/2023-07.json`, `data/metrics.json`, copied to a temp
folder: 5,521 files, 75.6 MB, 2,717,572 lines (longest line 1,761 chars), 166 files non-ASCII,
0 hits. Windows 11, one process, a full gate running elsewhere.

| Stage (old algorithm) | Time |
|---|---|
| read + decode (`read_text`) | 0.43-0.48 s |
| `splitlines` | 0.25-0.31 s |
| 12 compiled `\b<term>\b` IGNORECASE regexes x every line | 18.7 s (97%) |

Why it is slow: Python's `re` has no literal-prefix shortcut under IGNORECASE, so each
pattern is tried at each position of each line, 12 times over. Cost scales with
bytes x 12, and nearly every byte is clean. Scope facts: `data/` is 83,658 `.json` files /
554 MB in a fresh checkout; `site/dist` (not in a fresh worktree) is about 16.5k files,
13,155 of them `.html` (file counts only; I did not measure `site/dist` bytes, the size
walk timed out). STATUS.md's "~3.3 GB" for the whole scan most likely includes the built
site, which is the large part; I did not re-measure it. The real-repo pytest call (`test_banned_words_passes_on_clean_repo`,
`tests/test_bootstrap.py:53`) scans the tree once per pytest run; CI runs `uv run checks`
as a separate step (`ci.yml:76-77`), so the tree is scanned a second time there. I did
not dedupe across those two invocations; each is now cheap.

### What changed (`ingest/checks/banned_words.py`; list, exceptions, scope untouched)

- `find_hits` reads each file as bytes and decodes UTF-8 with `errors="replace"`, then
  asks `_maybe_has_hit(text)`. Only if that is true does it run `_scan_text`, which is the
  original per-line x per-pattern loop moved into a function, so hit tuples, order and
  `main()` messages are identical.
- `_maybe_has_hit`: if the text has none of the "fold characters", lowercase it and test
  each lowercased term as a plain substring (memory speed, no word boundary, so a superset
  of the boundary match); `False` only if none is present. Otherwise (a candidate, or a
  fold character present) one whole-text union regex of the same `\b<term>\b` IGNORECASE
  patterns decides.
- `_fold_chars()` is derived at first use by sweeping all 1,114,112 code points (0.10 s,
  once per process) for characters IGNORECASE equates with a character of any term.
  Today: U+0130, U+0131, U+017F (long s), U+212A (Kelvin sign). Derived, not hard-coded,
  so a different Python/Unicode version cannot silently narrow the scan.
- Whole-text vs per-line is safe because no term contains a line break and every character
  `str.splitlines` breaks on is non-word, so `\b` behaves the same at a line edge.
- `str.lower()` is one-for-one on every code point except the fold characters (U+0130
  lowercases to two characters), so terms cannot be split or merged by it. Tested.

### Not done, on purpose
- No result cache keyed on content hash or mtime: it adds state, and a fresh CI checkout
  has none to reuse. Revisit only if the timing turn shows IO, not the scan, dominating.
- No parallelism (RAM is tight, gains unmeasured).
- `_iter_text_files` (the walker, suffixes, allowlist, exclusions) is unchanged.

### Tests added: `tests/test_banned_words_narrow.py` (95 tests)
- Every surface x every suffix: planted `hypocrisy` fails (3 surfaces x 12 suffixes = 36).
- Every banned term x every surface (12 x 3 = 36), upper-cased in place.
- AI/site text surfaces: `data/statements`, `data/absences`, `data/state/ms/bills`, `site/src`, `site/dist` (5).
- Every in-scope file is read in full (spy on `read_bytes`); exclusions/allowlist/unscanned suffix unchanged.
- Equivalence on a 20-file fixture (CRLF, lone CR, U+2028/2029, form feed, BOM, invalid UTF-8,
  repeated terms, phrase split over lines, whole-word-only, non-ASCII clean/hit, Kelvin sign,
  long s, minified, 200 kB line, empty): new `find_hits` == original algorithm, same order;
  "nothing that failed before passes now"; clean tree clean in both.
- Seeded fuzz (4,000 strings): prefilter never clears a text the exact scan flags; `_scan_text` equals the original.
- Case-folded look-alikes alone in a file (6) plus a non-vacuity guard; fold-set completeness
  over all Unicode; only fold characters change length under `lower()`.
- `main()` failure and OK messages unchanged.
- Mutation checks run once, then reverted: using the fast path on text with fold characters
  failed 5 tests; making the regex stage always say "clean" failed 88 of 93 then-current tests; dropping `site/dist`
  from `SCAN_DIRS` failed 27.

Targeted run: new file (95) + `test_banned_words_scope.py` + `test_bootstrap.py` minus the
full-repo test: 112 passed. `uv run ruff check .` clean. Full suite and the real-repo scan
were deliberately NOT run.

### Timing: before / after (TBD, separate later turn)

| Measurement | Before | After |
|---|---|---|
| `find_hits()` on real repo, `data/` only | TBD | TBD |
| `find_hits()` on real repo, with built `site/dist` | TBD | TBD |
| `test_banned_words_passes_on_clean_repo` alone | TBD | TBD |
| `test_bootstrap.py` whole file | TBD | TBD |
| Full pytest gate | TBD | TBD |
| Equivalence on the real repo: old vs new `find_hits()` identical | TBD | TBD |

Sample (this turn, 5,521 files / 75.6 MB, noisy because a gate was running): old 16.6-19.0 s,
new 1.6-1.9 s.
