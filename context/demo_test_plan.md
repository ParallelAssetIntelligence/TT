# 🎬 Tustin CoPilot Bot — Demo Test Plan

Complete test queries with **actual expected results** captured from the live Railway API on 2026-05-17.

---

## 📋 Available Leads (Excel rows 2-11)

| Row | Name | Company | Title |
|-----|------|---------|-------|
| 2 | Leigh Guarino | Westtown School | Physical Plant Manager |
| 3 | Adalberto Dejesus | United Lutheran Seminary Philadelphia | Director of Facilities |
| 4 | Adam cheyney | Berkeley One | Facilities Maintenance Engineer |
| 5 | Adam Lord | Deacon Industrial Supply | Director of Operations |
| 6 | Al Augustine | Lower Merion Township | Facilities Manager |
| 7 | Al Eby | Gwynedd Mercy Academy HS | Facilities Manager |
| 8 | Alan Mitchell | Spitz - Cosm company | Operations Manager |
| 9 | Alan Moretti | Brandywine Realty | Senior Property Manager |
| 10 | Alex Kotlyar | Curtiss Wright EST Group | Director, Engineering & Operations |
| 11 | Alex Sadler | Perelman Jewish Day School | Director of Facilities |

---

# 🧪 TEST 1: `/copilot/lookup` — Find Lead by Name

## TEST 1.1 — Find Adam Lord ✅
**Input:** `lookup Adam Lord`

**Expected Output:**
```
Name:    Adam Lord
Company: Deacon Industrial Supply
Title:   Director of Operations
Status:  HTTP 200 OK
```

## TEST 1.2 — Find Alex Kotlyar ✅
**Input:** `lookup Alex Kotlyar`

**Expected Output:**
```
Name:    Alex Kotlyar
Company: Curtiss Wright EST Group
Title:   Director, Engineering & Operations
Status:  HTTP 200 OK
```

## TEST 1.3 — Find Alan Moretti ✅
**Input:** `find Alan Moretti`

**Expected Output:**
```
Name:    Alan Moretti
Company: Brandywine Realty
Title:   Senior Property Manager
Status:  HTTP 200 OK
```

## TEST 1.4 — Lead Not Found ⚠️
**Input:** `lookup Nonexistent Person`

**Expected Output:**
```
Status: HTTP 404
Bot reply: "No lead found matching 'Nonexistent Person'"
```

---

# 🧪 TEST 2: `/copilot/brief` — Pre-Call Brief

## TEST 2.1 — Leigh Guarino (IN_HOUSE — Don't Pitch) ✅
**Input:** `brief me on Leigh Guarino`

**Expected Output:**
```
🎯 Recommendation:
   Leigh is in-house ops — position Tustin as a force multiplier
   for his team, not a replacement. Lead with cost consolidation
   and reduced emergency callouts.

📞 Recommended Opener:
   "Hi Leigh, this is Matt from The Tustin Group — we're a
   commercial building services company working with schools and
   institutions across the greater Philadelphia area..."

📜 Script Used: Script 6: Reactive

⚠️ Objections: 2 returned
❓ Follow-ups: 2 returned
```

## TEST 2.2 — Adalberto Dejesus (Director — Decision Maker) ✅
**Input:** `brief me on Adalberto Dejesus`

**Expected Output:**
```
🎯 Recommendation:
   Lead with building systems assessment angle — religious/educational
   institutions often operate on tight budgets and deferred maintenance.
   Position as cost-reduction partner, not vendor.

📞 Recommended Opener:
   "Hi Adalberto, this is Matt from The Tustin Group — we're a
   commercial building services company serving the Philadelphia
   area. I'm calling because we work with a lot of educational
   and institutional buildings..."

📜 Script Used: Script 6 (adapted for institutional setting)

⚠️ Objections: 2 returned
❓ Follow-ups: 2 returned
```

## TEST 2.3 — Alex Kotlyar (Director, Engineering) ✅
**Input:** `tell me about Alex Kotlyar`

**Expected Output:**
```
🎯 Recommendation:
   Alex is a decision-maker in engineering and operations —
   position as a peer conversation about building systems
   reliability and operational efficiency, not a vendor pitch.

📞 Recommended Opener:
   "Hi Alex, this is Matt from The Tustin Group — we're a
   commercial building services company serving the greater
   Hatfield area. Given your role in operations, I wanted to
   reach out directly..."

📜 Script Used: Script 1 / Script 5 (hybrid)

⚠️ Objections: 2 returned
❓ Follow-ups: 2 returned
```

