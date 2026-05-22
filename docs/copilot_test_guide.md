TUSTIN CO-PILOT — QUICK TEST GUIDE
═══════════════════════════════════════════════════════════════════

A 5-minute walkthrough of the 4 tools in the bot. For each tool you will see:

   • WHAT TO TYPE  — the exact words to send the bot
   • WHAT THE BOT SAYS  — a sample of what comes back
   • WHAT IT MEANS  — how to read the response

Open the agent at https://copilotstudio.microsoft.com → Tustin Co-Pilot →
"Test your agent" (right side panel). Or use it in the Teams channel where
it is installed.


THE 4 TOOLS AT A GLANCE
───────────────────────────────────────────────────────────────────

   #   TOOL                WHEN TO USE IT                       SAMPLE INPUT
   1   Lookup              You want a lead's full record        lookup Vinnie Corsi
   2   Brief               You want a pre-call brief            brief me on John Smith
   3   Respond             You are on a live call               says he has Johnson Controls 10 yrs
   4   Upload from URL     New leads need to be added           paste a Google Sheets / Drive link



1. LOOKUP — GET A LEAD'S RECORD
═══════════════════════════════════════════════════════════════════

What it does:
   Pulls one lead's full info from the database. No AI. Instant.

WHAT TO TYPE
───────────────────────────────────────────────────────────────────

      lookup Vinnie Corsi

Other phrasings that work:

   • find Vinnie Corsi
   • show me Sarah Mitchell
   • who is Harsh Soni

WHAT THE BOT RETURNS
───────────────────────────────────────────────────────────────────

      Name:                 Vinnie Corsi
      Company:              DFT
      Title:                Director Facilities
      Phone:                (610) 363-8903 ext. 153
      Email:                vcorsi@dft-valves.com
      City:                 Exton
      State:                PA
      Industry:             Industrial Manufacturing
      Department:           Facilities
      LinkedIn URL:         https://linkedin.com/in/vinniecorsi
      Tenure (months):      36
      Tenure Label:         MID_TENURE
      Prior Company 1:      Prior Co Inc
      Title Qualifier:      DECISION_MAKER
      Signal Tag:           UNKNOWN
      Script Used:          Script 6: Reactive
      Personalized Opener:  Hi Vinnie, this is Matt from The Tustin Group…
      Enrichment Status:    done
      Enriched At:          2026-05-21T22:58:47
      Source File:          TustinGroupLeadGenlist.xlsx

WHAT IT MEANS
───────────────────────────────────────────────────────────────────

   • Status "done"  =  enrichment finished successfully.
   • Empty LinkedIn  =  the public web did not have a profile for this person.
   • Signal Tag "UNKNOWN"  =  no specific calling signal triggered
                              (not a new hire, not long-tenured, etc.).
   • The Personalized Opener is what you would say on a cold call.

EDGE CASE
───────────────────────────────────────────────────────────────────

If the lead does not exist, the bot replies:

      No lead found matching 'whatever you typed'

Try a different spelling or just a first name.



2. BRIEF — GENERATE A PRE-CALL BRIEF
═══════════════════════════════════════════════════════════════════

What it does:
   Creates a structured call-prep document. Uses AI. Takes about 2–3 seconds.

WHAT TO TYPE
───────────────────────────────────────────────────────────────────

      brief me on John Smith

Other phrasings:

   • tell me about Harsh Soni
   • prep me for Sarah Mitchell
   • what should I know about Leigh Guarino

WHAT THE BOT RETURNS
───────────────────────────────────────────────────────────────────

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
        Lead with the new-hire angle. Decision-maker authority but still
        learning the building's pain points — perfect window to introduce.

      Recommended Opener:
        "Hey John, saw you joined ABC Hospital recently from Penn
         Medicine — we work with a lot of facility leads in that
         first-year ramp and have helped cut HVAC costs fast.
         Got 15 minutes this week?"

      Script Used:         Script 2: New Occupant

      Likely Objections:
        1. "I'm still onboarding, not making vendor changes yet."
           Response: "Totally — that's why I'm calling early. We'd just
                      baseline so when you're ready, you have a 15% cost
                      number ready to discuss."

        2. "We have a vendor we're happy with."
           Response: "Good — Penn used multiple vendors for HVAC. Worth a
                      no-pressure 15-min benchmark to know your current
                      rate vs market?"

      Follow-up Questions:
        • What did Penn use for chillers? Elliot Lewis?
        • What's your first big facility project this year?

