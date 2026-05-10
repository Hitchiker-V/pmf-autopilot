from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
# pyrefly: ignore [missing-import]
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS for Vercel landing pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook/signal")
async def capture_signal(request: Request):
    payload = await request.json()
    # Forward to Edge Function or insert directly
    await supabase.table("signals").insert(payload).execute()
    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    print("Hello")
    uvicorn.run(app, host="0.0.0.0", port=8000)