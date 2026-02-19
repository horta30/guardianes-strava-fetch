import os
import json
from datetime import datetime, timedelta, timezone
import requests

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


def must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def refresh_access_token() -> str:
    payload = {
        "client_id": must_env("STRAVA_CLIENT_ID"),
        "client_secret": must_env("STRAVA_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": must_env("STRAVA_REFRESH_TOKEN"),
    }
    r = requests.post(STRAVA_TOKEN_URL, data=payload, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def strava_get(path: str, access_token: str, params=None):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{STRAVA_API_BASE}{path}"
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    club_id = int(must_env("STRAVA_CLUB_ID"))
    lookback_days = int(os.getenv("LOOKBACK_DAYS", "7"))

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=lookback_days)

    access_token = refresh_access_token()

    club = strava_get(f"/clubs/{club_id}", access_token)

    activities = []
    page = 1
    per_page = 200

    while True:
        batch = strava_get(
            f"/clubs/{club_id}/activities",
            access_token,
            params={"page": page, "per_page": per_page},
        )
        if not batch:
            break

        activities.extend(batch)

        last = batch[-1]
        start_date = last.get("start_date")
        if start_date:
            last_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if last_dt < since:
                break

        page += 1
        if page > 10:
            break

    payload = {
        "fetched_at_utc": now.isoformat(),
        "club_id": club_id,
        "lookback_days": lookback_days,
        "club": club,
        "activities": activities,
    }

    os.makedirs("data", exist_ok=True)

    filename = now.strftime("%Y-%m-%d") + ".json"
    with open(f"data/{filename}", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved weekly snapshot ({len(activities)} activities)")


if __name__ == "__main__":
    main()
