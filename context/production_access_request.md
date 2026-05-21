# 📋 Tustin CoPilot — Production Access Request & Setup Guide

> **Purpose:** What we need from Andrew (or Tustin IT) to move the bot from prototype → production, plus the step-by-step setup guide once access is granted.

---

## 🎯 TL;DR — What We Need

| # | What | For | Who Sets It Up |
|---|------|-----|----------------|
| 1 | Copilot Studio Topic + Power Automate flow | Step 1: Matt uploads lead file directly in chat → Supabase | Harsh (no Tustin access needed) |
| 2 | Teams channel + webhook | Step 4: "File ready" notifications | Andrew / Tustin IT |
| 3 | Guest access to Tustin's M365 tenant | Bot hosting + Copilot Studio | Andrew / Tustin IT |

**Total monthly cost to Tustin:** ~$226/user (much cheaper than hiring a sales analyst)

---

# 🔑 PART 1: Access Request Email (Send to Andrew)

```
Subject: Tustin CoPilot — Production Access Needed

Hi Andrew,

To put the Tustin CoPilot bot into production, I need 2 things 
from you (or Tustin's IT team):

1. Teams channel for notifications
   + Power Automate webhook URL for that channel

2. Microsoft 365 license OR guest access to Tustin's tenant
   for me (harsh@dyotaai.com) so I can build the bot in 
   their environment.

(No SharePoint setup needed — Matt will upload his lead file 
directly inside the Copilot chat, and the bot stages it in 
our storage automatically.)

Estimated setup time once I have access: 1 week.
Cost to Tustin: ~$226/month per user.

Want to jump on a 15-min call to discuss?

— Harsh
```

---

# 📦 PART 2: Detailed Access Breakdown

## 1️⃣ In-Chat File Upload (for Step 1 — Lead Ingest)

### What it's for
Matt drops his weekly ZoomInfo `.xlsx` directly into the Copilot Studio chat in Teams. A Topic asks for the file, a Power Automate flow uploads the bytes to our Supabase **`uploaded-leads`** bucket, and the bot replies in chat:

> ✅ File uploaded successfully — `leads_week22.xlsx` is now in the queue.

**No SharePoint, no Azure AD app, no Tustin IT involvement for ingest.** Enrichment runs as a separate step (covered in Setup 2/3).

### What Andrew needs to provide

Nothing for this step. Ingest is fully owned on our side (Copilot Studio Topic + Power Automate flow + Supabase Storage, all configured by Harsh).

### How it works under the hood

1. Matt types "enrich this file" (or just attaches the file) in the Copilot Studio chat.
2. The **"Upload Leads"** Topic fires → asks for the file via `Ask question` (File variable).
3. Power Automate flow grabs the binary, POSTs it (multipart/form-data) to the Railway backend.
4. Backend writes it to the Supabase `uploaded-leads` bucket and returns `{status, filename, message}`.
5. Topic shows Matt the success message in chat.

