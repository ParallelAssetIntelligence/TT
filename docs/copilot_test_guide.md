# Tustin Co-Pilot — Quick Test Guide

A 5-minute walkthrough of the 4 tools in the bot. For each tool you'll see:

- **What to type** — the exact words to send
- **What the bot says** — a sample of what comes back
- **What it means** — how to read the response

Open the agent at <https://copilotstudio.microsoft.com> → **Tustin Co-Pilot** → **Test your agent** (right side panel). Or use it in the Teams channel where it's installed.

---

## The 4 Tools at a Glance

| # | Tool | When to use it | Sample input |
|---|------|----------------|--------------|
| 1 | **Lookup** | You want a lead's full record | `lookup Vinnie Corsi` |
| 2 | **Brief** | You want a pre-call brief | `brief me on John Smith` |
| 3 | **Respond** | You're on a live call | `says he has Johnson Controls 10 yrs` |
| 4 | **Upload from URL** | New leads need to be added | Paste a Google Sheets / Drive link |

---

## 1️⃣ Lookup — Get a lead's record

**What it does:** Pulls one lead's full info from the database (no AI, instant).

### What to type

```
lookup Vinnie Corsi
```

Other phrasings that work:

- `find Vinnie Corsi`
- `show me Sarah Mitchell`
- `who is Harsh Soni`

### What the bot returns

```
Name:                  Vinnie Corsi
Company:               DFT
Title:                 Director Facilities
Phone:                 (610) 363-8903 ext. 153
Email:                 vcorsi@dft-valves.com
City:                  Exton
State:                 PA
Industry:              Industrial Manufacturing
Department:            Facilities
LinkedIn URL:          https://linkedin.com/in/vinniecorsi
Tenure (months):       36
Tenure Label:          MID_TENURE
Prior Company 1:       Prior Co Inc
Title Qualifier:       DECISION_MAKER
Signal Tag:            UNKNOWN
Script Used:           Script 6: Reactive
Personalized Opener:   Hi Vinnie, this is Matt from The Tustin Group...
Enrichment Status:     done
Enriched At:           2026-05-21T22:58:47
Source File:           TustinGroupLeadGenlist.xlsx
```

### What it means

- **Status `done`** = enrichment finished successfully.
- **Empty LinkedIn** = the public web didn't have a profile for this person.
- **Signal Tag `UNKNOWN`** = no specific calling signal triggered (e.g. not a new hire, not long-tenured).
- The **Personalized Opener** is what you'd say on a cold call.

### ⚠️ Edge case

If the lead doesn't exist:
```
No lead found matching 'whatever you typed'
```
Try a different spelling or just a first name.

---

## 2️⃣ Brief — Generate a pre-call brief

**What it does:** Creates a structured call-prep document. Uses AI. Takes ~2-3 seconds.

### What to type

```
brief me on John Smith
```

Other phrasings:

- `tell me about Harsh Soni`
- `prep me for Sarah Mitchell`
- `what should I know about Leigh Guarino`

### What the bot returns

```
Name:                John Smith
Company:             ABC Hospital
Title:               Director of Facilities
Title Qualifier:     DECISION_MAKER
Signal Tag:          NEW_HIRE
Tenure (months):     8
Prior Companies:
  1. Penn Medicine
  2. Temple Health

Recommendation:
  Lead with the new-hire angle. Decision-maker authority but still learning
  the building's pain points — perfect window to introduce.

Recommended Opener:
  "Hey John, saw you joined ABC Hospital recently from Penn Medicine —
   we work with a lot of facility leads in that first-year ramp and
   have helped cut HVAC costs fast. Got 15 minutes this week?"

Script Used:         Script 2: New Occupant

Likely Objections:
  1. "I'm still onboarding, not making vendor changes yet."
     → "Totally — that's why I'm calling early. We'd just baseline so when
        you're ready, you have a 15% cost number ready to discuss."

  2. "We have a vendor we're happy with."
     → "Good — Penn used multiple vendors for HVAC. Worth a no-pressure
        15-min benchmark to know your current rate vs market?"

Follow-up Questions:
  • What did Penn use for chillers? Elliot Lewis?
  • What's your first big facility project this year?
```

### What it means

- **`Title Qualifier`** tells you who can sign — `DECISION_MAKER` is gold.
- **`Signal Tag`** tells you why this person, why now — `NEW_HIRE` = great timing window.
- **`Recommended Opener`** is what you say on the call.
- **`Likely Objections`** are practice for the common pushbacks.
- **`Follow-up Questions`** keep the conversation moving.

### Time

Brief generation takes **2–3 seconds**. Brief responses get richer when LinkedIn data is available.

---

## 3️⃣ Respond — Live-call assistant

**What it does:** Mid-call, you type what the prospect just said. AI suggests your next sentence in **under 3 seconds**.

### What to type

Just paste what the prospect said:

```
says he has Johnson Controls 10 yrs
```

Other examples:

- `not interested`
- `asking about price`
- `already have a vendor`
- `new building in 2025`
- `wrong person`

### What the bot returns

```
Suggestion:
  "What's your process for making sure they're still delivering value?
   Have they done a full systems audit in the last 2 years?"

Intent Detected:     VENDOR_LOCKED
```

### What it means

