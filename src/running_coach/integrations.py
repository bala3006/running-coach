import os
import time
from urllib.parse import quote

import httpx

from running_coach.credentials import get_credential, set_credential

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def integration_status() -> dict[str, bool]:
    return {
        "strava": bool(get_credential("strava")),
        "strava_configured": bool(
            os.getenv("STRAVA_CLIENT_ID") and os.getenv("STRAVA_CLIENT_SECRET")
        ),
        "google_sheets": bool(get_credential("google"))
        and bool(os.getenv("GOOGLE_SHEET_ID")),
        "google_configured": bool(
            os.getenv("GOOGLE_CLIENT_ID")
            and os.getenv("GOOGLE_CLIENT_SECRET")
            and os.getenv("GOOGLE_SHEET_ID")
        ),
    }


async def _service_token(provider: str) -> dict:
    credential = get_credential(provider)
    if not credential:
        raise RuntimeError(f"{provider} is not connected. Connect it in local settings first.")
    if credential.get("expires_at", 0) > time.time() + 60:
        return credential

    refresh_token = credential.get("refresh_token")
    client_id = os.getenv(f"{provider.upper()}_CLIENT_ID")
    client_secret = os.getenv(f"{provider.upper()}_CLIENT_SECRET")
    if not refresh_token or not client_id or not client_secret:
        raise RuntimeError(f"{provider} needs to be reconnected to refresh its access.")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            STRAVA_TOKEN_URL if provider == "strava" else GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
    refreshed = response.json()
    refreshed["expires_at"] = refreshed.get("expires_at", int(time.time()) + 3600)
    refreshed["refresh_token"] = refreshed.get("refresh_token", refresh_token)
    set_credential(provider, refreshed)
    return refreshed


async def get_recent_runs(days: int = 30) -> list[dict]:
    if not 1 <= days <= 90:
        raise ValueError("days must be between 1 and 90")
    credential = await _service_token("strava")
    after = int(time.time()) - days * 24 * 60 * 60
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {credential['access_token']}"},
            params={"after": after, "per_page": 100},
        )
        response.raise_for_status()
    activities = response.json()
    return [
        {
            "name": item.get("name"),
            "sport_type": item.get("sport_type", item.get("type")),
            "distance_km": round(item.get("distance", 0) / 1000, 2),
            "moving_time_minutes": round(item.get("moving_time", 0) / 60),
            "start_date_local": item.get("start_date_local"),
            "average_heartrate": item.get("average_heartrate"),
        }
        for item in activities
        if item.get("sport_type", item.get("type")) in {"Run", "VirtualRun", "TrailRun"}
    ]


async def get_training_sheet() -> dict:
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("Set GOOGLE_SHEET_ID in .env before connecting a training Sheet.")
    credential = await _service_token("google")
    sheet_range = os.getenv("GOOGLE_SHEET_RANGE", "Training!A1:Z100")
    url = (
        "https://sheets.googleapis.com/v4/spreadsheets/"
        f"{quote(spreadsheet_id, safe='')}/values/{quote(sheet_range, safe='!:$')}"
    )
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {credential['access_token']}"},
            params={"valueRenderOption": "FORMATTED_VALUE"},
        )
        response.raise_for_status()
    payload = response.json()
    return {"range": payload.get("range", sheet_range), "rows": payload.get("values", [])}