> **Why this works:** the Power Automate flow can pass the file binary (the LLM orchestrator can't — known Copilot Studio limitation around `format: binary` schemas). The Topic owns the upload step; the LLM stays out of it.

---

## 2️⃣ Teams Channel + Notification Webhook (for Step 4 — Delivery)

### What it's for
After enrichment finishes (5-10 min), Matt gets a Teams notification:

> 📊 **Co-Pilot:** This week's enriched list is ready.
> 700 contacts processed · 142 new hires flagged · 89 long-tenured
> [Open file]

### What Andrew needs to provide

| Item | Why |
|------|-----|
| Teams channel | Where notifications go (e.g., `Sales / #Lead Updates`) |
| Power Automate workflow URL | The webhook URL the bot POSTs to |

### How Andrew sets it up

1. Open the Teams channel
2. Click ⋯ on channel name → **Workflows**
3. Pick template: **"Post to a channel when a webhook request is received"**
4. Select the team + channel
5. Click **Add workflow**
6. Copy the webhook URL → send to Harsh

---

## 3️⃣ Copilot Studio Access (Bot Hosting)

### What it's for
The bot currently lives in a test (school) tenant. For production, it needs to be hosted in Tustin's M365 tenant so Matt can use it natively inside Teams.

### What Andrew needs to provide

| Item | Why | Cost |
|------|-----|------|
| M365 Business Basic license | Includes Teams + SharePoint | $6/user/month |
| Guest invite to Tustin tenant | Lets Harsh build the bot | Free |
| Power Platform Maker role | Permission to create agents | Free |
| Copilot Studio license | Production-grade AI bot platform | ~$200/tenant/month |

### How Andrew adds Harsh as guest

1. Go to **admin.microsoft.com**
2. **Users** → **Guest users** → **Add a guest user**
3. Email: `harsh@dyotaai.com`
4. Role: **Maker** (Power Platform)
5. Send invitation → Harsh accepts via email

---

# 🛠️ PART 3: Setup Steps (After Access is Granted)

## SETUP 1: In-Chat File Upload → Supabase

### Step 1.1: Add Supabase credentials to `.env`
Already present from earlier work — just confirm:
```env
SUPABASE_URL=https://wzhqsmaunimgvowkdegl.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role key>
SUPABASE_UPLOADED_BUCKET=uploaded-leads
```

### Step 1.2: Build the upload endpoint (`POST /copilot/upload-file`)
New FastAPI route in `app/routes/copilot.py`:
- Accepts `multipart/form-data` with a single `file` field (`UploadFile`).
- Reads bytes, hands them to `storage_uploader.upload_uploaded_file(bytes, filename)` (extend the existing uploader to write to the `uploaded-leads` bucket).
- Returns:
  ```json
  {
    "status": "success",
    "filename": "leads_week22.xlsx",
    "storage_url": "https://wzhqsmaunimgvowkdegl.supabase.co/storage/v1/object/public/uploaded-leads/...",
    "message": "✅ File uploaded successfully — leads_week22.xlsx is in the queue."
  }
  ```
- Validates: extension is `.xlsx`/`.xls`, size under (say) 25 MB. Return `400` with a friendly `detail` on failure so the Topic can show the error verbatim.

### Step 1.3: Add the operation to the OpenAPI spec
Append a `/copilot/upload-file` path to `context/copilot_openapi.json` with:
- `operationId: "UploadLeadsFile"`
- Request body: `multipart/form-data`, `file: { type: string, format: binary }`
- Response 200 schema matching the payload above

Re-import the spec into the Copilot Studio custom connector so the new action is available to Power Automate (not to the LLM).

### Step 1.4: Build the Copilot Studio "Upload Leads" Topic
1. **Trigger phrases:** `enrich this file`, `upload leads`, `process this file`, plus the file-attachment intent.
2. **Ask question** node → variable `LeadsFile` of type **File**.
3. **Call an action** → Power Automate flow `Upload Leads File` (see next step), pass `LeadsFile` as input.
4. **Message** node → display `flow.message` to Matt (the `"✅ File uploaded successfully…"` string).
5. **On error branch** → display `flow.detail` so backend validation errors surface in chat.

### Step 1.5: Build the Power Automate flow (`Upload Leads File`)
1. **Trigger:** *"When Copilot Studio calls a flow"*. Input: `LeadsFile` (File).
2. **HTTP action:**
   - Method: `POST`
   - URI: `https://tt-production-da10.up.railway.app/copilot/upload-file`
   - Headers: `Content-Type: multipart/form-data; boundary={boundary}` *(Power Automate's HTTP action builds this automatically when you use the "Multipart form data" body option)*
   - Body: one part, name `file`, content `triggerBody()['LeadsFile']['contentBytes']`, filename `triggerBody()['LeadsFile']['name']`.
3. **Parse JSON** the response.
4. **Return to Copilot Studio:** `message` (string), `status` (string), `storage_url` (string).

### Step 1.6: Test end-to-end
- In Teams → open Tustin CoPilot → drag in `tests/test_leads.xlsx`.
- Expect chat reply: `✅ File uploaded successfully — test_leads.xlsx is in the queue.`
- Verify in Supabase dashboard: `uploaded-leads` bucket has the new object with a timestamp prefix.

### What this replaces
The previous design used a SharePoint folder watcher + Azure AD app + Microsoft Graph subscription. **All of that is gone** — no Tustin-side IT work for ingest, no 3-day subscription renewals, no Graph credentials in `.env`.

---

## SETUP 2: Teams Notifications

### Step 2.1: Add webhook URL to `.env`
```env
TEAMS_WEBHOOK_URL=https://prod-xx.westus.logic.azure.com/...
```

### Step 2.2: Wire into the enrichment pipeline
After enrichment completes, call `send_enrichment_complete()` — already built in `app/services/teams_notifier.py`.

### Step 2.3: Test
Run a manual enrichment → verify the Teams channel receives the card.

---

## SETUP 3: Move Copilot Studio Bot to Tustin Tenant

### Step 3.1: Log into Copilot Studio with new account
- Go to **copilotstudio.microsoft.com**
- Sign in with Tustin tenant credentials (from Andrew)

### Step 3.2: Re-create the agent
Same steps as the prototype build:
- Create new agent: `Tustin CoPilot`
- Upload Knowledge: `script.md`, `meeting.md`
- Add Tools: upload `copilot_openapi.json`
- Set Overview Instructions
- Test with sample queries

### Step 3.3: Publish to Teams
- **Channels** tab → **Microsoft Teams** → **Add channel** → **Publish**
- Submit for admin approval (Andrew approves)

### Step 3.4: Test as Matt
- Open Teams → search "Tustin CoPilot" → add to chat
- Run test queries:
  - `brief me on Leigh Guarino`
  - `says he has Johnson Controls`
  - `lookup Adam Lord`

---

# 💰 PART 4: Cost Breakdown for Tustin

| Item | Cost | Frequency |
|------|------|-----------|
| M365 Business Basic | $6/user | per month |
| Copilot Studio license | ~$200/tenant | per month |
| Azure (Graph API + Storage) | ~$0-10 | per month |
| Railway (backend hosting) | $5 | per month |
| OpenRouter (Claude API) | ~$5 per 1000 leads | usage-based |
| **TOTAL (1 user, Matt)** | **~$226/month** | |

### ROI for Tustin
- Sales analyst: $5,000+/month
- CoPilot bot: $226/month
- **Savings:** ~95% reduction in research/prep time

---

