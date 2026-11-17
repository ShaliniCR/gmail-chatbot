#!/usr/bin/env python3
"""
FastAPI backend for the TrainerCentral Assignment Chatbot.

Flow:
  1. Frontend (React) POSTs conversation to /api/chat.
  2. Fetches fresh data from the TrainerCentral Text Dashboard API.
  3. Claude answers questions based strictly on the fetched data.
  4. Serves the built React frontend static files from /frontend/dist when available.

Run locally:
  uvicorn backend.main:app --reload --port 8000
"""

import json
import os
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load local .env if present (in development)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TRAINER_API_KEY = os.environ.get("TRAINER_API_KEY")
DEFAULT_MODEL = "claude-sonnet-5-5"
# Older Claude 3.x model IDs (e.g. claude-3-5-sonnet-20241022) are retired and return 404,
# which surfaced as a 502 from /api/chat. Ignore a stale value if one is still configured.
_configured_model = (os.environ.get("ANTHROPIC_MODEL") or "").strip()
MODEL = DEFAULT_MODEL if (not _configured_model or _configured_model.startswith("claude-3")) else _configured_model
DASHBOARD_API_BASE = os.environ.get(
    "DASHBOARD_API_BASE", "https://trainer-central-assigments-api.onrender.com"
)

SYSTEM_PROMPT = """You are a helpful assistant answering questions about a TrainerCentral
assignment-submission dashboard.

You will be given the current dashboard data as JSON (entries, learners, stats) followed by
a conversation with a user. Answer the user's question using ONLY the data provided -
don't make anything up. Count, filter, and summarize the data yourself as needed
(e.g. counting how many entries mention a particular learner). Be concise and
conversational. If the data doesn't let you answer, say so plainly.
"""

app = FastAPI(title="Assignment Chatbot")

# CORS middleware for when frontend and backend are hosted on separate domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] | None = None
    message: str | None = None


def get_anthropic_client() -> anthropic.Anthropic:
    """Return an Anthropic client, raising a clear HTTPException if the API key is missing."""
    api_key = os.environ.get("ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "ANTHROPIC_API_KEY is not set. Please configure ANTHROPIC_API_KEY in your "
                "Render environment variables or local .env file."
            ),
        )
    return anthropic.Anthropic(api_key=api_key)


def fetch_dashboard_data() -> dict:
    headers = {"x-api-key": TRAINER_API_KEY} if TRAINER_API_KEY else {}
    data = {}

    endpoints = {
        "entries": ("/api/entries", {"limit": 500}),
        "learners": ("/api/learners", None),
        "stats": ("/api/stats", None),
    }
    for key, (path, params) in endpoints.items():
        try:
            resp = requests.get(
                f"{DASHBOARD_API_BASE}{path}",
                headers=headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data[key] = resp.json()
        except requests.RequestException as e:
            data[key] = {"error": str(e)}
    return data


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "anthropic_configured": bool(os.environ.get("ANTHROPIC_API_KEY") or ANTHROPIC_API_KEY),
        "trainer_key_configured": bool(os.environ.get("TRAINER_API_KEY") or TRAINER_API_KEY),
        "model": MODEL,
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    if req.messages:
        claude_messages = [{"role": m.role, "content": m.content} for m in req.messages]
    elif req.message:
        claude_messages = [{"role": "user", "content": req.message}]
    else:
        raise HTTPException(
            status_code=400,
            detail="Request body must include either 'messages' or 'message'.",
        )

    client = get_anthropic_client()
    dashboard_data = fetch_dashboard_data()

    system = SYSTEM_PROMPT + "\n\nCurrent dashboard data (JSON):\n" + json.dumps(dashboard_data, indent=2)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=claude_messages,
        )
    except anthropic.AuthenticationError as e:
        raise HTTPException(
            status_code=502,
            detail=(
                "Claude API Authentication Error (401 invalid x-api-key): "
                "Your ANTHROPIC_API_KEY is invalid. Please make sure you are using an API key from "
                "https://console.anthropic.com/settings/keys (starts with 'sk-ant-api03-...'), "
                "not a Claude.ai user session token."
            ),
        ) from e
    except anthropic.NotFoundError as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Claude model '{MODEL}' was not found (it may be retired). "
                f"Set ANTHROPIC_MODEL to a current model such as '{DEFAULT_MODEL}'. Details: {e.message}"
            ),
        ) from e
    except anthropic.BadRequestError as e:
        raise HTTPException(status_code=502, detail=f"Claude API rejected the request: {e.message}") from e
    except anthropic.RateLimitError as e:
        raise HTTPException(status_code=429, detail=f"Claude API Rate Limit Exceeded: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach the Claude API: {e}") from e

    if response.stop_reason == "refusal":
        return {"reply": "Sorry, I can't help with that request."}

    reply = "".join(block.text for block in response.content if block.type == "text").strip()
    return {"reply": reply}


# --- Static frontend serving (for unified Render full-stack deployment) ---
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def serve_root_fallback():
        return {
            "message": "Assignment Chatbot API is running.",
            "health_check": "/api/health",
            "frontend_status": "Frontend dist not found. Build frontend (`npm run build`) to serve the UI from here.",
        }