---

# 🧪 TEST 3: `/copilot/respond` — Live Call Suggestions

## TEST 3.1 — Vendor Locked ✅
**Input:** `says he has Johnson Controls for 10 years`

**Expected Output:**
```
🏷️ Intent:      VENDOR_LOCKED
💬 Suggestion:  "Johnson Controls is solid — when's that agreement
               up for renewal? We're not trying to replace them,
               just want to be on your radar if you ever want to
               benchmark."
```

## TEST 3.2 — Not Interested ✅
**Input:** `not interested`

**Expected Output:**
```
🏷️ Intent:      NOT_INTERESTED
💬 Suggestion:  "No problem — just curious, are you handling water
               treatment and fire systems in-house too, or is that
               where you'd want a partner?"
```

## TEST 3.3 — Pricing Question ✅
**Input:** `asking about pricing`

**Expected Output:**
```
🏷️ Intent:      PRICE_QUESTION
💬 Suggestion:  "Happy to walk through pricing — it really depends
               on your building size and what services you need.
               What's your square footage, and are you currently
               on any kind of maintenance agreement?"
```

## TEST 3.4 — Gatekeeper ✅
**Input:** `he's not the right person`

**Expected Output:**
```
🏷️ Intent:      GATEKEEPER
💬 Suggestion:  "Got it — who handles the building systems or HVAC
               decisions? Is that you, or is there someone else
               I should connect with?"
```

## TEST 3.5 — In-House Team ✅
**Input:** `they handle everything in-house`

**Expected Output:**
```
🏷️ Intent:      OTHER
💬 Suggestion:  "Got it — do you have in-house coverage for water
               treatment and fire systems too, or mainly just the
               HVAC side?"
```

## TEST 3.6 — Interested (Positive Signal) ✅
**Input:** `send him details, he's interested`

**Expected Output:**
```
🏷️ Intent:      INTERESTED
💬 Suggestion:  "Perfect — I'll get those over to him today. Just
               to make sure I'm sending the right info, is he
               looking more at maintenance agreements or energy
               optimization?"
```

---

# 🎬 5-Minute Demo Script for Matt

Show these in order — proves all 3 endpoints + all 3 use cases:

### Step 1 — Lookup (10 sec)
**Type:** `lookup Adam Lord`
**Show:** *"This is how the bot finds any lead in your list instantly."*

### Step 2 — Brief for Decision Maker (60 sec)
**Type:** `brief me on Adalberto Dejesus`
**Show:** *"Before you dial, you get a full strategy: opener, objections, follow-ups — all using YOUR scripts."*

### Step 3 — Brief for In-House (60 sec)
**Type:** `brief me on Leigh Guarino`
**Show:** *"Notice how the bot says DON'T pitch Leigh — he's maintenance, not a decision maker. Different strategy automatically."*

### Step 4 — Live Objection (45 sec)
**Type:** `says he has Johnson Controls 10 years`
**Show:** *"Mid-call, type 3 words. Bot gives you the comeback in 5 seconds. This is your real-time coach."*

### Step 5 — Different Objection (45 sec)
**Type:** `asking about pricing`
**Show:** *"Different objection, different response — bot understands context and uses your discovery questions."*

### Step 6 — Lookup Edge Case (15 sec)
**Type:** `lookup John Smith Random`
**Show:** *"Bot won't make stuff up — if the lead isn't in your list, it tells you."*

**Total: ~4-5 minutes. Drops the mic.** 🎤

---

# ✅ Pre-Demo Checklist

Before showing Matt, verify:

- [ ] All 3 tools show "Enabled" in Copilot Studio
- [ ] Connection shows green checkmark
- [ ] "After running" set to "Write the response with generative AI"
- [ ] Railway env vars include OPENROUTER_API_KEY
- [ ] Test panel loads without errors
- [ ] Test queries above all return expected responses

---

# 🚨 Backup Plan if Demo Fails

If the bot doesn't respond during the demo:

### Plan A: Show curl outputs directly
You have all the responses captured above. Open this doc and read them.

### Plan B: Run curl live
```bash
curl -X POST https://tt-production-da10.up.railway.app/copilot/brief \
  -H "Content-Type: application/json" \
  -d '{"lead_name":"Adalberto Dejesus"}'
```

### Plan C: Show the Excel
Open `Tustin Group Lead Gen list.xlsx` — show the enriched columns directly. The data is there.

---

*Generated: 2026-05-17 from live Railway API at https://tt-production-da10.up.railway.app*
