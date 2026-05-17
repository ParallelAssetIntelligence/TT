# AI Sales Co-Pilot — Build Plan

> **Goal:** Help Matt make better cold calls by enriching leads with LinkedIn data and writing personalized openers using Tustin's 6 scripts.

---

## 📊 Status at a Glance

| # | Step | What It Does | Status | Effort |
|---|------|--------------|--------|--------|
| 1 | **Ingest** | Upload lead file | 🟡 Mostly done | Small |
| 2 | **Enrich** | LinkedIn lookup + signals | ✅ **DONE** | — |
| 3 | **Script** | Write personal openers | ✅ **DONE** | — |
| 4 | **Deliver** | Save file + notify Matt | 🟡 Half | Small |
| 5 | **Brief** | Pre-call one-pager | 🔴 Not started | Medium |
| 6 | **Live Assist** | Real-time call helper | 🔴 Not started | Large |

**Progress:** ~50% complete. Steps 1, 2, 3 working end-to-end.

---

## STEP 1 — INGEST
### *Upload the weekly lead list*

### 🎯 What Client Wants
Matt drops his weekly ZoomInfo file into SharePoint. The system auto-picks it up.

### 💡 Example

Matt exports 700 facility managers in Pennsylvania from ZoomInfo → saves as `leads_week22.xlsx` → drops into SharePoint → system processes automatically.

**Input file looks like:**

| Name | Company | Title | Phone | City |
|------|---------|-------|-------|------|
| John Smith | ABC Hospital | Director of Facilities | 215-555-1234 | Philadelphia |
| Jane Doe | XYZ School | Maintenance Mgr | 215-555-5678 | Pittsburgh |

### ✅ What We Have
- `POST /leads/upload` endpoint accepts `.xlsx` / `.xls` files
- Excel parser reads any column structure

### ⚠️ What We Need to Add
- [ ] **SharePoint folder watcher** — Microsoft Graph API webhook
- [ ] **Column validation** — require Name, Company, Title, Phone
- [ ] **Email backup trigger** — monitored inbox fallback

### 🔧 How (Technically)

```
SharePoint webhook → FastAPI endpoint → validate → save → trigger Step 2
```

---

## STEP 2 — ENRICH ✅
### *Look up each person on LinkedIn + extract signals*

### 🎯 What Client Wants
For every row, find their LinkedIn and extract: how long they've been there, where they worked before, what their real title is. Then tag them.

### 💡 Example

**Input row:**
```
John Smith | ABC Hospital | Director of Facilities
```

**After enrichment:**

| Field | Value |
|-------|-------|
| LinkedIn URL | `linkedin.com/in/johnsmith` |
| Tenure | 8 months |
| Prior Company 1 | Penn Medicine (5 yrs) |
| Prior Company 2 | Temple Health (3 yrs) |
| Title Qualifier | **DECISION_MAKER** ✅ |
| Signal Tag | **NEW_HIRE** |

### ✅ What We Have (Implemented)
- ✅ SerpAPI pulls LinkedIn URL, headline, summary, location, company description
- ✅ **Tenure detection** (months at current company)
- ✅ **Tenure label** — `NEW_HIRE` / `MID_TENURE` / `LONG_TENURED`
- ✅ **Prior companies** extracted (Prior_Company_1, Prior_Company_2)
- ✅ **Title classifier** — `DECISION_MAKER` / `INFLUENCER` / `IN_HOUSE`
- ✅ **Signal tagging** — picks one of 9 trigger tags

### 🔧 How It Works

```
Lead row → SerpAPI (LinkedIn search) → Claude Haiku 4.5 (OpenRouter)
        → returns JSON with all signals → written to Excel
```

**Files:** `app/services/serpapi_enricher.py` + `app/services/intelligence.py`

---

## STEP 3 — SCRIPT ✅
### *Write a custom opener per person*

### 🎯 What Client Wants
Don't use the same cold script. Write 2-3 sentences tailored to **why this person, why now** — based on Matt's 6 Tustin scripts.

