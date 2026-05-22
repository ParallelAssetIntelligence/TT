# Copilot Studio — Agent Setup Guide

End-to-end setup for the Tustin CoPilot agent at <https://copilotstudio.microsoft.com>.

Two things to configure:

1. **Agent instructions** — paste-in text that tells the LLM how to route messages and format output.
2. **Custom connector / Tools** — import `copilot_openapi.json` so the agent can call `brief`, `lookup`, `respond`, and `upload-from-url`.

> **Upload flow has changed.** Matt now pastes a public xlsx URL (Google Sheets, Drive, Dropbox, SharePoint, OneDrive, or any direct HTTPS link) in chat. The LLM calls `UploadLeadsFromUrl`, the file is downloaded server-side into the `uploaded-leads` bucket, and the storage webhook auto-inserts + enriches the rows. No Power Automate flow, no file-attachment Topic, no in-chat base64 dance. The legacy `/copilot/upload-file` endpoint is no longer registered as a tool.

---

## 1️⃣ Agent Instructions (paste-in)

Open the agent → **Settings** → **Generative AI** → **Instructions** (or the top-level "Agent instructions" panel depending on UI version). Paste everything between the triple backticks:

```
═══════════════════════════════════════════════════════
RESPONSE FORMAT — How to display tool results
═══════════════════════════════════════════════════════

When you receive results from any tool (brief, lookup, or respond), display ALL fields from the response in a clean, easy-to-read format. Use this approach:

- Show each field on its own line
- Label each field with its name (bold)
- For arrays (lists), show each item on a new numbered line
- Skip any fields that are empty or null
- Use line breaks between major sections
- Don't paraphrase the data — show it exactly as returned
- No closing summaries, no "Anything else?" — just the data


ROUTING RULES:
- If user mentions a person's NAME and asks for info → brief tool
- If user types what someone SAID → respond tool
- If user explicitly says "lookup" or "find" → lookup tool
- If user pastes / shares a URL pointing to an .xlsx, .xls, or Google Sheet (Google Drive, Google Sheets, Dropbox, OneDrive, SharePoint, or any direct HTTPS link), OR says "enrich this URL", "upload leads from this link", "process this file" with a URL → call upload-from-url tool. Show the response fields (status, filename, columns_detected, rows_detected, storage_url) verbatim — do NOT add commentary.
- If user attaches a file (no URL) → tell them: "Please share a public link to the file instead. I can fetch from Google Sheets/Drive, Dropbox, OneDrive, or SharePoint links."
- If ambiguous → ask a clarifying question
```

---

## 2️⃣ Tools (custom connector)

Import `context/copilot_openapi.json` so the LLM has access to the right actions.

### Which actions the LLM should see

| Action            | OperationId           | When the LLM calls it                                                          |
|-------------------|-----------------------|--------------------------------------------------------------------------------|
| brief             | `GetPreCallBrief`     | "tell me about X", "prep me for X", bare name                                  |
| lookup            | `LookupLeadByName`    | "find X", "lookup X"                                                           |
| respond           | `GetLiveSuggestion`   | `<prospect just said …>`                                                       |
| upload-from-url   | `UploadLeadsFromUrl`  | User pastes a Google Sheets / Drive / Dropbox / OneDrive / SharePoint URL      |

> **Why `/copilot/upload-file` is no longer in this spec:** Matt switched to a URL-paste flow (`upload-from-url`), so the legacy base64 upload tool is unused. The Python endpoint still exists for backward compatibility but is intentionally not advertised to the LLM. The storage webhook (`/webhooks/storage-uploaded`) handles the rest of the pipeline automatically — parse, insert, enrich, notify Teams.

### Import steps

