"""The post-call summary email.

This is the product's #1 sales artifact (docs/phases.md Phase 4): for most PMs it is the
*only* PropTalk surface they ever look at, and it arrives while they're deciding whether
this thing is worth $399/mo. It should read like a good assistant's handoff note - the
outcome first, the money detail next, the proof underneath.

Deliberately old-fashioned markup: 600px tables, inline styles, no flex/grid/webfonts.
Gmail strips <style> blocks and Outlook renders through Word, so anything cleverer than
this silently breaks in exactly the inboxes we're selling to.

Every interpolated value goes through _esc(): transcripts and messages are caller-supplied
text, and this is HTML we email to a client.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from app.config import SUMMARY_TRANSCRIPT_MAX_TURNS

# One palette, used by both the badges and the cards, so the email reads as one system.
INK = "#0f172a"
MUTED = "#64748b"
FAINT = "#94a3b8"
BORDER = "#e2e8f0"
PAGE_BG = "#eef2f6"
CARD_BG = "#ffffff"
BRAND = "#0f766e"

# outcome -> (badge label, badge text colour, badge background, headline verb)
_OUTCOME_STYLES = {
    "escalated": ("Emergency escalated", "#991b1b", "#fee2e2"),
    "tour_booked": ("Tour booked", "#065f46", "#d1fae5"),
    "ticket_created": ("Maintenance ticket", "#92400e", "#fef3c7"),
    "message_taken": ("Message taken", "#1e40af", "#dbeafe"),
    "info_only": ("Answered", "#334155", "#e2e8f0"),
}


def _esc(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _fmt_local(dt: datetime | None, tz_name: str) -> str:
    """Store UTC, speak client-local (docs/rules.md SS4)."""
    if dt is None:
        return "—"
    local = dt.astimezone(ZoneInfo(tz_name))
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local.strftime('%a, %b %d')} at {hour}:{local.strftime('%M %p %Z')}"


def _fmt_phone(raw: str | None) -> str:
    """US-pretty when it can be, untouched when it can't - never mangled."""
    if not raw:
        return "—"
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "—"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def _fmt_money(amount: int | None) -> str:
    return f"${amount:,}/mo" if amount else "—"


def _row(label: str, value: str, *, strong: bool = False) -> str:
    weight = "600" if strong else "400"
    return f"""
      <tr>
        <td style="padding:6px 0;font-size:13px;color:{MUTED};white-space:nowrap;vertical-align:top;width:130px;">{_esc(label)}</td>
        <td style="padding:6px 0;font-size:14px;color:{INK};font-weight:{weight};vertical-align:top;">{value}</td>
      </tr>"""


