"""Send enrichment-complete notifications via email (AgentMail).

Fires from leads_writer._notify_batch_complete() alongside the Teams card.
Best-effort: never raises — a mail failure must not break the enrichment
pipeline. Configure with three env vars:

  AGENTMAIL_API_KEY       - bearer token from console.agentmail.to
  AGENTMAIL_INBOX         - sender inbox you provisioned, e.g. tustin@agentmail.to
                            (also acts as the From address)
  NOTIFICATION_TO_EMAIL   - comma-separated recipients (any addresses — AgentMail
                            doesn't lock you to the account holder)

Endpoint: POST https://api.agentmail.to/inboxes/{inbox}/messages/send
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

AGENTMAIL_BASE_URL = "https://api.agentmail.to"
AGENTMAIL_API_KEY = os.getenv("AGENTMAIL_API_KEY", "")
AGENTMAIL_INBOX = os.getenv("AGENTMAIL_INBOX", "")
TO_EMAILS = [
    e.strip()
    for e in os.getenv("NOTIFICATION_TO_EMAIL", "").split(",")
    if e.strip()
]
SEND_TIMEOUT_SECONDS = 15.0


def send_enrichment_complete(
    filename: str,
    rows_processed: int,
    rows_failed: int = 0,
    new_hires: int = 0,
    long_tenured: int = 0,
    file_url: str | None = None,
) -> bool:
    """Email the 'leads enriched' summary. Returns True on success."""
    if not AGENTMAIL_API_KEY or not AGENTMAIL_INBOX:
        logger.warning(
            "AgentMail not configured (need AGENTMAIL_API_KEY + AGENTMAIL_INBOX) "
            "— skipping email notification"
        )
        return False
    if not TO_EMAILS:
        logger.warning("NOTIFICATION_TO_EMAIL not set — skipping email notification")
        return False

    subject = f"✅ Enrichment done — {filename} ({rows_processed} leads)"
    html = _build_html(
        filename=filename,
        rows_processed=rows_processed,
        rows_failed=rows_failed,
        new_hires=new_hires,
        long_tenured=long_tenured,
        file_url=file_url,
    )

    url = f"{AGENTMAIL_BASE_URL}/inboxes/{AGENTMAIL_INBOX}/messages/send"
    # AgentMail accepts a string for one recipient OR a list for many — list is
    # always safe.
    payload = {
        "to": TO_EMAILS,
        "subject": subject,
        "html": html,
        "text": _build_plaintext(
            filename, rows_processed, rows_failed,
            new_hires, long_tenured, file_url,
        ),
    }
    headers = {
        "Authorization": f"Bearer {AGENTMAIL_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=SEND_TIMEOUT_SECONDS) as client:
            r = client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            logger.error(
                "AgentMail send failed: HTTP %s — %s", r.status_code, r.text[:300]
            )
            return False
        logger.info(
            "Email notification sent for %s to %s", filename, TO_EMAILS
        )
        return True
    except httpx.HTTPError as e:
        logger.error("AgentMail transport error: %s", e)
        return False


def _build_html(
    filename: str,
    rows_processed: int,
    rows_failed: int,
    new_hires: int,
    long_tenured: int,
    file_url: str | None,
) -> str:
    """Render the summary as a plain, mobile-friendly HTML email."""
    rows = [
        ("File", filename),
        ("Rows enriched", str(rows_processed)),
    ]
    if rows_failed:
        rows.append(("Rows failed", str(rows_failed)))
    if new_hires:
        rows.append(("🆕 New hires", str(new_hires)))
    if long_tenured:
        rows.append(("📅 Long-tenured", str(long_tenured)))

    facts_html = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:#666"><b>{label}:</b></td>'
        f'<td style="padding:6px 0">{value}</td></tr>'
        for label, value in rows
    )

    download_btn = ""
    if file_url:
        download_btn = (
            f'<p style="margin:24px 0">'
            f'<a href="{file_url}" '
            f'style="background:#0078d4;color:#fff;padding:12px 24px;'
            f'border-radius:6px;text-decoration:none;display:inline-block;'
            f'font-weight:600">📂 Download enriched .xlsx</a>'
            f'</p>'
        )

    return f"""\
<!DOCTYPE html>
<html><body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;
                   max-width:560px;margin:0 auto;padding:24px;color:#222">
  <h2 style="color:#0078d4;margin:0 0 8px">📊 Lead enrichment complete</h2>
  <p style="font-size:15px;margin:0 0 16px"><b>✅ Your enriched leads are ready, Matt.</b></p>
  <table style="border-collapse:collapse;font-size:14px">{facts_html}</table>
  {download_btn}
  <p style="color:#666;font-size:13px;margin-top:24px;
            border-top:1px solid #eee;padding-top:16px">
    🤖 You can now ask the bot to <b>brief</b> or <b>lookup</b> any of these leads.
  </p>
</body></html>"""


def _build_plaintext(
    filename: str,
    rows_processed: int,
    rows_failed: int,
    new_hires: int,
    long_tenured: int,
    file_url: str | None,
) -> str:
    """Plain-text fallback for clients that don't render HTML."""
    lines = [
        "Lead enrichment complete.",
        "",
        f"File: {filename}",
        f"Rows enriched: {rows_processed}",
    ]
    if rows_failed:
        lines.append(f"Rows failed: {rows_failed}")
    if new_hires:
        lines.append(f"New hires: {new_hires}")
    if long_tenured:
        lines.append(f"Long-tenured: {long_tenured}")
    if file_url:
        lines.extend(["", f"Download: {file_url}"])
    return "\n".join(lines)