1. Agent → **Tools** → **+ Add a tool** → **New tool** → **Custom connector** → **New custom connector**.
2. Power Automate opens → **Custom connectors** → **+ New custom connector** → **Import an OpenAPI file**.
3. Upload `context/copilot_openapi.json`. Name it `Tustin CoPilot API`.
4. **Security:** No authentication (the endpoints are public; gate at the network layer if needed later).
5. **Create connector** → switch to **Test** → exercise each action with the sample payloads from the spec.
6. Back in Copilot Studio → **Tools** → **+ Add a tool** → pick `Tustin CoPilot API` → enable **brief**, **lookup**, **respond**, **upload-from-url**.

---

## 3️⃣ Upload flow (URL-based, fully LLM-driven)

There is **no Topic and no Power Automate flow** for uploads anymore. The LLM detects when the user pastes an xlsx / Google Sheet URL and calls `upload-from-url` directly.

```
Matt:    https://docs.google.com/spreadsheets/d/1aB.../edit
  ↓
LLM detects URL → calls UploadLeadsFromUrl with { url: "..." }
  ↓
Backend downloads + parses + stages file in `uploaded-leads` bucket
  ↓
Returns: { status: "✅ success", filename, columns_detected, rows_detected, storage_url }
  ↓
Storage webhook fires → leads inserted → background SerpAPI/LLM enrichment
  ↓
Teams card posted to the "Lead Enrichment" channel when enrichment finishes
```

### What the LLM shows back to Matt

After the connector returns, the agent displays the response fields verbatim:

```
Status: ✅ success
Filename: test_leads.xlsx
Columns detected: 15
Rows detected: 5
Storage URL: https://wzhqsmaunimgvowkdegl.supabase.co/storage/v1/object/public/uploaded-leads/20260521_220636_test_leads.xlsx
```

A separate Teams card lands ~30-60 seconds later with the **"Download enriched .xlsx"** button. Matt clicks it to grab the filtered, fully-enriched spreadsheet from `/leads/download?source_file=...`.

### Sharing requirements (tell Matt this)

For the URL to actually download the file, the share permission must be:

| Source | Required setting |
|---|---|
| Google Sheets / Drive | "Anyone with the link – Viewer" |
| Dropbox | Default public share works |
| SharePoint / OneDrive Business | "Anyone with the link" (not "People in your organization") |
| Direct HTTPS xlsx URL | The URL just needs to return the file (no login redirect) |

---

## 4️⃣ End-to-end test

In the Copilot Studio test pane (or Teams) after publishing the agent:

| Test | Steps | Expected |
|------|-------|----------|
| Happy path (URL paste) | Paste a Google Sheets share link | Bot calls `upload-from-url` → returns `✅ success`, filename, rows_detected. Supabase `uploaded-leads` bucket gets a new object. Teams card lands ~30-60s later. |
| Restricted share | Paste a Sheets URL set to "Restricted" | Bot returns a 400 — the URL must be public. |
| Non-Excel URL | Paste a link to a PDF or random page | Bot returns a 400 — only .xlsx/.xls or Google Sheets are accepted. |
| Lookup works | Type `look up Vinnie Corsi` | LLM calls the `lookup` tool, renders all 30 fields including `enrichment_status`. |
| Brief works | Type `brief me on Harsh Soni` | LLM calls the `brief` tool and renders the structured brief. |
| File attachment (no URL) | Drag-drop an xlsx without a URL | Bot tells Matt to share a public link instead. |

### Where to debug if something is off

- **Railway deploy logs**: confirm the `upload-from-url` request hit the backend; look for "Parsed N rows" and "Uploaded uploaded-leads/...".
- **Supabase Storage** dashboard → `uploaded-leads` bucket: confirm the file landed.
- **Supabase Database Webhooks** → `leads_storage_uploaded` → Recent deliveries: confirm the webhook fired and got 200 from `/webhooks/storage-uploaded`.
- **`leads` table** filtered by `source_file = '<filename>'`: confirm rows inserted and `enrichment_status` transitioning `pending → done`.
- **Teams channel "Lead Enrichment"**: should receive a card when the batch finishes.