### 💡 Examples

**John Smith** *(NEW_HIRE, 8 months in)*:
> *"Hey John, saw you joined ABC Hospital recently from Penn Medicine — we work with a lot of facility leads in that first-year ramp and have helped cut HVAC costs fast. Got 15 minutes this week?"*

**Jane Doe** *(LONG_TENURED, 12 yrs)*:
> *"Jane, you've run XYZ for over a decade — quick question: when's the last time your current vendor did a full systems audit to make sure you're still getting max savings?"*

**Leigh Guarino** *(IN_HOUSE, Westtown School)* — actual output from our system:
> *"Hi Leigh, this is Matt from The Tustin Group — we're a commercial building services company working with schools and institutions across the greater Philadelphia area. I'm calling because most facilities teams like yours are managing HVAC, water treatment, and fire safety across multiple vendors on a reactive basis…"*

### ✅ What We Have (Implemented)
- ✅ **OpenRouter integration** — using `anthropic/claude-haiku-4.5`
- ✅ **All 6 Tustin scripts** embedded in system prompt
- ✅ **Script selector** picks best fit (1-6) based on signals
- ✅ **Personalized opener** stored in `Enriched_Personalized_Opener` column
- ✅ **Objection handlers** included as context for the LLM

### 🔧 How It Works

```python
# Pseudocode of the actual flow
lead_data + linkedin_data
    → Claude Haiku 4.5
    → returns JSON: {
        signal_tag, title_qualifier, tenure_months,
        script_used: "Script 6: Reactive",
        personalized_opener: "Hi Leigh, this is Matt..."
      }
    → save to Excel
```

**Cost:** ~$0.30–$0.60 for the whole 700-row list.
**Speed:** ~2-3 seconds per lead.

**Files:** `app/services/intelligence.py` + `app/services/openrouter_client.py`

---

## STEP 4 — DELIVER
### *Send enriched file back + notify Matt*

### 🎯 What Client Wants
Get the finished Excel back in SharePoint. Get a Teams/email ping saying "your file is ready."

### 💡 Example

📱 **Matt's phone buzzes — Teams notification:**
> 📊 **Co-Pilot:** This week's enriched list is ready.
> 700 contacts processed · 142 new hires flagged · 89 long-tenured
> [Open file]

**Excel now has these columns:**

```
LinkedIn_URL, Tenure_Months, Tenure_Label, Prior_Company_1, Prior_Company_2,
Title_Qualifier, Signal_Tag, Script_Used, Personalized_Opener
```

### ✅ What We Have
- ✅ Excel write-back works
- ✅ All 16 enrichment columns added
- ✅ Returns file as download via `/leads/upload`

### ⚠️ What We Need to Add
- [ ] **SharePoint upload** — Microsoft Graph API
- [ ] **Teams notification** — Teams webhook
- [ ] **Email fallback** — SendGrid or SMTP

### 🔧 How (Technically)

```python
upload_to_sharepoint(file, folder="/Leads/Enriched/")
send_teams_message(webhook_url, "File ready: 700 contacts")
```

---

## STEP 5 — PRE-CALL BRIEF
### *One-page summary before dialing*

### 🎯 What Client Wants
Before calling John, Matt sees a clean summary: who he is, the opener, what he'll likely say no to, and how to handle it.

### 💡 Example

**📋 Call Brief — John Smith @ ABC Hospital**

> **🎯 Why this person, why now:**
> New hire (8 months), came from Penn Medicine (past customer of ours). Director-level = decision maker.
>
> **📞 Recommended opener:**
> *"Hey John, saw you joined ABC Hospital from Penn Medicine..."*
>
> **⚠️ Likely objections:**
> 1. *"I already inherited a vendor"* → *"Totally — when's their next contract review? Worth benchmarking now while you're still onboarding."*
> 2. *"Too busy ramping up"* → *"Exactly why this matters — a 20-min baseline now saves months later."*
>
> **❓ Good follow-ups:**
> - *"What did Penn use for chillers? Was it Elliot Lewis?"*
> - *"What's your first big facility project this year?"*

