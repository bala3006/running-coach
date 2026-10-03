import asyncio
import os
import uuid
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from running_coach.embeddings import (
    embedding_model,
    index_pending_training_memory,
    training_memory_stats,
)
from running_coach.integrations import get_recent_runs, get_run_descent
from running_coach.ollama import chat_with_ollama
from running_coach.oauth import router as integration_router
from running_coach.prompts import LANGUAGES
from running_coach.db import (
    get_history,
    list_race_goals,
    list_runs,
    save_exchange,
    save_race_goal,
    save_run_reflection,
    upsert_runs,
)
from running_coach.training import project_race_goal

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


class RunReflectionRequest(BaseModel):
    feeling: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=2000)
    perceived_effort: int | None = Field(default=None, ge=1, le=10)
    temperature_c: float | None = Field(default=None, ge=-50, le=60)
    humidity_pct: float | None = Field(default=None, ge=0, le=100)


class RaceGoalRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    event_date: date
    distance_km: float = Field(gt=0, le=1000)
    target_time_seconds: int = Field(gt=0, le=864000)


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/architecture", include_in_schema=False)
async def architecture() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "docs" / "architecture.html")


@app.get("/architecture/linkedin.png", include_in_schema=False)
async def linkedin_architecture() -> FileResponse:
    return FileResponse(
        PROJECT_ROOT / "docs" / "thunai-ai-linkedin-architecture.png",
        media_type="image/png",
        filename="thunai-ai-linkedin-architecture.png",
    )


@app.get("/api/health")
async def health() -> dict[str, str | bool | int]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    embed_model = embedding_model()
    memory_stats = training_memory_stats(embed_model)
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
        installed_models = {item.get("name") for item in response.json().get("models", [])}
        return {
            "ollama": True,
            "model": model,
            "model_available": model in installed_models,
            "embedding_model": embed_model,
            "embedding_model_available": embed_model in installed_models,
            "memory_total": memory_stats["total"],
            "memory_embedded": memory_stats["embedded"],
        }
    except Exception:
        return {
            "ollama": False,
            "model": model,
            "model_available": False,
            "embedding_model": embed_model,
            "embedding_model_available": False,
            "memory_total": memory_stats["total"],
            "memory_embedded": memory_stats["embedded"],
        }


@app.post("/api/training/sync")
async def sync_training(
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, str | int | bool]:
    try:
        activities = await get_recent_runs(days)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not sync recent Strava runs.") from exc

    semaphore = asyncio.Semaphore(5)

    async def add_descent(activity: dict) -> None:
        activity_id = activity.get("id")
        if not activity_id or activity.get("descent_m") is not None:
            return
        try:
            async with semaphore:
                activity["descent_m"] = await get_run_descent(activity_id)
        except (httpx.HTTPError, RuntimeError):
            return

    await asyncio.gather(*(add_descent(activity) for activity in activities))
    synced = upsert_runs(activities)
    indexing = await index_pending_training_memory()
    return {"synced": synced, "days": days, **indexing}


@app.post("/api/training/reindex")
async def reindex_training_memory() -> dict[str, str | int | bool]:
    return await index_pending_training_memory()


@app.get("/api/training/runs")
async def training_runs() -> dict[str, list[dict]]:
    return {"runs": list_runs()}


@app.put("/api/training/runs/{activity_id}/reflection")
async def save_reflection(activity_id: str, request: RunReflectionRequest) -> dict[str, str | int | bool]:
    try:
        save_run_reflection(
            activity_id,
            request.feeling,
            request.notes,
            request.perceived_effort,
            request.temperature_c,
            request.humidity_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"saved": True, **(await index_pending_training_memory())}


def _race_with_projection(goal: dict) -> dict:
    return {
        **goal,
        "assessment": project_race_goal(
            list_runs(),
            goal["distance_km"],
            goal["target_time_seconds"],
            goal["event_date"],
        ),
    }


@app.get("/api/training/races")
async def training_races() -> dict[str, list[dict]]:
    return {"races": [_race_with_projection(goal) for goal in list_race_goals()]}


@app.post("/api/training/races", status_code=201)
async def create_race_goal(request: RaceGoalRequest) -> dict:
    goal_id = save_race_goal(
        request.name.strip(),
        request.event_date.isoformat(),
        request.distance_km,
        request.target_time_seconds,
    )
    indexing = await index_pending_training_memory()
    goal = next(goal for goal in list_race_goals() if goal["id"] == goal_id)
    return {**_race_with_projection(goal), "embedding_index": indexing}


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
