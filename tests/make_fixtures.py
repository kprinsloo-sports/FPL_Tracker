#!/usr/bin/env python3
"""Write a fake FPL API to tests/fixtures/ for offline testing.

    python tests/make_fixtures.py
    python -m http.server 8765 --directory tests/fixtures &
    FPL_API_BASE=http://localhost:8765 python scripts/fetch_fpl.py
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "fixtures"
TEAMS = [
    ("Arsenal", "ARS"), ("Aston Villa", "AVL"), ("Bournemouth", "BOU"), ("Brentford", "BRE"),
    ("Brighton", "BHA"), ("Burnley", "BUR"), ("Chelsea", "CHE"), ("Crystal Palace", "CRY"),
    ("Everton", "EVE"), ("Fulham", "FUL"), ("Leeds", "LEE"), ("Liverpool", "LIV"),
    ("Man City", "MCI"), ("Man Utd", "MUN"), ("Newcastle", "NEW"), ("Nott'm Forest", "NFO"),
    ("Sunderland", "SUN"), ("Spurs", "TOT"), ("West Ham", "WHU"), ("Wolves", "WOL"),
]
POSITIONS = [(1, "GKP", 2), (2, "DEF", 7), (3, "MID", 8), (4, "FWD", 4)]
PLAYED = 9


def main() -> None:
    rnd = random.Random(7)
    elements, pid = [], 1
    for tid, _ in enumerate(TEAMS, 1):
        for etype, _, count in POSITIONS:
            for _ in range(count):
                skill = rnd.random()
                elements.append({
                    "id": pid, "web_name": f"Player{pid}", "first_name": "Test", "second_name": f"Player{pid}",
                    "team": tid, "element_type": etype, "now_cost": 40 + int(skill * 90),
                    "selected_by_percent": f"{skill * 40:.1f}", "status": "a", "_skill": skill,
                })
                pid += 1

    events = []
    for gw in range(1, 39):
        events.append({
            "id": gw, "name": f"Gameweek {gw}", "deadline_time": f"2026-08-{(gw % 28) + 1:02d}T17:30:00Z",
            "finished": gw <= PLAYED, "data_checked": gw < PLAYED, "is_current": gw == PLAYED,
            "average_entry_score": rnd.randint(38, 68) if gw <= PLAYED else 0,
            "highest_score": rnd.randint(110, 160) if gw <= PLAYED else None,
        })
    events[0]["deadline_time"] = "2026-08-15T17:30:00Z"

    (OUT / "bootstrap-static").mkdir(parents=True, exist_ok=True)
    for gw in range(1, PLAYED + 1):
        live = []
        for el in elements:
            plays = rnd.random() < 0.4 + el["_skill"] * 0.5
            minutes = rnd.choice([90, 90, 90, 75, 60, 23]) if plays else 0
            goals = sum(rnd.random() < el["_skill"] * 0.25 * (el["element_type"] / 2) for _ in range(2)) if plays else 0
            assists = int(plays and rnd.random() < el["_skill"] * 0.3)
            cs = int(minutes >= 60 and el["element_type"] <= 2 and rnd.random() < 0.35)
            bonus = rnd.choice([0, 0, 0, 1, 2, 3]) if goals else 0
            pts = (2 if minutes >= 60 else 1 if minutes else 0) + goals * (6 - el["element_type"] // 2) + assists * 3 + cs * 4 + bonus
            live.append({"id": el["id"], "stats": {
                "total_points": pts, "minutes": minutes, "goals_scored": goals, "assists": assists,
                "clean_sheets": cs, "bonus": bonus, "bps": pts * 3, "saves": 0, "yellow_cards": 0,
                "red_cards": 0, "expected_goal_involvements": f"{el['_skill'] * 0.6:.2f}",
            }})
        d = OUT / "event" / str(gw) / "live"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(json.dumps({"elements": live}))

    for el in elements:
        del el["_skill"]
    bootstrap = {
        "events": events,
        "teams": [{"id": i, "name": n, "short_name": s} for i, (n, s) in enumerate(TEAMS, 1)],
        "element_types": [{"id": i, "singular_name_short": s} for i, s, _ in POSITIONS],
        "elements": elements,
    }
    (OUT / "bootstrap-static" / "index.html").write_text(json.dumps(bootstrap))


if __name__ == "__main__":
    main()
