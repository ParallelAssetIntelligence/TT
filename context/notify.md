Teams Webhook Implementation — Step by Step
⚠️ Critical Heads-Up First
Microsoft retired the old "Incoming Webhook" connector in early 2025. You can't create new ones anymore. The replacement is Power Automate Workflows — same idea, different setup. I'll show you the new way.

🗺️ The Plan (30 minutes total)

1. Create Workflow in Teams        (10 min — one-time, in browser)
2. Copy webhook URL → .env         (1 min)
3. Add teams_notifier.py service   (5 min — copy/paste code)
4. Wire into enrich_row_range      (5 min)
5. Test                            (5 min)
STEP 1: Create the Workflow in Teams (Browser)
A. Pick the channel
Open Teams (desktop or web)
Go to the channel where Matt should get notifications (or create a new one called "Lead Enrichment")
Hover over the channel name → ⋯ (three dots) → Workflows
B. Create the workflow
In the search box, type: "Post to a channel when a webhook request is received"
Click that template → Next
Pick:
Team: Tustin Group (or whatever)
Channel: Lead Enrichment
Click Add workflow
C. Copy the URL
Teams shows you a webhook URL like:

https://prod-xx.westus.logic.azure.com:443/workflows/abc.../triggers/manual/...
Copy it — you only see it once. Save it somewhere safe.
Click Done
STEP 2: Add to .env
Read c:\Users\harsh\OneDrive\Dyota\Tustin\.env
Add this line to your .env:


TEAMS_WEBHOOK_URL=https://prod-xx.westus.logic.azure.com:443/workflows/...
(Paste your actual URL from Step 1)

STEP 3: Create the Teams Notifier Service
Create the new file app/services/teams_notifier.py:


"""Send notifications to a Teams channel via Power Automate workflow webhook.

Microsoft retired the legacy Office 365 Connector webhooks in 2025.
This module uses the newer "Post to channel when webhook received" workflow,
which expects an Adaptive Card payload at /workflows/.../triggers/manual/...
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
DEFAULT_TIMEOUT = 10.0


def send_enrichment_complete(
    filename: str,
    rows_processed: int,
    rows_failed: int = 0,
    new_hires: int = 0,
    long_tenured: int = 0,
    file_link: str | None = None,
) -> bool:
    """Post a rich card to Teams when a lead file finishes enrichment.

    Returns True on 2xx, False on any failure (logged, never raised — we don't
    want a notification glitch to break the enrichment pipeline).
    """
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL not set — skipping Teams notification")
        return False

    card = _build_adaptive_card(
        filename=filename,
        rows_processed=rows_processed,
        rows_failed=rows_failed,
        new_hires=new_hires,
        long_tenured=long_tenured,
        file_link=file_link,
    )

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            r = client.post(TEAMS_WEBHOOK_URL, json=card)
        if r.status_code >= 400:
            logger.error(f"Teams webhook failed: HTTP {r.status_code} — {r.text[:200]}")
            return False
        logger.info(f"Teams notification sent for {filename}")
        return True
    except httpx.HTTPError as e:
        logger.error(f"Teams webhook transport error: {e}")
        return False


def send_simple_message(text: str) -> bool:
    """Send a plain text message — useful for errors or quick pings."""
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL not set — skipping Teams notification")
        return False

    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [{"type": "TextBlock", "text": text, "wrap": True}],
            },
        }],
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            r = client.post(TEAMS_WEBHOOK_URL, json=payload)
        return r.status_code < 400
    except httpx.HTTPError as e:
        logger.error(f"Teams webhook error: {e}")
        return False


def _build_adaptive_card(
    filename: str,
    rows_processed: int,
    rows_failed: int,
    new_hires: int,
    long_tenured: int,
    file_link: str | None,
) -> dict:
    """Build an Adaptive Card payload (Teams' rich message format)."""
    facts = [
        {"title": "File:", "value": filename},
        {"title": "Rows enriched:", "value": str(rows_processed)},
    ]
    if rows_failed:
        facts.append({"title": "Rows failed:", "value": str(rows_failed)})
    if new_hires:
        facts.append({"title": "🆕 New hires flagged:", "value": str(new_hires)})
    if long_tenured:
        facts.append({"title": "📅 Long-tenured:", "value": str(long_tenured)})

    body = [
        {
            "type": "TextBlock",
            "text": "📊 Lead enrichment complete",
            "weight": "Bolder",
            "size": "Large",
            "color": "Accent",
        },
        {
            "type": "TextBlock",
            "text": f"Your enriched leads are ready, Matt.",
            "wrap": True,
            "spacing": "Small",
        },
        {"type": "FactSet", "facts": facts},
    ]

    actions = []
    if file_link:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "Open file",
            "url": file_link,
        })

    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body,
                "actions": actions,
            },
        }],
    }
