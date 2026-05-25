"""Send notifications to a Teams channel when lead enrichment finishes.

Uses the new Power Automate "Post to channel when webhook received" workflow
(Microsoft retired the legacy Office 365 Connector webhooks in 2025). Payload
is an Adaptive Card, which Teams renders as a rich, formatted message.

All failures are logged but never raised — a notification glitch must not
break the enrichment pipeline.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
API_BASE_URL = os.getenv("API_BASE_URL", "https://tt-production-da10.up.railway.app").rstrip("/")
DEFAULT_TIMEOUT_SECONDS = 10.0


def send_enrichment_complete(
    filename: str,
    rows_processed: int,
    rows_failed: int = 0,
    new_hires: int = 0,
    long_tenured: int = 0,
    file_url: str | None = None,
) -> bool:
    """Post the 'leads enriched' card to Teams.

    Returns True on 2xx, False on any failure (logged, never raised).
    """
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL not set — skipping Teams notification")
        return False

    card = _build_card(
        filename=filename,
        rows_processed=rows_processed,
        rows_failed=rows_failed,
        new_hires=new_hires,
        long_tenured=long_tenured,
        file_url=file_url,
    )

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            r = client.post(TEAMS_WEBHOOK_URL, json=card)
        if r.status_code >= 400:
            logger.error(
                "Teams webhook failed: HTTP %s — %s", r.status_code, r.text[:200]
            )
            return False
        logger.info("Teams notification sent for %s", filename)
        return True
    except httpx.HTTPError as e:
        logger.error("Teams webhook transport error: %s", e)
        return False


def send_upload_skipped(
    filename: str, total_rows: int, skipped: int, file_url: str | None = None,
) -> bool:
    """Post a Teams card when all uploaded rows were duplicates."""
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL not set — skipping Teams notification")
        return False

    body: list[dict] = [
        {
            "type": "TextBlock",
            "text": "📊 Lead enrichment complete",
            "weight": "Bolder",
            "size": "Large",
            "color": "Accent",
        },
        {
            "type": "TextBlock",
            "text": "✅ Your enriched leads are ready!",
            "wrap": True,
            "spacing": "Small",
            "weight": "Bolder",
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "File:", "value": filename},
                {"title": "Total rows:", "value": str(total_rows)},
                {"title": "Skipped (duplicates):", "value": str(skipped)},
            ],
        },
    ]
    if file_url:
        body.append({
            "type": "TextBlock",
            "text": "📂 Download enriched leads:",
            "wrap": True,
            "spacing": "Medium",
            "weight": "Bolder",
        })
        body.append({
            "type": "TextBlock",
            "text": file_url,
            "wrap": True,
            "isSubtle": True,
            "spacing": "None",
        })
    body.append({
        "type": "TextBlock",
        "text": f"📌 All {skipped} leads in this file were already enriched, so we skipped them. You can still ask the bot to **brief** or **lookup** any of these leads.",
        "wrap": True,
        "spacing": "Medium",
        "isSubtle": True,
    })

    card_content: dict = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }
    if file_url:
        card_content["actions"] = [
            {"type": "Action.OpenUrl", "title": "Download enriched .xlsx", "url": file_url}
        ]

    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content,
            }
        ],
    }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            r = client.post(TEAMS_WEBHOOK_URL, json=card)
        if r.status_code >= 400:
            logger.error(
                "Teams webhook failed (skipped): HTTP %s — %s",
                r.status_code, r.text[:200],
            )
            return False
        logger.info("Teams skipped-upload notification sent for %s", filename)
        return True
    except httpx.HTTPError as e:
        logger.error("Teams webhook transport error (skipped): %s", e)
        return False


def _build_card(
    filename: str,
    rows_processed: int,
    rows_failed: int,
    new_hires: int,
    long_tenured: int,
    file_url: str | None,
) -> dict:
    """Adaptive Card payload — Teams' rich message format."""
    facts = [{"title": "File:", "value": filename}]
    facts.append({"title": "Rows enriched:", "value": str(rows_processed)})
    if rows_failed:
        facts.append({"title": "Rows failed:", "value": str(rows_failed)})
    if new_hires:
        facts.append({"title": "🆕 New hires:", "value": str(new_hires)})
    if long_tenured:
        facts.append({"title": "📅 Long-tenured:", "value": str(long_tenured)})

    body: list[dict] = [
        {
            "type": "TextBlock",
            "text": "📊 Lead enrichment complete",
            "weight": "Bolder",
            "size": "Large",
            "color": "Accent",
        },
        {
            "type": "TextBlock",
            "text": "✅ Your enriched leads are ready!",
            "wrap": True,
            "spacing": "Small",
            "weight": "Bolder",
        },
        {"type": "FactSet", "facts": facts},
        {
            "type": "TextBlock",
            "text": "🤖 You can now ask the bot to **brief** or **lookup** any of these leads.",
            "wrap": True,
            "spacing": "Medium",
        },
    ]

    if file_url:
        body.append(
            {
                "type": "TextBlock",
                "text": "📂 Download enriched leads:",
                "wrap": True,
                "spacing": "Medium",
                "weight": "Bolder",
            }
        )
        body.append(
            {
                "type": "TextBlock",
                "text": file_url,
                "wrap": True,
                "isSubtle": True,
                "spacing": "None",
            }
        )

    actions: list[dict] = []
    if file_url:
        actions.append(
            {"type": "Action.OpenUrl", "title": "Download enriched .xlsx", "url": file_url}
        )

    card_content: dict = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }
    if actions:
        card_content["actions"] = actions

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content,
            }
        ],
    }


def build_public_url(source_file: str, bucket: str = "uploaded-leads") -> str | None:
    """Reconstruct the Supabase Storage public URL for the raw uploaded file.

    Returns None if SUPABASE_URL isn't set.
    """
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not supabase_url or not source_file:
        return None
    return f"{supabase_url}/storage/v1/object/public/{bucket}/{source_file}"


def build_download_url(source_file: str) -> str | None:
    """URL to the /leads/download endpoint filtered by source_file.

    This is what we link from the Teams card so Matt downloads a freshly
    generated xlsx containing the *enriched* rows for his upload — not the
    raw file he originally uploaded.
    """
    if not source_file or not API_BASE_URL:
        return None
    from urllib.parse import quote
    return f"{API_BASE_URL}/leads/download?source_file={quote(source_file)}"
