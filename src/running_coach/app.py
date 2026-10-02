import os
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from running_coach.ollama import chat_with_ollama
from running_coach.oauth import router as integration_router
from running_coach.prompts import LANGUAGES
from running_coach.db import get_history, save_exchange

load_dotenv()

ROOT = Path(__file__).parent
PROJECT_ROOT = ROOT.parents[1]
app = FastAPI(title="Thunai AI · Coach Eklavya", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.include_router(integration_router)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = "en-ta"
    tamil_voice: bool = True
    session_id: uuid.UUID | None = None


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/architecture", include_in_schema=False)
async def architecture() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "docs" / "architecture.html")


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
        installed_models = {item.get("name") for item in response.json().get("models", [])}
        return {"ollama": True, "model": model, "model_available": model in installed_models}
    except Exception:
        return {"ollama": False, "model": model, "model_available": False}


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, str]:
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Write a message for your coach.")
    if request.language not in LANGUAGES:
        raise HTTPException(status_code=422, detail="Choose English, Tamil, or Tanglish.")
    try:
        session_id = str(request.session_id or uuid.uuid4())
        user_message = request.message.strip()
        response = await chat_with_ollama(
            user_message,
            request.language,
            request.tamil_voice,
            get_history(session_id),
        )
        save_exchange(session_id, user_message, response)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not reach Ollama. Check that it is running and the selected model is installed.",
        ) from exc
    return {"response": response, "session_id": session_id}


@app.get("/api/chat/{session_id}/history")
async def chat_history(session_id: uuid.UUID) -> dict[str, list[dict[str, str]]]:
    return {"messages": get_history(str(session_id))}