STEP 4: Wire It Into the Enrichment Pipeline
Edit app/routes/leads.py — after enrichment completes, send the Teams ping:


# Add to imports at top
from app.services.teams_notifier import send_enrichment_complete

# In the enrich_row endpoint, after `result = enrich_row_range(...)`:
@router.post("/enrich-row")
async def enrich_row(rows: str = Query(...)):
    try:
        start, end = parse_row_range(rows)
        result = enrich_row_range(DEFAULT_LEADS_FILE, start, end)
    except # ... existing error handling ...

    # Count signal tags for the notification
    new_hires = sum(
        1 for r in result["results"]
        if r["enriched"].get("Enriched_Tenure_Label") == "NEW_HIRE"
    )
    long_tenured = sum(
        1 for r in result["results"]
        if r["enriched"].get("Enriched_Tenure_Label") == "LONG_TENURED"
    )

    # Fire-and-forget Teams notification
    send_enrichment_complete(
        filename=DEFAULT_LEADS_FILE,
        rows_processed=result["rows_processed"],
        rows_failed=result["rows_failed"],
        new_hires=new_hires,
        long_tenured=long_tenured,
    )

    return {"file": DEFAULT_LEADS_FILE, "rows": rows, **result}
STEP 5: Test It
Quick smoke test (no enrichment, just verify the webhook works):

cd "c:/Users/harsh/OneDrive/Dyota/Tustin"
venv/Scripts/python.exe -c "
from dotenv import load_dotenv
load_dotenv()
from app.services.teams_notifier import send_simple_message, send_enrichment_complete

# Test 1: simple text
print('Simple message:', send_simple_message('Hello Matt — Tustin Co-Pilot is online ✅'))

# Test 2: full rich card
print('Rich card:', send_enrichment_complete(
    filename='Tustin Group Lead Gen list.xlsx',
    rows_processed=700,
    rows_failed=3,
    new_hires=142,
    long_tenured=89,
    file_link='https://example.com/file.xlsx',
))
"
You should see two messages appear in your Teams channel within ~3 seconds.

📱 What Matt Will See
The Adaptive Card renders like this in Teams:


┌────────────────────────────────────────┐
│  📊 Lead enrichment complete           │
│                                        │
│  Your enriched leads are ready, Matt.  │
│                                        │
│  File:              leads_week22.xlsx  │
│  Rows enriched:     700                │
│  🆕 New hires:      142                │
│  📅 Long-tenured:   89                 │
│                                        │
│  [ Open file ]                         │
└────────────────────────────────────────┘
🐛 Common Issues & Fixes
Problem	Fix
HTTP 400 / "InvalidWorkflowRun"	You're sending old "MessageCard" format — must use Adaptive Card JSON (the code above does)
HTTP 404	Webhook URL is wrong or workflow was deleted — recreate in Teams
No error but no message appears	Check the Workflow run history at flow.microsoft.com → My Flows
"Workflows" option missing in Teams	Your org's M365 admin disabled Power Automate — ask IT to enable
Card looks broken	Adaptive Card version must be "1.4" or lower for Teams
🎁 Bonus: Add the file_link Later
Right now the [Open file] button only appears if you pass a file_link. When you implement SharePoint upload (Step 4 Part A), pass the SharePoint URL:


sharepoint_url = upload_to_sharepoint(file_bytes, filename)
send_enrichment_complete(..., file_link=sharepoint_url)
✅ Want Me To Implement It?
I can do Steps 3–5 right now (code + wiring + test). You just need to:

Create the workflow in Teams (Step 1)
Paste the webhook URL into .env
Tell me when done — I'll wire the code and run the test
OR if you want, I can write all the code first (with a stub URL) so it's ready to go the moment you have the webhook URL. Just say the word.

