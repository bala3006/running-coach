import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from running_coach.credentials import get_credential, set_credential
from running_coach.integrations import GOOGLE_TOKEN_URL, STRAVA_TOKEN_URL

router = APIRouter(prefix="/api/integrations")
STATE_COOKIE = "running_coach_oauth_state"
CALLBACK_BASE = "http://127.0.0.1:8000/api/integrations"


def _state_cookie(provider: str) -> str:
    return f"{STATE_COOKIE}_{provider}"


def _start_oauth(provider: str, authorization_url: str, extra: dict, scope: str) -> RedirectResponse:
    client_id = os.getenv(f"{provider.upper()}_CLIENT_ID")
    if not client_id or not os.getenv(f"{provider.upper()}_CLIENT_SECRET"):
        raise HTTPException(503, detail=f"Add {provider} OAuth credentials to .env first.")
    if provider == "google" and not os.getenv("GOOGLE_SHEET_ID"):
        raise HTTPException(503, detail="Set GOOGLE_SHEET_ID in .env before connecting Sheets.")
    state = secrets.token_urlsafe(32)
    callback = f"{CALLBACK_BASE}/{provider}/callback"
    query = {
        "client_id": client_id,
        "redirect_uri": callback,
        "response_type": "code",
        "scope": scope,
        "state": state,
        **extra,
    }
    response = RedirectResponse(f"{authorization_url}?{urlencode(query)}")
    response.set_cookie(
        _state_cookie(provider),
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return response


async def _finish_oauth(provider: str, request: Request, code: str, state: str) -> RedirectResponse:
    if not state or not secrets.compare_digest(
        state, request.cookies.get(_state_cookie(provider), "")
    ):
        raise HTTPException(400, detail="OAuth state check failed. Start the connection again.")
    client_id = os.getenv(f"{provider.upper()}_CLIENT_ID")
    client_secret = os.getenv(f"{provider.upper()}_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(503, detail=f"Add {provider} OAuth credentials to .env first.")
    callback = f"{CALLBACK_BASE}/{provider}/callback"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }
    if provider == "strava":
        data["redirect_uri"] = callback
    else:
        data["redirect_uri"] = callback

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            STRAVA_TOKEN_URL if provider == "strava" else GOOGLE_TOKEN_URL,
            data=data,
        )
        token_response.raise_for_status()
    token = token_response.json()
    if provider == "google" and not token.get("refresh_token"):
        previous = get_credential("google") or {}
        token["refresh_token"] = previous.get("refresh_token")
    token["expires_at"] = token.get("expires_at", int(time.time()) + token.get("expires_in", 3600))
    set_credential(provider, token)
    response = RedirectResponse("/")
    response.delete_cookie(_state_cookie(provider))
    return response


@router.get("/status")
async def status() -> dict[str, bool]:
    from running_coach.integrations import integration_status

    return integration_status()


@router.delete("/{provider}")
async def disconnect(provider: str) -> dict[str, bool]:
    if provider not in {"strava", "google"}:
        raise HTTPException(404, detail="Unknown integration.")
    from running_coach.credentials import delete_credential

    delete_credential(provider)
    return {"connected": False}


@router.get("/strava/connect")
async def connect_strava() -> RedirectResponse:
    return _start_oauth(
        "strava",
        "https://www.strava.com/oauth/authorize",
        {"approval_prompt": "auto"},
        "read,activity:read_all",
    )


@router.get("/strava/callback")
async def strava_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    return await _finish_oauth("strava", request, code, state)


@router.get("/google/connect")
async def connect_google() -> RedirectResponse:
    return _start_oauth(
        "google",
        "https://accounts.google.com/o/oauth2/v2/auth",
        {"access_type": "offline", "prompt": "consent"},
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    )


@router.get("/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    return await _finish_oauth("google", request, code, state)