**Plus a chat box:** Matt types *"What do I know about this person?"* → gets a paragraph summary.

### 🔴 What We Have
Nothing yet.

### ⚠️ What We Need to Add
- [ ] `GET /brief/{row_id}` endpoint → returns JSON brief
- [ ] Claude prompt for brief generation
- [ ] Simple HTML/React page to display brief
- [ ] `POST /ask` Q&A endpoint

### 🔧 How (Technically)

```
GET /brief/123 → Claude generates summary → return JSON → render page
POST /ask {"row_id": 123, "question": "..."} → Claude answers
```

---

## STEP 6 — LIVE CALL ASSIST
### *Real-time help during the call*

### 🎯 What Client Wants
Matt is on the phone. Prospect says something. Matt types 3 words. AI fires back the perfect comeback in **under 3 seconds**.

### 💡 Example

📞 *Matt on call with John Smith*

| Matt types | AI suggests (in <3s) |
|---|---|
| *"says he has Johnson Controls 10 yrs"* | *"What's your process for making sure they're still delivering value? Have they done a full systems audit in the last 2 years?"* |
| *"not interested"* | *"Totally understand — one question before I let you go: if you could save 15% on facility costs without switching vendors, would that be worth a 20-min chat?"* |
| *"asking price"* | *"We don't do fixed pricing — it's always scoped to your systems. Let's set up a walk-through so I can give you a real number. Next week work?"* |
| *"new building 2025"* | *"Ah — sounds like your construction contract is wrapping up. Are you locked into their service plan or evaluating other vendors?"* |

### 🔴 What We Have
Nothing yet.

### ⚠️ What We Need to Add
- [ ] **WebSocket / SSE endpoint** for <3s streaming
- [ ] **Claude streaming API** integration
- [ ] **Chat UI** — text box that stays open during call
- [ ] **Context injection** — every message has full contact brief
- [ ] **Hotkey support** so Matt doesn't lose focus

### 🔧 How (Technically)

```
WebSocket /call/{row_id}/chat
  → Matt types → send to Claude (streaming)
  → tokens stream back → display
  → System prompt = full contact brief + Matt's tone/scripts
```

---

## 🚀 Recommended Build Order

```
✅ 1. Claude API integration         (DONE — via OpenRouter)
✅ 2. Step 2 signals                 (DONE — tenure, title, signal tag)
✅ 3. Step 3 opener generation       (DONE — 6 Tustin scripts)
🔜 4. Step 5 pre-call brief          (next — small lift, huge impact)
🔜 5. Step 4 SharePoint + Teams      (delivery automation)
🔜 6. Step 1 SharePoint watcher      (full automation)
🔜 7. Step 6 live call chat          (last — needs UI work)
```

---

## 📂 Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python + FastAPI |
| Excel I/O | openpyxl |
| Lead lookup | SerpAPI |
| AI / LLM | OpenRouter → Claude Haiku 4.5 |
| Database | Supabase |
| Hosting | Railway |

---

## 📋 Output Excel Columns

After processing, each row has these enriched fields:

| Column | Example Value |
|--------|---------------|
| `Enriched_LinkedIn` | `linkedin.com/in/johnsmith` |
| `Enriched_LinkedIn_Headline` | `Director of Facilities at ABC Hospital` |
| `Enriched_Tenure_Months` | `8` |
| `Enriched_Tenure_Label` | `NEW_HIRE` |
| `Enriched_Prior_Company_1` | `Penn Medicine` |
| `Enriched_Prior_Company_2` | `Temple Health` |
| `Enriched_Title_Qualifier` | `DECISION_MAKER` |
| `Enriched_Signal_Tag` | `NEW_HIRE` |
| `Enriched_Script_Used` | `Script 2: New Occupant` |
| `Enriched_Personalized_Opener` | *"Hey John, saw you joined..."* |

---

*Last updated: 2026-05-17*
