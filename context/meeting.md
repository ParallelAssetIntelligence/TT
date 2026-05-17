AI SALES CO-PILOT
Meeting Summary, Sales Intelligence Q&A & Agent Build Specification
Meeting Date: May 14, 2025  |  Participants: Matt Pindilli, Andrew (Vendor Re-Aline)


SECTION 1: MEETING SUMMARY
This working session between Matt (sales rep) and Andrew (vendor/builder) focused on understanding the current cold-calling workflow and exploring how to enrich lead lists with LinkedIn data to generate personalized outreach scripts. The meeting also surfaced key objections, ideal contact profiles, and call tactics that will inform the AI co-pilot build.

Key Outcomes
Andrew will enrich Matt's 700-row lead list with LinkedIn data (tenure, past companies, job title)
Andrew will generate personalized outreach scripts based on profile signals (new hire vs. long-tenured)
Matt will send a fresh lead list (not yet called) and a vertical market breakdown
Andrew will send a Loom walkthrough of the enriched file and proposed scripts
The team will test personalized scripts on live calls and evaluate callback/connection rates



SECTION 2: SALES INTELLIGENCE Q&A
The following captures Andrew's questions and Matt's answers in sequential order from the meeting. This serves as the ground-truth input for building the AI agent's knowledge base and script logic.

CATEGORY 1: Current Call Workflow & Channel Strategy

Q (Andrew): Are you calling cell phones or landlines?
A (Matt): We prefer cell phones, but most contacts don't list them. So we end up calling desk phones or HQ main lines — then trying to get transferred. That's mostly useless. We've found way more success reaching people on cell phones. Nobody answers desk phones anymore; some offices have removed them entirely.


Q (Andrew): Have you run into the iOS live voicemail feature where it asks you to identify yourself before connecting?
A (Matt): No, I haven't really run into that. I don't get many calls on my cell. But if we could craft a good message that generates callbacks, we'd start using that approach.


Q (Andrew): Do you currently leave voicemails?
A (Matt): No. Jim told us not to leave voicemails — we haven't found much success with them. But if we had a strong voicemail script, we'd test it.


CATEGORY 2: Lead Data & Research Process

Q (Andrew): Do you do any research before calling?
A (Matt): None. I just make calls. The leads come from ZoomInfo — we export every facility manager in Pennsylvania and go from there. No vetting, no enrichment, no pre-call research.


Q (Andrew): Have you called most of the people on this 700-row list already?
A (Matt): Probably most of them, yeah.


Q (Andrew): Would it help to know if a contact is a new hire vs. long-tenured?
A (Matt): Yes. If someone just joined, I'd say something like: 'Hey, I know you're new in the role — we've helped similar facilities reduce costs, I'd love to schedule time to discuss how we can do that for you.' If they've been there 30 years, I'd challenge their complacency: 'What's your process for making sure your facility is still saving as much money as possible? Has your current vendor come out to review all your systems?'


Q (Andrew): Would knowing past companies or career history be useful?
A (Matt): Yes — especially if they previously worked somewhere we had a contract with, or if we knew who their vendor was at their old building. That's a strong in.


CATEGORY 3: Objection Handling & Common Scenarios

Q (Andrew): What's the biggest objection you run into on calls?
A (Matt): The immediate 'I'm not interested, bye.' Or: 'I already have a vendor, I don't need you.' The easy button — they've been with someone for 5-10 years, don't want the hassle of switching. That's our biggest blocker.


Q (Andrew): What script do you use when someone is locked in with an existing vendor like Johnson Controls?
A (Matt): I'll say: 'I know you've been with them a long time — what's your process for making sure your facility is still saving as much money as possible? Has your current company come out and reviewed all your systems to make sure everything is running at peak efficiency?' That plants a seed of doubt without being confrontational.


Q (Andrew): What about companies with a new building — is that a useful signal?
A (Matt): Yes, but timing matters. Normally there's a 1-year contract built into the construction deal. But if we can time it right — like calling in 2026 on a building completed in late 2025 — a lot of those guys hate the construction company by then and don't want to renew. That's a warm window.


Q (Andrew): Are there any other common scenarios?
A (Matt): Not many. It's mostly: 'I have a vendor, I'm not switching.' New hire and long-tenured are the two main profiles worth scripting around.


CATEGORY 4: Contact Qualification & Title Filtering

Q (Andrew): Do job titles matter — like Director of Facilities vs. Maintenance Manager?
A (Matt): Hugely. 'Director of Facilities' is our ideal — they make vendor decisions. 'Maintenance Manager' or anything with 'Maintenance' is usually an in-house guy who works ON the systems, not someone who hires outside vendors. They'll either say 'talk to my boss' or think we're going to take their job.


Q (Andrew): What do you do when you hit a gatekeeper or bad title?
A (Matt): I call the main line and ask for 'the person in charge of making financial decisions as it pertains to the building.' That language works — they never route you to the maintenance guy. If I say 'who handles HVAC,' they send me to the janitor.


CATEGORY 5: Vertical Markets & Success Rates

