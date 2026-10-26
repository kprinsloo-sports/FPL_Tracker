#!/usr/bin/env python3
"""Pull per-gameweek Fantasy Premier League points for every player.

Uses only the public FPL API and the Python standard library:
  bootstrap-static/   players, teams, positions and gameweek metadata
  event/{gw}/live/    every player's stats for one gameweek

Raw gameweek stats are cached per season under data/<season>/gw/ so old
gameweeks are only downloaded once. The latest few gameweeks are always
re-fetched because bonus points and corrections land after the final whistle.

Outputs:
  data/<season>/gw/gwNN.json           compact per-player stats for one gameweek
  data/<season>/points_by_gameweek.csv player x gameweek points table
  docs/data/fpl.json                   everything the dashboard needs
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE = os.environ.get("FPL_API_BASE", "https://fantasy.premierleague.com/api").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SITE_DATA = ROOT / "docs" / "data" / "fpl.json"

# Gameweeks this close to the latest finished one are always re-downloaded.
REFRESH_RECENT = 2

STAT_KEYS = [
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "bonus",
    "bps",
    "saves",
    "yellow_cards",
    "red_cards",
    "expected_goal_involvements",
]


def get_json(path: str, retries: int = 4) -> dict:
    url = f"{API_BASE}/{path.lstrip('/')}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (fpl-tracker; github actions)", "Accept": "application/json"},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == retries:
                raise RuntimeError(f"GET {url} failed: {exc}") from exc
            wait = 2 ** (attempt + 1)
            print(f"  {url} failed ({exc}), retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise AssertionError("unreachable")


def season_label(events: list[dict]) -> str:
    first = min(events, key=lambda e: e["id"])
    year = int(first["deadline_time"][:4])
    return f"{year}-{str(year + 1)[-2:]}"


def compact_live(live: dict) -> dict[str, dict]:
    out = {}
    for el in live.get("elements", []):
        stats = el.get("stats", {})
        row = {}
        for key in STAT_KEYS:
            val = stats.get(key, 0)
            if isinstance(val, str):
                try:
                    val = float(val)
                except ValueError:
                    val = 0
            row[key] = val
        out[str(el["id"])] = row
    return out


def load_gameweeks(season_dir: Path, events: list[dict]) -> dict[int, dict]:
    gw_dir = season_dir / "gw"
    gw_dir.mkdir(parents=True, exist_ok=True)

    played = [e for e in events if e.get("finished") or e.get("is_current")]
    if not played:
        return {}
    latest = max(e["id"] for e in played)

    gameweeks = {}
    for ev in sorted(played, key=lambda e: e["id"]):
        gw = ev["id"]
        path = gw_dir / f"gw{gw:02d}.json"
        stale = gw > latest - REFRESH_RECENT or not ev.get("data_checked", ev.get("finished"))
        if path.exists() and not stale:
            gameweeks[gw] = json.loads(path.read_text())
            continue
        print(f"Fetching gameweek {gw}")
        payload = {
            "gameweek": gw,
            "finished": bool(ev.get("finished")),
            "data_checked": bool(ev.get("data_checked")),
            "players": compact_live(get_json(f"event/{gw}/live/")),
        }
        path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        gameweeks[gw] = payload
    return gameweeks


def build(bootstrap: dict, gameweeks: dict[int, dict]) -> dict:
    events = bootstrap["events"]
    gws = sorted(gameweeks)
    teams = {t["id"]: t for t in bootstrap["teams"]}
    positions = {p["id"]: p["singular_name_short"] for p in bootstrap["element_types"]}

    players = []
    for el in bootstrap["elements"]:
        pid = str(el["id"])
        pts, mins = [], []
        for gw in gws:
            row = gameweeks[gw]["players"].get(pid)
            pts.append(int(row["total_points"]) if row else 0)
            mins.append(int(row["minutes"]) if row else 0)

        def season_sum(key: str) -> float:
            return sum(gameweeks[gw]["players"].get(pid, {}).get(key, 0) for gw in gws)

        players.append(
            {
                "id": el["id"],
                "name": el["web_name"],
                "full": f"{el['first_name']} {el['second_name']}".strip(),
                "team": el["team"],
                "pos": positions.get(el["element_type"], "?"),
                "price": el["now_cost"] / 10,
                "sel": float(el.get("selected_by_percent") or 0),
                "status": el.get("status", "a"),
                "total": sum(pts),
                "pts": pts,
                "min": mins,
                "g": int(season_sum("goals_scored")),
                "a": int(season_sum("assists")),
                "cs": int(season_sum("clean_sheets")),
                "bonus": int(season_sum("bonus")),
            }
        )
    players.sort(key=lambda p: -p["total"])

    by_id = {e["id"]: e for e in events}
    return {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season_label(events),
        "gws": gws,
        "gw_meta": [
            {
                "gw": gw,
                "finished": bool(by_id[gw].get("finished")),
                "avg": by_id[gw].get("average_entry_score") or 0,
                "high": by_id[gw].get("highest_score") or 0,
            }
            for gw in gws
        ],
        "teams": [{"id": t["id"], "name": t["name"], "short": t["short_name"]} for t in teams.values()],
        "players": players,
    }


def write_csv(path: Path, data: dict) -> None:
    teams = {t["id"]: t["short"] for t in data["teams"]}
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "name", "team", "position", "price", "total"] + [f"GW{gw}" for gw in data["gws"]])
        for p in data["players"]:
            writer.writerow([p["id"], p["full"], teams[p["team"]], p["pos"], p["price"], p["total"], *p["pts"]])


def main() -> int:
    print(f"Reading {API_BASE}/bootstrap-static/")
    bootstrap = get_json("bootstrap-static/")
    season = season_label(bootstrap["events"])
    season_dir = DATA_DIR / season
    gameweeks = load_gameweeks(season_dir, bootstrap["events"])
    if not gameweeks:
        print("No gameweeks played yet this season; nothing to do.")
        return 0

    data = build(bootstrap, gameweeks)
    write_csv(season_dir / "points_by_gameweek.csv", data)
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"Season {season}: {len(data['players'])} players, gameweeks {data['gws'][0]}-{data['gws'][-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
