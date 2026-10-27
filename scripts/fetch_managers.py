#!/usr/bin/env python3
"""Pull gameweek-by-gameweek history for the FPL managers listed in managers.json.

    python scripts/fetch_managers.py            refresh every tracked manager
    python scripts/fetch_managers.py --add 123  start tracking manager 123, then refresh

Uses the public endpoints entry/{id}/ (team and manager name),
entry/{id}/history/ (points, ranks, team value, transfers per gameweek) and
entry/{id}/event/{gw}/picks/ (the 15 players picked each gameweek).
The FPL API can't be called from a browser (no CORS), so the dashboard can
only show managers fetched here.

Run after fetch_fpl.py: player minutes from data/<season>/gw/ are used to
apply captaincy changes.

Outputs docs/data/managers.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_fpl import ROOT, get_json  # noqa: E402

CONFIG = ROOT / "managers.json"
OUT = ROOT / "docs" / "data" / "managers.json"


def load_ids() -> list[int]:
    if not CONFIG.exists():
        return []
    return [int(i) for i in json.loads(CONFIG.read_text()).get("ids", [])]


def save_ids(ids: list[int]) -> None:
    CONFIG.write_text(json.dumps({"ids": ids}, indent=2) + "\n")


def gw_minutes(gw: int) -> dict[int, int]:
    """Minutes per player for a gameweek, from the cache fetch_fpl.py writes."""
    site = ROOT / "docs" / "data" / "fpl.json"
    if not site.exists():
        return {}
    path = ROOT / "data" / json.loads(site.read_text())["season"] / "gw" / f"gw{gw:02d}.json"
    if not path.exists():
        return {}
    return {int(k): v.get("minutes", 0) for k, v in json.loads(path.read_text())["players"].items()}


def effective_picks(picks: dict, minutes: dict[int, int]) -> list[list[int]]:
    """[[player_id, squad_position, multiplier], ...] with the points that actually counted.

    The picks endpoint reports the team as picked at the deadline. Automatic
    substitutions are listed separately, and the vice-captain's armband takes
    over when the captain doesn't play, so both are applied here.
    """
    rows = {p["element"]: dict(p) for p in picks.get("picks", [])}
    for sub in picks.get("automatic_subs", []):
        out, inn = rows.get(sub["element_out"]), rows.get(sub["element_in"])
        if out and inn:
            inn["multiplier"], out["multiplier"] = max(1, out["multiplier"]), 0
    captain = next((r for r in rows.values() if r.get("is_captain")), None)
    vice = next((r for r in rows.values() if r.get("is_vice_captain")), None)
    if captain and vice and minutes and not minutes.get(captain["element"]) and minutes.get(vice["element"]):
        boost = captain["multiplier"] if captain["multiplier"] > 1 else 2
        vice["multiplier"], captain["multiplier"] = boost, 0
    return [[r["element"], r["position"], r["multiplier"]] for r in sorted(rows.values(), key=lambda r: r["position"])]


def fetch_picks(mid: int, gws: list[int], cached: dict) -> dict:
    """Picks per gameweek, reusing cached gameweeks except the latest two."""
    out = {}
    for gw in gws:
        key = str(gw)
        if key in cached and gw <= gws[-1] - 2:
            out[key] = cached[key]
            continue
        raw = get_json(f"entry/{mid}/event/{gw}/picks/")
        out[key] = {"chip": raw.get("active_chip"), "picks": effective_picks(raw, gw_minutes(gw))}
    return out


def fetch_manager(mid: int, cached_picks: dict | None = None) -> dict:
    entry = get_json(f"entry/{mid}/")
    hist = get_json(f"entry/{mid}/history/")
    gws = sorted(h["event"] for h in hist.get("current", []))
    return {
        "id": mid,
        "team": entry.get("name", f"Team {mid}"),
        "manager": f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip(),
        "history": [
            {
                "gw": h["event"],
                "points": h["points"],
                "total": h["total_points"],
                "rank": h.get("rank"),
                "overall_rank": h.get("overall_rank"),
                "value": h.get("value", 0) / 10,
                "bank": h.get("bank", 0) / 10,
                "transfers": h.get("event_transfers", 0),
                "hit": h.get("event_transfers_cost", 0),
                "bench": h.get("points_on_bench", 0),
            }
            for h in sorted(hist.get("current", []), key=lambda h: h["event"])
        ],
        "chips": [{"gw": c["event"], "name": c["name"]} for c in hist.get("chips", [])],
        "picks": fetch_picks(mid, gws, cached_picks or {}) if gws else {},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", type=int, help="FPL manager (team) ID to start tracking")
    args = ap.parse_args()

    ids = load_ids()
    if args.add:
        get_json(f"entry/{args.add}/")  # fail loudly on a bad ID before saving it
        if args.add not in ids:
            ids.append(args.add)
            save_ids(ids)
            print(f"Now tracking manager {args.add}")

    old = {m["id"]: m for m in json.loads(OUT.read_text()).get("managers", [])} if OUT.exists() else {}
    managers = []
    for mid in ids:
        try:
            managers.append(fetch_manager(mid, old.get(mid, {}).get("picks")))
            print(f"Fetched manager {mid}")
        except RuntimeError as exc:
            # Keep the last good copy rather than dropping the manager.
            print(f"  manager {mid} failed: {exc}", file=sys.stderr)
            if mid in old:
                managers.append(old[mid])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "managers": managers,
    }, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