Q (Andrew): Are you mostly calling schools and churches?
A (Matt): No, schools are actually one of our harder verticals — especially public schools. Too much red tape. Private institutions are slightly better. I can send you our full vertical market list with a pros/cons breakdown.


Q (Andrew): What was the best lead you've booked recently?
A (Matt): Widener University — a university contact who was a former Controls customer. He said we priced ourselves out of his building. He's been with Elliot Lewis for chillers since 2023. He has a summer project when school is closed and wants us to bid on it, with a path to earning his PM business. Booked a meeting off that call.




SECTION 3: AI AGENT BUILD SPECIFICATION
The following is the standard operating procedure and technical specification for the AI Sales Co-Pilot, derived directly from Matt's workflow insights and this discovery session.

Step1
INGEST — Weekly Lead List Upload
Matt drops the following week's lead CSV into a designated SharePoint folder (or emails to a monitored inbox). Trigger: file detected in folder. Format: ZoomInfo export (name, company, title, phone, city/state). Agent validates required columns and flags missing fields before proceeding.


Step2
ENRICH — LinkedIn Profile Scraping
Agent cross-references each contact (name + company + city/state) against LinkedIn. Pulls: current title, tenure at current company, prior companies and roles, career history length. Flags: new hire (< 1 year at company), long-tenured (5+ years), recent company mover (changed jobs in past 12 months), title qualifier (Director-level vs. Maintenance/Facilities Coordinator). Also checks for: new building permits or construction projects tied to the company, recent acquisitions or facility expansions.


Step3
SCRIPT — Personalized Outreach Generation
Agent generates a 2-3 sentence personalized opener for each contact based on enrichment signals. Script logic tree:• New hire (<1 yr): 'Hey [Name], I saw you recently joined [Company] — we work with a lot of facilities teams going through that onboarding ramp and have helped reduce costs quickly. I'd love to grab 15 minutes.'• Long-tenured (5+ yrs): 'You've been managing [Company] for a long time — what's your process for making sure you're still getting max savings? Has your current vendor done a full systems review lately?'• Known vendor (from call notes): 'I know you've been with [Vendor] — I'm not here to replace them overnight, just want to see if there are any gaps worth reviewing.'• New/post-construction building: 'I saw [Company] completed their new facility recently — now that the construction contract window is closing, are you evaluating your ongoing service vendors?'• Career mover: 'I noticed you came over from [Prior Company] — did you bring any vendor relationships with you or starting fresh?'


Step4
DELIVER — Enriched File to SharePoint
Agent writes the completed enriched Excel file back to a designated SharePoint folder. Output columns added: LinkedIn_URL, Tenure_Years, Prior_Company_1, Prior_Company_2, Title_Qualifier (Director / Manager / Maintenance / Unknown), Signal_Tag (New Hire / Long Tenured / Career Mover / New Building / Prior Customer), Personalized_Opener, Call_Notes (pre-populated from prior ZoomInfo/CRM data if available). Notification sent to Matt via Teams or email when file is ready.


Step5
PRE-CALL — Matt Reviews Co-Pilot Brief
Before dialing, Matt opens the enriched file row for the contact. Agent surfaces a one-page 'call brief' per contact: Signal summary (why this person, why now), Recommended opener (from Step 3), Top 2 objections likely based on profile, Suggested follow-up questions. Matt can also query the agent in plain English: 'What do I know about this person?' and get a synthesized response.


Step6
LIVE CALL — Real-Time Co-Pilot Assist
During the call, Matt types keywords or short phrases into the co-pilot interface. The agent uses the contact's enrichment data + the in-call context to suggest next responses in real time.Example triggers and agent responses:• Matt types: 'Says he has Johnson Controls 10 years'  Agent suggests: 'What's your process for making sure they're still delivering value? Have they done a full systems audit in the last 2 years?'• Matt types: 'Says he's not interested'  Agent suggests: 'Totally understand — just one question before I let you go: if you could save 15% on your facility costs without switching vendors, would that be worth a 20-minute conversation?'• Matt types: 'New hire, seems open'  Agent suggests: 'Since you're still getting settled in, this is actually a great time to benchmark what's in place. We can do a no-cost assessment so you know exactly what you're working with.'• Matt types: 'Asking about pricing'  Agent suggests: 'We don't do fixed pricing — it's always scoped to your specific systems. What I can do is set up a walk-through so we can give you an accurate number. Is there a week that works?'Interface: lightweight chat-style text box Matt can type into mid-call. Agent responds in under 3 seconds. Responses kept to 1-2 sentences max (actionable, conversational).




IMMEDIATE ACTION ITEMS

Action
Owner
Status
Send fresh (uncalled) lead list to Andrew
Matt
Pending
Send vertical market list with pros/cons
Matt
Pending
Enrich 700-row list with LinkedIn data (tenure, prior roles)
Andrew
In Progress
Generate personalized opener scripts by contact segment
Andrew
In Progress
Send Loom walkthrough of enriched file to Matt
Andrew
Pending
Test personalized scripts on live calls, track connect/book rate
Matt
Pending
Define SharePoint folder structure for lead file handoff
PAI / Both
Pending
Scope live co-pilot interface (Step 6) — UI + API
PAI Engineering
Pending