def _card(*, accent: str, title: str, rows_html: str, note: str | None = None) -> str:
    note_html = (
        f"""<tr><td colspan="2" style="padding-top:10px;font-size:12px;color:{MUTED};
             line-height:1.5;">{note}</td></tr>"""
        if note
        else ""
    )
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="border:1px solid {BORDER};border-left:3px solid {accent};border-radius:6px;
                  background:#fbfdfe;margin:0 0 14px 0;">
      <tr><td style="padding:16px 18px;">
        <div style="font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
                    color:{accent};padding-bottom:8px;">{_esc(title)}</div>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          {rows_html}
          {note_html}
        </table>
      </td></tr>
    </table>"""


def _booking_cards(bookings: list[dict], tz_name: str) -> str:
    out = []
    for b in bookings:
        rows = (
            _row("Unit", _esc(b.get("label")), strong=True)
            + _row("When", _esc(_fmt_local(b.get("slot_start"), tz_name)), strong=True)
            + _row("Prospect", _esc(b.get("prospect_name")))
            + _row(
                "Phone",
                f'<a href="tel:{_esc(b.get("prospect_phone"))}" style="color:{BRAND};'
                f'text-decoration:none;">{_esc(_fmt_phone(b.get("prospect_phone")))}</a>',
            )
            + _row("Address", _esc(b.get("address")))
            + _row("Rent", _esc(_fmt_money(b.get("rent"))))
            + _row("Texts OK?", "Yes — consent given on call" if b.get("sms_consent") else "No consent given")
        )
        # A booking with no Cal.com id is real but invisible to their calendar. Say so
        # plainly - a silent gap here is how you lose a client's trust permanently.
        note = (
            None
            if b.get("cal_booking_id")
            else "⚠️ This tour is <strong>not on your Cal.com calendar</strong> — the calendar "
            "didn't respond when we booked it. The tour is confirmed with the prospect; "
            "please add it manually."
        )
        # Titled "Tour details", not "Tour booked" - the badge above already said that,
        # and an email that repeats itself reads like a template rather than an assistant.
        out.append(_card(accent="#047857", title="Tour details", rows_html=rows, note=note))
    return "".join(out)


def _emergency_cards(items: list[dict]) -> str:
    out = []
    for t in items:
        rows = (
            _row("Unit", _esc(t.get("unit")), strong=True)
            + _row("Issue", _esc(t.get("description")), strong=True)
            + _row(
                "Call back",
                f'<a href="tel:{_esc(t.get("callback_number"))}" style="color:{BRAND};'
                f'text-decoration:none;">{_esc(_fmt_phone(t.get("callback_number")))}</a>',
            )
        )
        out.append(
            _card(
                accent="#b91c1c",
                title="Emergency — action needed",
                rows_html=rows,
                note="Your on-call contact was alerted during the call.",
            )
        )
    return "".join(out)


def _ticket_cards(items: list[dict]) -> str:
    out = []
    for t in items:
        entry = t.get("permission_to_enter")
        rows = (
            _row("Unit", _esc(t.get("unit")), strong=True)
            + _row("Type", _esc(t.get("issue_type")))
            + _row("Details", _esc(t.get("description")))
            + _row(
                "Call back",
                f'<a href="tel:{_esc(t.get("callback_number"))}" style="color:{BRAND};'
                f'text-decoration:none;">{_esc(_fmt_phone(t.get("callback_number")))}</a>',
            )
            + _row(
                "Entry permission",
                "Granted" if entry else ("Not granted" if entry is False else "Not asked"),
            )
        )
        out.append(_card(accent="#b45309", title="Maintenance request", rows_html=rows))
    return "".join(out)


def _message_cards(items: list[dict]) -> str:
    out = []
    for m in items:
        rows = (
            _row("From", _esc(m.get("caller_name")), strong=True)
            + _row(
                "Call back",
                f'<a href="tel:{_esc(m.get("callback_number"))}" style="color:{BRAND};'
                f'text-decoration:none;">{_esc(_fmt_phone(m.get("callback_number")))}</a>',
            )
            + _row("About", _esc(m.get("reason")))
            + _row("Message", _esc(m.get("body")))
        )
        out.append(_card(accent="#1d4ed8", title="Message", rows_html=rows))
    return "".join(out)


def _transcript_html(transcript: str | None) -> str:
    """Retell hands us a 'Agent: ...\\nUser: ...' string. Rendered as a real back-and-forth
    because the transcript is what convinces a sceptical PM the call actually went well."""
    if not transcript:
        return ""
    lines = [ln.strip() for ln in transcript.splitlines() if ln.strip()]
    truncated = len(lines) > SUMMARY_TRANSCRIPT_MAX_TURNS
    lines = lines[:SUMMARY_TRANSCRIPT_MAX_TURNS]

    rows = []
    for line in lines:
        speaker, _, text = line.partition(":")
        if not text:
            speaker, text = "", line
        is_agent = speaker.strip().lower() in ("agent", "assistant", "ai")
        colour = BRAND if is_agent else INK
        rows.append(
            f"""
        <tr>
          <td style="padding:5px 10px 5px 0;font-size:11px;font-weight:700;color:{colour};
                     white-space:nowrap;vertical-align:top;width:52px;text-transform:uppercase;
                     letter-spacing:.04em;">{_esc(speaker.strip() or "—")}</td>
          <td style="padding:5px 0;font-size:13px;color:#334155;line-height:1.55;
                     vertical-align:top;">{_esc(text.strip())}</td>
        </tr>"""
        )
    more = (
        f'<div style="padding-top:10px;font-size:12px;color:{FAINT};">'
        f"Transcript trimmed — open the recording for the full call.</div>"
        if truncated
        else ""
    )
    return f"""
      <div style="font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
                  color:{FAINT};padding:26px 0 10px 0;">Transcript</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border-top:1px solid {BORDER};padding-top:8px;">
        {"".join(rows)}
      </table>
      {more}"""


def render_summary_email(
    *,
    client: dict,
    call: dict,
    outcomes: dict,
    outcome: str,
    summary_text: str | None,
) -> tuple[str, str, str]:
    """Returns (subject, html, plain_text)."""
    tz_name = client.get("timezone") or "America/New_York"
    company = client.get("company_name") or "your properties"
    agent_name = client.get("agent_name") or "Your AI receptionist"
    label, badge_fg, badge_bg = _OUTCOME_STYLES.get(outcome, _OUTCOME_STYLES["info_only"])

    bookings = outcomes.get("bookings") or []
    emergencies = outcomes.get("emergencies") or []
    tickets = outcomes.get("tickets") or []
    msgs = outcomes.get("messages") or []

    # The subject line is most of the value: it should be readable on a lock screen,
    # without opening anything.
    if emergencies:
        subject = f"🚨 Emergency at {emergencies[0].get('unit') or 'a unit'} — {company}"
    elif bookings:
        b = bookings[0]
        subject = f"Tour booked — {b.get('label') or 'a unit'}, {_fmt_local(b.get('slot_start'), tz_name)}"
    elif tickets:
        subject = f"Maintenance request — {tickets[0].get('unit') or 'a unit'} ({company})"
    elif msgs:
        subject = f"Message from {msgs[0].get('caller_name') or 'a caller'} — {company}"
    else:
        subject = f"Call answered — {company}"

    started = _fmt_local(call.get("started_at"), tz_name)
    duration = _fmt_duration(call.get("duration_sec"))
    caller = _fmt_phone(call.get("from_number"))

    cards = (
        _emergency_cards(emergencies)
        + _booking_cards(bookings, tz_name)
        + _ticket_cards(tickets)
        + _message_cards(msgs)
    )
    if not cards:
        cards = _card(
            accent=FAINT,
            title="No action needed",
            rows_html=_row("Result", "Caller's questions were answered — nothing to follow up."),
        )

    summary_html = (
        f"""
      <div style="font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
                  color:{FAINT};padding:12px 0 8px 0;">What happened</div>
      <div style="font-size:14px;color:#334155;line-height:1.65;">{_esc(summary_text)}</div>"""
        if summary_text
        else ""
    )

    recording_url = call.get("recording_url")
    recording_html = (
        f"""
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:22px 0 0 0;">
        <tr><td style="background:{BRAND};border-radius:6px;">
          <a href="{_esc(recording_url)}"
             style="display:inline-block;padding:11px 22px;font-size:14px;font-weight:600;
                    color:#ffffff;text-decoration:none;">▶ Listen to the call</a>
        </td></tr>
      </table>"""
        if recording_url
        else ""
    )

    html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:{PAGE_BG};margin:0;padding:0;">
  <tr><td align="center" style="padding:28px 12px;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">
      {_esc(label)} · {_esc(started)} · {_esc(duration)}
    </div>
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
           style="width:600px;max-width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
                  Roboto,Helvetica,Arial,sans-serif;">

      <tr><td style="padding:0 4px 14px 4px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="font-size:14px;font-weight:700;color:{BRAND};letter-spacing:-.01em;">PropTalk</td>
          <td align="right" style="font-size:12px;color:{MUTED};">{_esc(company)}</td>
        </tr></table>
      </td></tr>

      <tr><td style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:26px 26px 28px 26px;">

        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="background:{badge_bg};border-radius:20px;padding:5px 12px;font-size:11px;
                     font-weight:700;color:{badge_fg};letter-spacing:.06em;text-transform:uppercase;">
            {_esc(label)}</td>
        </tr></table>

        <div style="font-size:21px;font-weight:700;color:{INK};line-height:1.35;padding:14px 0 6px 0;
                    letter-spacing:-.01em;">
          {_esc(agent_name)} answered a call for {_esc(company)}
        </div>
        <div style="font-size:13px;color:{MUTED};padding-bottom:20px;">
          {_esc(started)} &nbsp;·&nbsp; {_esc(duration)} &nbsp;·&nbsp; from {_esc(caller)}
        </div>

        {cards}
        {summary_html}
        {recording_html}
        {_transcript_html(call.get("transcript"))}

      </td></tr>

      <tr><td style="padding:16px 4px 0 4px;font-size:11px;color:{FAINT};line-height:1.6;">
        Answered by PropTalk, your AI leasing line — every call, first ring, 24/7.<br>
        Calls are recorded and disclosed to callers at the start of each call.
      </td></tr>

    </table>
  </td></tr>
</table>"""

    text = _render_text(
        company=company,
        agent_name=agent_name,
        label=label,
        started=started,
        duration=duration,
        caller=caller,
        bookings=bookings,
        emergencies=emergencies,
        tickets=tickets,
        msgs=msgs,
        summary_text=summary_text,
        recording_url=recording_url,
        tz_name=tz_name,
    )
    return subject, html, text


