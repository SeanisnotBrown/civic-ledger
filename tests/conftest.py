"""Make the local test run credential-blind, exactly like CI.

V2-11 task 4 added a `/actions` fetch to `bills.run()` and left one existing
test's network call unstubbed. It passed locally — a developer `.env` holds a
real `CONGRESS_API_KEY`, so the call went out to the live API — and failed in
CI, which has no key. The local gate said 452 passed while master was red.

So: hide `.env` and the credential environment variables from every test. An
unstubbed call that needs a credential now raises the same RuntimeError here
that it raises in CI, at the moment the test is written rather than after the
push. A test that genuinely wants one sets it with `monkeypatch.setenv`.
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


@pytest.fixture(autouse=True)
def _no_credentials_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest import env

    monkeypatch.setattr(env, "_dotenv_values", dict)
    for name in CREDENTIALS:
        monkeypatch.delenv(name, raising=False)
