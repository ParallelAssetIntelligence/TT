# Create virtual environment
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload




✅ Option A: Polling with service account (my recommendation)

Cron (hourly) → Drive API files.list → files.get (download) → Supabase
Auth: Service account JSON key (no user OAuth, no token refresh).
API calls:
files.list(q="'<FOLDER_ID>' in parents and mimeType='...spreadsheet' and modifiedTime > '<last_sync>'", fields="files(id,name,modifiedTime,size,mimeType)")
files.get_media(fileId=...) → returns raw bytes
Pros: simple, no expiry, fully server-to-server, no user interaction.
Cons: up to 1-hour latency.