WHAT IT MEANS
───────────────────────────────────────────────────────────────────

   • Title Qualifier  →  tells you who can sign. DECISION_MAKER is gold.
   • Signal Tag       →  tells you why this person, why now.
                          NEW_HIRE = great timing window.
   • Recommended Opener  →  what you say on the call.
   • Likely Objections   →  practice for the common pushbacks.
   • Follow-up Questions →  keep the conversation moving.

TIME
───────────────────────────────────────────────────────────────────

Brief generation takes 2–3 seconds. Briefs get richer when the lead has
LinkedIn data available.



3. RESPOND — LIVE-CALL ASSISTANT
═══════════════════════════════════════════════════════════════════

What it does:
   Mid-call, you type what the prospect just said. AI suggests your next
   sentence in under 3 seconds.

WHAT TO TYPE
───────────────────────────────────────────────────────────────────

Just paste what the prospect said:

      says he has Johnson Controls 10 yrs

Other examples:

   • not interested
   • asking about price
   • already have a vendor
   • new building in 2025
   • wrong person

WHAT THE BOT RETURNS
───────────────────────────────────────────────────────────────────

      Suggestion:
        "What's your process for making sure they're still delivering
         value? Have they done a full systems audit in the last 2 years?"

      Intent Detected:     VENDOR_LOCKED

WHAT IT MEANS
───────────────────────────────────────────────────────────────────

   • Suggestion  →  the next 1–2 sentences you say. Max 30 words.
                    Designed to be said out loud immediately.

   • Intent Detected  →  what the prospect's underlying signal is.
                          Possible values:

         VENDOR_LOCKED     they already have someone
         NOT_INTERESTED    cold refusal
         PRICE_QUESTION    asking about cost
         GATEKEEPER        wrong person blocking you
         INTERESTED        positive signal
         OTHER             uncertain

TIME
───────────────────────────────────────────────────────────────────

1–2 seconds. Built for live-call speed.

PRO TIP
───────────────────────────────────────────────────────────────────

You can include the lead's name for better context. Try:

      lead is John Smith — says he's locked in with Johnson

The bot will use John's specific signals to tailor the comeback.



4. UPLOAD FROM URL — ADD NEW LEADS
═══════════════════════════════════════════════════════════════════

What it does:
   You paste a link to an Excel file (or Google Sheet). The bot downloads
   it, parses it, adds new leads to the database, and starts enriching
   them automatically.

WHAT TO TYPE
───────────────────────────────────────────────────────────────────

Just paste the URL. No prefix needed:

      https://docs.google.com/spreadsheets/d/1aBcDeFg.../edit?usp=sharing

Supported sources:

   SOURCE                  EXAMPLE LINK
   Google Sheets           https://docs.google.com/spreadsheets/d/.../edit
   Google Drive            https://drive.google.com/file/d/.../view
   Dropbox                 https://www.dropbox.com/s/.../file.xlsx?dl=0
   OneDrive / SharePoint   https://contoso.sharepoint.com/.../file.xlsx
   Direct download         Any HTTPS link ending in .xlsx

WHAT THE BOT RETURNS (INSTANTLY)
───────────────────────────────────────────────────────────────────

      Status:              ✅ success
      Filename:            test_leads.xlsx
      Columns detected:    15
      Rows detected:       5
      Storage URL:         https://wzhqsmaunimgvowkdegl.supabase.co/...

WHAT HAPPENS NEXT (IN THE BACKGROUND)
───────────────────────────────────────────────────────────────────

   T+0s         Upload confirmation shows above
   T+1-3 sec    Leads inserted into the table
   T+10-60 sec  Each lead enriched (LinkedIn, tenure, opener)
   T+~1 min     A Teams card appears in the "Lead Enrichment" channel
                with a "Download enriched .xlsx" button