- **`Suggestion`** = the next 1–2 sentences you say. Max 30 words. Designed to be said out loud immediately.
- **`Intent Detected`** = what the prospect's underlying signal is. Possible values:
  - `VENDOR_LOCKED` — they have someone
  - `NOT_INTERESTED` — cold refusal
  - `PRICE_QUESTION` — asking about cost
  - `GATEKEEPER` — wrong person blocking you
  - `INTERESTED` — positive signal
  - `OTHER` — uncertain

### Time

**1–2 seconds.** Built for live-call speed.

### Pro tip

You can include the lead's name for better context: type `lead is John Smith — says he's locked in with Johnson` and the bot uses John's specific signals to tailor the comeback.

---

## 4️⃣ Upload from URL — Add new leads

**What it does:** You paste a link to an Excel file (or Google Sheet). The bot downloads it, parses it, adds new leads to the database, and starts enriching them automatically.

### What to type

Just paste the URL. No prefix needed:

```
https://docs.google.com/spreadsheets/d/1aBcDeFg.../edit?usp=sharing
```

Supported sources:

| Source | Example link |
|--------|--------------|
| Google Sheets | `https://docs.google.com/spreadsheets/d/.../edit` |
| Google Drive | `https://drive.google.com/file/d/.../view` |
| Dropbox | `https://www.dropbox.com/s/.../file.xlsx?dl=0` |
| OneDrive / SharePoint | `https://contoso.sharepoint.com/.../file.xlsx` |
| Direct download | Any HTTPS link ending in `.xlsx` |

### What the bot returns (instantly)

```
Status:               ✅ success
Filename:             test_leads.xlsx
Columns detected:     15
Rows detected:        5
Storage URL:          https://wzhqsmaunimgvowkdegl.supabase.co/storage/.../test_leads.xlsx
```

### What happens next (in the background)

```
T+0s        Upload confirmation shows above
T+1–3 sec   Leads inserted into the table
T+10–60 sec Each lead enriched (LinkedIn, tenure, opener)
T+~1 min    A Teams card appears in the "Lead Enrichment" channel
            with a "Download enriched .xlsx" button
```

### What it means

- **`Status: ✅ success`** = file accepted.
- **`Rows detected: 5`** = 5 leads will be added (duplicates auto-skipped).
- **`Storage URL`** = where the raw file is stored permanently.
- Within ~1 minute, the Teams card lets you download the fully enriched spreadsheet.

### ⚠️ Sharing permission

The link **must be public**. Settings to use:

| Source | Setting |
|--------|---------|
| Google Sheets / Drive | "Anyone with the link – Viewer" |
| Dropbox | Default share is public ✓ |
| SharePoint / OneDrive | "Anyone with the link" (not "People in your organization") |

If the link is restricted, the bot returns a 400 error and tells you so.

### What kinds of errors you might see

| Error message | What to do |
|---|---|
| `URL must use https://` | Use the https version of the link |
| `URL resolves to a non-public address` | The hostname is invalid / private |
| `Download failed with HTTP 401` | The link is restricted — change to "Anyone with the link" |
| `URL did not return an .xlsx or .xls file` | The link is to a webpage, not a file |
| `No lead rows detected` | The file's empty or has only a header row |
| `File too large (X MB); limit is 25 MB` | Split the file or remove old leads |

---

## 5-Minute Smoke Test (do this every time)

Run these in order to verify the whole pipeline:

| # | Type this | Expect |
|---|-----------|--------|
| 1 | `lookup Harsh Soni` | Full record card with `enrichment_status: done` |
| 2 | `brief me on Harsh Soni` | Brief card with opener, objections, follow-ups |
| 3 | `says he already has a vendor` | 1–2 sentence comeback in ~2 sec |
| 4 | Paste a Google Sheets URL | `✅ success` card with `rows_detected: N` |
| 5 | Wait 60 seconds → check Teams "Lead Enrichment" channel | New "Lead enrichment complete" card with download button |

If all 5 pass, the bot is fully working.

---

## Troubleshooting Quick Reference

### Bot says "I don't have that information"
- The agent might not be published. Ask the admin to re-publish in Copilot Studio.

### Lookup returns 404
- The name doesn't exist in the database. Try just the first name, or paste the full name as it appears in the source spreadsheet.

### Upload says success but no Teams card after 5 min
- Enrichment may have failed silently. Ask the admin to check the `leads` table — rows should have `enrichment_status='done'` or `enrichment_status='failed'`.

### Card shows but download button doesn't work
- The Railway server may be sleeping. Click again after 30 seconds.

### Bot is slow (>10 sec)
- First request after idle wakes the server. Should be fast on the second try.

---

## Quick facts

| Question | Answer |
|---|---|
| Is the data live? | Yes — `lookup` always pulls the latest from the database. |
| How many leads in the system? | Visible to admin in Supabase Table Editor. |
| Can I upload the same file twice? | Yes — duplicates are skipped automatically (matched by phone or name + company). |
| Where do enriched files go? | They're regenerated on demand via the "Download enriched .xlsx" button on each Teams card. |
| What if I find a lead with wrong data? | Ask the admin to re-enrich it via the retry endpoint. The data refreshes from SerpAPI + AI. |

---

*Last updated: 2026-05-22 — questions to <product@parallelassetintelligence.com>*