def _render_text(**kw) -> str:
    """Plain-text alternative. Not decoration: a text part measurably helps deliverability,
    and it's what a smartwatch/notification preview actually shows."""
    lines = [
        f"{kw['label'].upper()} — {kw['company']}",
        f"{kw['agent_name']} answered a call · {kw['started']} · {kw['duration']} · from {kw['caller']}",
        "",
    ]
    for t in kw["emergencies"]:
        lines += [
            "EMERGENCY — ACTION NEEDED",
            f"  Unit: {t.get('unit')}",
            f"  Issue: {t.get('description')}",
            f"  Call back: {_fmt_phone(t.get('callback_number'))}",
            "  Your on-call contact was alerted during the call.",
            "",
        ]
    for b in kw["bookings"]:
        lines += [
            "TOUR BOOKED",
            f"  Unit: {b.get('label')}",
            f"  When: {_fmt_local(b.get('slot_start'), kw['tz_name'])}",
            f"  Prospect: {b.get('prospect_name')} · {_fmt_phone(b.get('prospect_phone'))}",
            f"  Rent: {_fmt_money(b.get('rent'))}",
            f"  Texts OK? {'Yes' if b.get('sms_consent') else 'No'}",
        ]
        if not b.get("cal_booking_id"):
            lines.append("  WARNING: not on your Cal.com calendar — please add it manually.")
        lines.append("")
    for t in kw["tickets"]:
        lines += [
            "MAINTENANCE REQUEST",
            f"  Unit: {t.get('unit')} · {t.get('issue_type')}",
            f"  Details: {t.get('description')}",
            f"  Call back: {_fmt_phone(t.get('callback_number'))}",
            "",
        ]
    for m in kw["msgs"]:
        lines += [
            "MESSAGE",
            f"  From: {m.get('caller_name')} · {_fmt_phone(m.get('callback_number'))}",
            f"  About: {m.get('reason')}",
            f"  {m.get('body')}",
            "",
        ]
    if kw["summary_text"]:
        lines += ["WHAT HAPPENED", kw["summary_text"], ""]
    if kw["recording_url"]:
        lines += [f"Listen: {kw['recording_url']}", ""]
    lines.append("Answered by PropTalk, your AI leasing line.")
    return "\n".join(lines)
