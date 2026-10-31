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
                    "selected_by_percent": f"{skill * 40:.1f}", "_skill": skill,
                    "status": "d" if pid % 50 == 0 else "a", "chance_of_playing_next_round": 50 if pid % 50 == 0 else None,
                })
                pid += 1

    events = []
    for gw in range(1, 39):
        events.append({
            "id": gw, "name": f"Gameweek {gw}",
            "deadline_time": f"{2026 if gw <= PLAYED else 2099}-{gw // 28 + 8:02d}-{(gw % 28) + 1:02d}T17:30:00Z",
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
                "expected_goals": f"{el['_skill'] * 0.4 * (minutes > 0):.2f}", "expected_assists": f"{el['_skill'] * 0.2 * (minutes > 0):.2f}",
                "expected_goals_conceded": f"{rnd.random() * 2 * (minutes > 0):.2f}", "goals_conceded": rnd.randint(0, 3) if minutes else 0,
                "influence": f"{pts * 4.2:.1f}", "creativity": f"{rnd.random() * 40 * (minutes > 0):.1f}", "threat": f"{goals * 30 + rnd.random() * 20:.1f}",
                "ict_index": f"{pts * 0.9:.1f}", "starts": int(minutes >= 60), "tackles": rnd.randint(0, 4) if minutes else 0,
                "recoveries": rnd.randint(0, 8) if minutes else 0, "clearances_blocks_interceptions": rnd.randint(0, 6) if minutes else 0,
                "defensive_contribution": rnd.randint(0, 12) if minutes else 0, "own_goals": 0, "penalties_saved": 0, "penalties_missed": 0,
                "in_dreamteam": pts >= 12,
            }})
        d = OUT / "event" / str(gw) / "live"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(json.dumps({"elements": live}))

    for el in elements:
        cost, history = el["now_cost"] - 3, []
        for gw in range(1, PLAYED + 1):
            cost += rnd.choice([-1, 0, 0, 0, 1, 1])
            if rnd.random() < 0.85:
                history.append({"round": gw, "value": cost, "selected": int(skill * 4_000_000 * (0.6 + 0.4 * gw / PLAYED)),
                                "kickoff_time": f"2026-08-{gw + 10:02d}T15:00:00Z"})
        el["now_cost"] = cost
        d = OUT / "element-summary" / str(el["id"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(json.dumps({"history": history}))
        del el["_skill"]
    bootstrap = {
        "events": events,
        "teams": [{"id": i, "name": n, "short_name": s} for i, (n, s) in enumerate(TEAMS, 1)],
        "element_types": [{"id": i, "singular_name_short": s} for i, s, _ in POSITIONS],
        "elements": elements,
        "total_players": 11_234_567,
    }
    (OUT / "bootstrap-static" / "index.html").write_text(json.dumps(bootstrap))

    # Round-robin fixtures; GW11 is a blank for teams 1-2 and a double for 3-4.
    fixtures, ids = [], list(range(1, len(TEAMS) + 1))
    for gw in range(1, 39):
        pairs = [(ids[i], ids[-1 - i]) for i in range(len(ids) // 2)]
        if gw == PLAYED + 2:
            pairs = [pr for pr in pairs if 1 not in pr and 2 not in pr] + [(3, 4)]
        for h, a in pairs:
            fx = {"id": len(fixtures) + 1, "event": gw, "team_h": h if gw % 2 else a, "team_a": a if gw % 2 else h, "finished": gw <= PLAYED,
                  "kickoff_time": f"2026-{8 + gw // 5:02d}-{(gw % 5) * 5 + 1:02d}T15:00:00Z", "team_h_score": None, "team_a_score": None}
            if fx["finished"]:
                fx["team_h_score"], fx["team_a_score"] = rnd.choice([0, 1, 1, 2, 2, 3]), rnd.choice([0, 0, 1, 1, 2, 3])
            fixtures.append(fx)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    (OUT / "fixtures").mkdir(parents=True, exist_ok=True)
    (OUT / "fixtures" / "index.html").write_text(json.dumps(fixtures))

    for mid, team, first, last in [(1234567, "Kobus XI", "Test", "Manager"), (7654321, "Rivals FC", "Other", "Manager")]:
        rank, total, history = rnd.randint(500_000, 3_000_000), 0, []
        for gw in range(1, PLAYED + 1):
            pts = rnd.randint(30, 95)
            total += pts
            rank = max(1, int(rank * rnd.uniform(0.45, 1.6)))
            history.append({
                "event": gw, "points": pts, "total_points": total, "rank": rnd.randint(1_000, 9_000_000),
                "overall_rank": rank, "value": 1000 + gw * 2, "bank": rnd.randint(0, 20),
                "event_transfers": rnd.randint(0, 2), "event_transfers_cost": rnd.choice([0, 0, 4]),
                "points_on_bench": rnd.randint(0, 15),
            })
        d = OUT / "entry" / str(mid)
        (d / "history").mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(json.dumps({"name": team, "player_first_name": first, "player_last_name": last}))
        squad = rnd.sample(range(1, len(elements) + 1), 15)
        for gw in range(1, PLAYED + 1):
            if gw > 1:
                squad[rnd.randrange(15)] = rnd.choice([i for i in range(1, len(elements) + 1) if i not in squad])
            picks = [{"element": e, "position": i + 1, "multiplier": 0 if i >= 11 else 2 if i == 5 else 1,
                      "is_captain": i == 5, "is_vice_captain": i == 6} for i, e in enumerate(squad)]
            pd = d / "event" / str(gw) / "picks"
            pd.mkdir(parents=True, exist_ok=True)
            (pd / "index.html").write_text(json.dumps({
                "active_chip": "bboost" if gw == 7 else None, "picks": picks,
                "automatic_subs": [{"element_in": squad[11], "element_out": squad[2], "event": gw}] if gw == 3 else []}))
        (d / "history" / "index.html").write_text(json.dumps({
            "current": history, "chips": [{"event": 4, "name": "wildcard"}, {"event": 7, "name": "bboost"}]}))


if __name__ == "__main__":
    main()
