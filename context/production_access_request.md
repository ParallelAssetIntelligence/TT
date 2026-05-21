# 📋 Tustin CoPilot — Production Access Request & Setup Guide

> **Purpose:** What we need from Andrew (or Tustin IT) to move the bot from prototype → production, plus the step-by-step setup guide once access is granted.

---

## 🎯 TL;DR — What We Need

| # | What | For | Who Sets It Up |
|---|------|-----|----------------|
| 1 | SharePoint folder + Azure AD app | Step 1: Auto-pickup of lead files | Andrew / Tustin IT |
| 2 | Teams channel + webhook | Step 4: "File ready" notifications | Andrew / Tustin IT |
| 3 | Guest access to Tustin's M365 tenant | Bot hosting + Copilot Studio | Andrew / Tustin IT |

**Total monthly cost to Tustin:** ~$226/user (much cheaper than hiring a sales analyst)

---

# 🔑 PART 1: Access Request Email (Send to Andrew)

```
Subject: Tustin CoPilot — Production Access Needed

Hi Andrew,

To put the Tustin CoPilot bot into production, I need 3 things 
from you (or Tustin's IT team):

1. SharePoint folder for Matt's lead files
   + Azure AD app with Files.ReadWrite.All permission

2. Teams channel for notifications
   + Power Automate webhook URL for that channel

3. Microsoft 365 license OR guest access to Tustin's tenant
   for me (harsh@dyotaai.com) so I can build the bot in 
   their environment.

Estimated setup time once I have access: 1 week.
Cost to Tustin: ~$226/month per user.

Want to jump on a 15-min call to discuss?

— Harsh
```

---

# 📦 PART 2: Detailed Access Breakdown

## 1️⃣ SharePoint Access (for Step 1 — Lead Ingest)

### What it's for
Matt drops his weekly ZoomInfo file in a SharePoint folder. The app auto-picks it up, enriches it, and writes the enriched version back. **Zero manual steps for Matt.**

### What Andrew needs to provide

| Item | Why |
|------|-----|
| SharePoint site URL | Where the folder lives (e.g., `tustingroup.sharepoint.com/sites/Sales`) |
| Folder path | Exact path (e.g., `/Documents/Leads/Inbox`) |
| Azure AD App registration | Lets the bot authenticate to SharePoint |
| Application (client) ID | Identifies the app |
| Directory (tenant) ID | Tustin's tenant |
| Client Secret | Password for the app |
| Permissions | `Files.ReadWrite.All`, `Sites.ReadWrite.All` |

### How Andrew creates the Azure AD app

1. Go to **portal.azure.com**
2. **Azure Active Directory** → **App registrations** → **New registration**
3. Name: `Tustin-CoPilot`
4. After creation, send to Harsh:
   - Client ID
   - Tenant ID
   - Client Secret (generate under "Certificates & secrets")
5. Under **API permissions**, add:
   - `Files.ReadWrite.All`
   - `Sites.ReadWrite.All`
6. Click **"Grant admin consent"**

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

## SETUP 1: SharePoint File Watcher

### Step 1.1: Add Azure credentials to `.env`
```env
AZURE_TENANT_ID=<from Andrew>
AZURE_CLIENT_ID=<from Andrew>
AZURE_CLIENT_SECRET=<from Andrew>
SHAREPOINT_SITE_ID=<from Andrew>
SHAREPOINT_FOLDER_PATH=/Documents/Leads/Inbox
```

### Step 1.2: Install Microsoft Graph SDK
```bash
pip install msal httpx
```

### Step 1.3: Create the webhook endpoint
Build `app/routes/webhooks.py` that:
- Listens for SharePoint "file added" events
- Downloads the new file via Graph API
- Triggers the enrichment pipeline
- Uploads the enriched file back

### Step 1.4: Register the SharePoint subscription
Run once to tell Microsoft Graph: *"Watch this folder."*

Subscriptions expire every ~3 days → set up a cron to renew.

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

