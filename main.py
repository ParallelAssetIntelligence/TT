from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.databaseconnection import supabase_manager
from app.routes.leads import router as leads_router

app = FastAPI(title="Tustin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(leads_router)


@app.get("/")
async def root():
    return {"message": "Tustin API is running"}


@app.get("/health")
async def health():
    db_status = supabase_manager.test_connection()
    return {"api": "healthy", "database": db_status}


@app.get("/test-supabase-connection")
async def test_supabase_connection():
    import os
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    return {
        "env": {
            "SUPABASE_URL": url[:30] + "..." if len(url) > 30 else url,
            "SUPABASE_KEY_prefix": key[:20] + "..." if len(key) > 20 else key,
            "SUPABASE_KEY_length": len(key),
            "key_starts_with_eyJ": key.startswith("eyJ"),
        },
        "client_initialized": supabase_manager.is_connected(),
        "connection_test": supabase_manager.test_connection(),
    }
