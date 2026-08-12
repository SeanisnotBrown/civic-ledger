"""INC-11 — local curation Flask app (statements + absence approvals).

LOCALHOST ONLY. `assert_loopback` refuses to bind any non-loopback address, so the
tool can never be exposed on a network (brief §5.10; the app touches owner-only
workflows and stages git commits). It supersedes the INC-6 absence-approval CLI.

Two tabs:
  * Statements — paste a verbatim quote + source URL, Capture (SPN2, verified), then
    Save. The Save control does not exist until a verified capture is in hand, and the
    save endpoint itself refuses without the stored `Capture` (curation.statements),
    so "no verified capture, no save" holds in the UI AND server-side.
  * Absences — the INC-6 review queue: verbatim excerpt + matched roll, Approve →
    writes the owner-approved `Absence.stated_reason` via the existing approver.

Nothing here authors content; the owner supplies and approves every field (H8/H9).
"""

from __future__ import annotations

import ipaddress
import json
import secrets
import sys
from dataclasses import dataclass
from datetime import date as _date
from urllib.parse import urlsplit

from flask import Flask, abort, redirect, render_template_string, request, url_for

from curation import absences, statements
from ingest.export import MEMBERS_DIR
from ingest.sources.archive_org import Capture, SpnClient, SpnError


class NonLoopbackBindError(RuntimeError):
    """Raised when the app is asked to bind a host that is not loopback."""


def assert_loopback(host: str) -> None:
    """Refuse any bind host that is not a loopback address. `localhost` and the
    loopback IP ranges (127.0.0.0/8, ::1) pass; everything else raises."""
    if host == "localhost":
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise NonLoopbackBindError(
            f"refusing to bind non-loopback host {host!r} (use 127.0.0.1 or localhost)"
        ) from exc
    if not ip.is_loopback:
        raise NonLoopbackBindError(f"refusing to bind non-loopback host {host!r}")


def _origin_is_loopback(origin: str) -> bool:
    """True iff a request `Origin`/`Referer` header names a loopback host. A missing
    hostname (e.g. the literal `Origin: null` some browsers send) is NOT loopback."""
    host = urlsplit(origin).hostname
    if not host:
        return False
    try:
        assert_loopback(host)
    except NonLoopbackBindError:
        return False
    return True


def _validate_capture_fields(fields: dict) -> None:
    """Reject a malformed statement draft BEFORE the (rate-limited) SPN capture runs,
    so a mistyped date or specificity never burns an archive capture (R-1a/M-6). The
    Statement model re-validates on save; this is the early, capture-sparing gate."""
    try:
        _date.fromisoformat(fields["date"])
    except ValueError as exc:
        raise ValueError(f"date must be ISO YYYY-MM-DD, got {fields['date']!r}") from exc
    spec = fields["specificity_level"]
    if spec is not None and spec not in (0, 1, 2, 3):
        raise ValueError(f"specificity level must be 0-3 (or blank), got {spec!r}")


# --- pending capture drafts (in-memory; single-user localhost tool) --------


@dataclass
class _Draft:
    fields: dict
    capture: Capture


def _covered_members() -> list[dict]:
    if not MEMBERS_DIR.exists():
        return []
    out = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(MEMBERS_DIR.glob("*.json"))]
    return sorted(out, key=lambda m: m["name"])


