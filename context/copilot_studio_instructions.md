# Copilot Studio — Agent Setup Guide

End-to-end setup for the Tustin CoPilot agent at <https://copilotstudio.microsoft.com>.

Three things to configure:

1. **Agent instructions** — paste-in text that tells the LLM how to route messages and format output.
2. **Custom connector / Tools** — import `copilot_openapi.json` so the agent can call `brief`, `lookup`, and `respond`.
3. **"Upload Leads" Topic + Power Automate flow** — handles file uploads (Matt drops an `.xlsx` in chat → bucket → success message). The LLM stays out of this path.

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
- If user UPLOADS / ATTACHES a file, or says "enrich this", "upload leads", "process this file", "run enrichment" → DO NOT call any tool. The "Upload Leads" Topic handles this automatically. Stay silent and let the Topic trigger.
- If ambiguous → ask a clarifying question
```

---

## 2️⃣ Tools (custom connector)

Import `context/copilot_openapi.json` so the LLM has access to the right actions.

### Which actions the LLM should see

| Action      | OperationId         | When the LLM calls it                         |
|-------------|---------------------|-----------------------------------------------|
| brief       | `GetPreCallBrief`   | "tell me about X", "prep me for X", bare name |
| lookup      | `LookupLeadByName`  | "find X", "lookup X"                          |
| respond     | `GetLiveSuggestion` | `<prospect just said …>`                      |

> **Why upload-file is NOT in this spec:** Copilot Studio converts uploaded OpenAPI 3.0 specs to Swagger 2.0 internally, and the conversion fails on `multipart/form-data` + `format: binary` schemas with `JSON does not match any schemas from 'anyOf'`. Since the upload endpoint is meant to be called by the Power Automate flow (not the LLM), it doesn't need a connector registration at all — the flow's plain HTTP action calls the Railway URL directly. See section 3a.

### Import steps

1. Agent → **Tools** → **+ Add a tool** → **New tool** → **Custom connector** → **New custom connector**.
2. Power Automate opens → **Custom connectors** → **+ New custom connector** → **Import an OpenAPI file**.
3. Upload `context/copilot_openapi.json`. Name it `Tustin CoPilot API`.
4. **Security:** No authentication (the endpoints are public; gate at the network layer if needed later).
5. **Create connector** → switch to **Test** → exercise each action with the sample payloads from the spec.
6. Back in Copilot Studio → **Tools** → **+ Add a tool** → pick `Tustin CoPilot API` → enable **brief**, **lookup**, **respond**.

---

## 3️⃣ "Upload Leads" Topic + Power Automate flow

This is the path for Matt dropping an `.xlsx` in chat. **Build the flow first**, then the Topic that calls it.

### 3a. Power Automate flow — `Upload Leads File`

1. <https://make.powerautomate.com> → **+ Create** → **Instant cloud flow**.
2. Name: `Upload Leads File`. Trigger: **When Copilot Studio calls a flow**.
3. In the trigger → **+ Add an input** → type **File** → name it `LeadsFile`.
4. **+ New step** → **HTTP** (built-in premium connector).
   - **Method:** `POST`
   - **URI:** `https://tt-production-da10.up.railway.app/copilot/upload-file`
   - **Body** → expand **Show advanced options** → set **Body Type** to **multipart/form-data**.
   - Add a form-data part:
     - **Name:** `file`
     - **Body:** dynamic content → `LeadsFile.contentBytes`
     - **Filename:** dynamic content → `LeadsFile.name`
     - **Content type:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
5. **+ New step** → **Parse JSON**.
   - **Content:** `Body` (from the HTTP step)
   - **Schema:** use *Generate from sample* and paste a real success response, e.g.:
     ```json
     {
       "status": "success",
       "filename": "test_leads.xlsx",
       "storage_path": "20260521_104530_test_leads.xlsx",
       "storage_url": "https://wzhqsmaunimgvowkdegl.supabase.co/storage/v1/object/public/uploaded-leads/20260521_104530_test_leads.xlsx",
       "rows_detected": 5,
       "columns_detected": 12,
       "message": "File uploaded successfully — 5 leads detected in test_leads.xlsx. Reply 'enrich it' to start enrichment."
     }
     ```
6. **+ New step** → **Respond to Copilot Studio**. Add outputs:
   - `message` (String) → dynamic content → `message` from Parse JSON
   - `status` (String) → `status`
   - `rows_detected` (Number) → `rows_detected`
7. **Save**.

### 3b. Copilot Studio Topic — `Upload Leads`

1. Open the agent → **Topics** → **+ Add a topic** → **From blank**.
2. Name: `Upload Leads`.
3. **Trigger phrases** (one per line):
   - `enrich this file`
   - `upload leads`
   - `process this file`
   - `enrich my leads`
   - `run enrichment`
4. **+ Add node** → **Ask a question**:
   - Question: `Sure — drop your .xlsx lead file here and I'll stage it.`
   - **Identify:** *File* (under "User's entire response")
   - Save user response as: `LeadsFile`
5. **+ Add node** → **Call an action** → **Add a flow** → pick `Upload Leads File`.
   - Map input `LeadsFile` → `Topic.LeadsFile`.
6. **+ Add node** → **Condition**:
   - `Topic.UploadLeadsFile.status` *equals* `success`
   - **Yes branch:** **Send a message** → dynamic content → `Topic.UploadLeadsFile.message`
   - **No (or "All other conditions") branch:** **Send a message** → `Something went wrong uploading the file. Please try again, or check the file is a valid .xlsx under 25 MB.`
7. **Save** → click **Publish** (top right of the agent). The Topic does not fire until you publish.

---

## 4️⃣ End-to-end test

In Teams (after publishing the agent):

| Test | Steps | Expected |
|------|-------|----------|
| Happy path | Type `enrich this file` → drag in `tests/test_leads.xlsx` | Bot replies within ~5 sec: `File uploaded successfully — 5 leads detected in test_leads.xlsx…` Supabase `uploaded-leads` bucket gets a new object. |
| Wrong file type | Type `upload leads` → drop a `.pdf` | Bot replies with the error fallback message. Power Automate run shows `400 Only .xlsx or .xls files are accepted`. |
| Empty file | Drop a fresh empty `.xlsx` | Bot replies with the error fallback. Backend log shows `Excel file is empty`. |
| Brief still works | Type `brief me on Leigh Guarino` | LLM calls the `brief` tool and renders the structured response. No Topic fires. |
| LLM stays out of upload | Type `process this file` *without* attaching anything | Topic asks for the file (does not try to call any tool itself). |

### Where to debug if something is off

- **Flow run history** (`make.powerautomate.com` → My flows → `Upload Leads File` → Run history): shows the exact body sent to Railway and the response received. This is the single best debugging surface.
- **Railway deploy logs**: confirm the request hit the backend; look for `Parsed N rows` and `Uploaded uploaded-leads/...`.
- **Supabase Storage** dashboard: confirm the file landed in the `uploaded-leads` bucket.
- **Copilot Studio Topic test pane** (left panel of the Topic editor): step through the Topic with a fake file to verify the Condition branches.