WHAT IT MEANS
───────────────────────────────────────────────────────────────────

   • Status "✅ success"  =  file accepted.
   • Rows detected: 5      =  5 leads will be added.
                              Duplicates auto-skipped.
   • Storage URL           =  where the raw file is stored permanently.
   • Within ~1 minute, the Teams card lets you download the fully
     enriched spreadsheet.

SHARING PERMISSION — IMPORTANT
───────────────────────────────────────────────────────────────────

The link must be PUBLIC. Settings to use:

   SOURCE                   SETTING
   Google Sheets / Drive    "Anyone with the link – Viewer"
   Dropbox                  Default share is public
   SharePoint / OneDrive    "Anyone with the link"
                            (NOT "People in your organization")

If the link is restricted, the bot returns a 400 error and tells you so.

POSSIBLE ERRORS
───────────────────────────────────────────────────────────────────

   ERROR MESSAGE                            WHAT TO DO
   URL must use https://                    Use the https version of the link
   URL resolves to a non-public address     Hostname is invalid / private
   Download failed with HTTP 401            Link is restricted — set to
                                            "Anyone with the link"
   URL did not return an .xlsx file         Link goes to a webpage,
                                            not a file
   No lead rows detected                    File is empty or only has
                                            a header row
   File too large (X MB); limit is 25 MB    Split the file or remove
                                            old leads



5-MINUTE SMOKE TEST  (DO THIS EVERY TIME)
═══════════════════════════════════════════════════════════════════

Run these in order to verify the whole pipeline works end-to-end.

   STEP   TYPE THIS                          EXPECT
   1      lookup Harsh Soni                  Full record card with
                                              enrichment_status: done

   2      brief me on Harsh Soni             Brief card with opener,
                                              objections, follow-ups

   3      says he already has a vendor       1-2 sentence comeback
                                              in ~2 seconds

   4      Paste a Google Sheets URL          ✅ success card with
                                              rows_detected: N

   5      Wait 60 seconds → check Teams      New "Lead enrichment
          "Lead Enrichment" channel          complete" card with
                                              download button

If all 5 steps pass, the bot is fully working.



TROUBLESHOOTING QUICK REFERENCE
═══════════════════════════════════════════════════════════════════

PROBLEM
   Bot says "I don't have that information"

CAUSE / FIX
   The agent might not be published. Ask the admin to re-publish in
   Copilot Studio.


PROBLEM
   Lookup returns "No lead found"

CAUSE / FIX
   The name does not exist in the database yet.
   • Try just the first name
   • Or paste the full name as it appears in the source spreadsheet


PROBLEM
   Upload says success, but no Teams card after 5 min

CAUSE / FIX
   Enrichment may have failed silently. Ask the admin to check the
   leads table — rows should have enrichment_status = 'done' or
   enrichment_status = 'failed'.


PROBLEM
   Card shows but the download button does not work

CAUSE / FIX
   The Railway server may be sleeping. Click the button again
   after 30 seconds.


PROBLEM
   Bot is slow (over 10 seconds)

CAUSE / FIX
   The first request after idle wakes the server. Should be fast
   on the second try.



QUICK FACTS
═══════════════════════════════════════════════════════════════════

QUESTION                              ANSWER
Is the data live?                     Yes — Lookup always pulls
                                       the latest from the database.

How many leads in the system?         Visible to admin in Supabase
                                       Table Editor.

Can I upload the same file twice?     Yes — duplicates are skipped
                                       automatically. Matched by
                                       phone number, or name + company
                                       if no phone.

Where do enriched files go?           Regenerated on demand via the
                                       "Download enriched .xlsx" button
                                       on each Teams card.

What if a lead has wrong data?        Ask the admin to re-enrich it
                                       via the retry endpoint. The data
                                       refreshes from SerpAPI + AI.



───────────────────────────────────────────────────────────────────
Last updated: 2026-05-22
Questions: product@parallelassetintelligence.com
───────────────────────────────────────────────────────────────────