_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Civic Ledger — curate</title>
<style>body{font-family:system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem}
nav a{margin-right:1rem}label{display:block;margin:.6rem 0 .2rem;font-weight:600}
input,select,textarea{width:100%;padding:.4rem;font:inherit}textarea{min-height:6rem}
.msg{padding:.6rem;border-radius:.3rem;margin:.6rem 0}
.ok{background:#e6ffed}.err{background:#ffecec}
.card{border:1px solid #ccc;border-radius:.4rem;padding:1rem;margin:.8rem 0}
button{padding:.5rem 1rem;font:inherit;margin-top:.8rem}</style></head><body>
<nav><a href="{{ url_for('statements_tab') }}">Statements</a>
<a href="{{ url_for('absences_tab') }}">Absence approvals</a></nav><hr>{{ body|safe }}
</body></html>"""


def _render(body: str, **ctx):
    return render_template_string(_PAGE, body=render_template_string(body, **ctx))


def create_app() -> Flask:
    app = Flask(__name__)
    drafts: dict[str, _Draft] = {}
    # Per-process CSRF secret. Embedded as a hidden field in every form and required
    # on every POST (below), so a malicious page the owner happens to have open cannot
    # forge a cross-origin approval/capture at http://127.0.0.1:5000 while `curate app`
    # runs (R-1c/M-1). Regenerated each app start; never leaves the machine.
    csrf_token = secrets.token_urlsafe(32)

    @app.before_request
    def _csrf_guard():
        if request.method != "POST":
            return None
        # Belt: a cross-origin form POST carries the attacker's Origin/Referer. When
        # the header is present it MUST be loopback (an absent header — some same-origin
        # navigations omit it — falls through to the token check).
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin and not _origin_is_loopback(origin):
            abort(403)
        # Braces: the unguessable per-process token must be echoed by the form. A forged
        # cross-origin POST cannot read it (same-origin policy), so it cannot supply it.
        if not secrets.compare_digest(request.form.get("csrf", ""), csrf_token):
            abort(403)
        return None

    @app.route("/")
    def index():
        return redirect(url_for("statements_tab"))

    @app.route("/statements")
    def statements_tab():
        body = """<h1>Statements</h1>
        {% if msg %}<div class="msg {{ cls }}">{{ msg }}</div>{% endif %}
        <form method="post" action="{{ url_for('statements_capture') }}">
          <input type="hidden" name="csrf" value="{{ csrf }}">
          <label>Member</label><select name="member_id">
          {% for m in members %}
          <option value="{{ m.id }}">{{ m.name }} ({{ m.party }})</option>
          {% endfor %}
          </select>
          <label>Verbatim quote</label><textarea name="text" required></textarea>
          <label>Date (YYYY-MM-DD)</label><input name="date" required>
          <label>Venue</label><input name="venue" required>
          <label>Source URL</label><input name="source_url" type="url" required>
          <label>Named measures (bill ids / allowlisted titles, comma-separated)</label>
          <input name="named_measures">
          <label>Specificity level (0-3, blank = unscored)</label><input name="specificity_level">
          <label>Stance</label><select name="stated_position">
            <option value="">— unassigned —</option><option value="support">support</option>
            <option value="oppose">oppose</option></select>
          <button type="submit">Capture source (Save unlocks only after a verified capture)</button>
        </form>"""
        return _render(
            body, members=_covered_members(), csrf=csrf_token,
            msg=request.args.get("msg"), cls=request.args.get("cls", "ok"),
        )

    @app.post("/statements/capture")
    def statements_capture():
        spec_raw = request.form.get("specificity_level", "").strip()
        try:
            spec = int(spec_raw) if spec_raw else None
        except ValueError:
            spec = spec_raw  # keep the bad value so validation reports it, not a 500
        fields = {
            "member_id": request.form["member_id"],
            "text": request.form["text"].strip(),
            "date": request.form["date"].strip(),
            "venue": request.form["venue"].strip(),
            "source_url": request.form["source_url"].strip(),
            "named_measures": [
                s.strip() for s in request.form.get("named_measures", "").split(",") if s.strip()
            ],
            "specificity_level": spec,
            "stated_position": request.form.get("stated_position") or None,
        }
        # Validate BEFORE the capture — a bad date/specificity must not burn an SPN
        # capture (rate-limited) only to be rejected at save (R-1a/M-6).
        try:
            _validate_capture_fields(fields)
        except ValueError as exc:
            return redirect(url_for("statements_tab", msg=f"Not captured: {exc}", cls="err"))
        try:
            capture = SpnClient().capture(fields["source_url"])
        except SpnError as exc:
            return redirect(url_for("statements_tab", msg=f"Capture failed — not saved: {exc}",
                                    cls="err"))
        token = secrets.token_urlsafe(8)
        drafts[token] = _Draft(fields=fields, capture=capture)
        body = """<h1>Verified capture — review &amp; save</h1>
        <div class="msg ok">Archived:
        <a href="{{ d.capture.archive_url }}">{{ d.capture.archive_url }}</a>
        (captured {{ d.capture.captured_at }})</div>
        <div class="card"><strong>{{ d.fields.member_id }}</strong>
        — {{ d.fields.date }}, {{ d.fields.venue }}
        <blockquote>{{ d.fields.text }}</blockquote>
        Named measures: {{ d.fields.named_measures }}<br>
        Stance: {{ d.fields.stated_position }} · Specificity: {{ d.fields.specificity_level }}</div>
        <form method="post" action="{{ url_for('statements_save') }}">
          <input type="hidden" name="csrf" value="{{ csrf }}">
          <input type="hidden" name="token" value="{{ token }}">
          <button type="submit">Save statement</button></form>"""
        return _render(body, d=drafts[token], token=token, csrf=csrf_token)

    @app.post("/statements/save")
    def statements_save():
        token = request.form["token"]
        draft = drafts.get(token)  # peek — do NOT pop until the save actually succeeds
        if draft is None:
            return redirect(url_for("statements_tab",
                                    msg="No verified capture on file — nothing saved.", cls="err"))
        try:
            stmt = statements.build_statement(capture=draft.capture, **draft.fields)
            path = statements.save_statement(stmt)
        except Exception as exc:  # noqa: BLE001 — any failure must keep the verified capture
            # A rejected save must NOT discard the verified capture (R-1a/M-6): the draft
            # stays on file so the owner can retry without re-capturing (rate-limited SPN).
            return redirect(url_for("statements_tab", msg=f"Not saved: {exc}", cls="err"))
        drafts.pop(token, None)
        return redirect(url_for("statements_tab",
                                msg=f"Saved {path.name} (staged for commit).", cls="ok"))

    @app.route("/absences")
    def absences_tab():
        pending = [
            {"path": p.name, **json.loads(p.read_text(encoding="utf-8"))}
            for p in absences._pending()
        ]
        body = """<h1>Absence approvals</h1>
        {% if msg %}<div class="msg {{ cls }}">{{ msg }}</div>{% endif %}
        {% if not pending %}<p>No pending candidates.</p>{% endif %}
        {% for c in pending %}<div class="card">
          <strong>{{ c.member_id }} ({{ c.hon_name }})</strong> — {{ c.date_issued }}<br>
          Matched roll: {{ c.matched_rollcall_id or 'UNMATCHED — attach by hand' }}<br>
          Source: <a href="{{ c.source_url }}">{{ c.source_url }}</a>
          <blockquote>{{ c.verbatim_text }}</blockquote>
          {% if c.matched_rollcall_id %}
          <form method="post" action="{{ url_for('absences_approve') }}">
            <input type="hidden" name="csrf" value="{{ csrf }}">
            <input type="hidden" name="granule" value="{{ c.granule_id }}">
            <button type="submit">Approve (publish verbatim)</button></form>{% endif %}
        </div>{% endfor %}"""
        return _render(body, pending=pending, csrf=csrf_token,
                       msg=request.args.get("msg"), cls=request.args.get("cls", "ok"))

    @app.post("/absences/approve")
    def absences_approve():
        granule = request.form["granule"]
        path = absences.QUEUE_DIR / f"{granule}.json"
        if not path.exists():
            return redirect(url_for("absences_tab", msg=f"No queue file {granule!r}.", cls="err"))
        written = absences.approve_one(path)
        return redirect(url_for("absences_tab", msg=f"Approved → {written.name}.", cls="ok"))

    return app


def run(argv: list[str] | None = None) -> int:
    """`curate app [--host 127.0.0.1] [--port 5000]`. Binds loopback only."""
    args = sys.argv[1:] if argv is None else argv
    host = "127.0.0.1"
    port = 5000
    if "--host" in args:
        host = args[args.index("--host") + 1]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    try:
        assert_loopback(host)
    except NonLoopbackBindError as exc:
        print(f"curate app: {exc}")
        return 2
    print(f"curate app: serving on http://{host}:{port} (loopback only; Ctrl-C to stop)")
    create_app().run(host=host, port=port, debug=False)
    return 0
