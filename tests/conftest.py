"""Make the local test run match CI: credential-blind, and not-CI by default.

V2-11 task 4 added a `/actions` fetch to `bills.run()` and left one existing
test's network call unstubbed. It passed locally — a developer `.env` holds a
real `CONGRESS_API_KEY`, so the call went out to the live API — and failed in
CI, which has no key. The local gate said 452 passed while master was red.

So: hide `.env` and the credential environment variables from every test. An
unstubbed call that needs a credential now raises the same RuntimeError here
that it raises in CI, at the moment the test is written rather than after the
push. A test that genuinely wants one sets it with `monkeypatch.setenv`.

The same fixture clears `CI`/`GITHUB_ACTIONS`, for the mirror-image failure: the
V2-11 backfill refuses to run under those (it would cost more Actions minutes
than a month's allowance), so three tests that exercise `--congress` passed on a
developer machine, where neither is set, and failed in CI, where both are. Every
test now starts from a known not-CI baseline; the tests that exercise the refusal
set the variable themselves.
"""

from __future__ import annotations

import pytest

CREDENTIALS = (
    "CONGRESS_API_KEY",
    "LEGISCAN_API_KEY",
    "FEC_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "IA_S3_ACCESS_KEY",
    "IA_S3_SECRET_KEY",
)


# Set on a GitHub runner, absent on a developer machine. Anything that branches
# on these must be given the environment it expects, explicitly, by the test.
CI_MARKERS = ("CI", "GITHUB_ACTIONS")


@pytest.fixture(autouse=True)
def _same_environment_as_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest import env

    monkeypatch.setattr(env, "_dotenv_values", dict)
    for name in (*CREDENTIALS, *CI_MARKERS):
        monkeypatch.delenv(name, raising=False)
