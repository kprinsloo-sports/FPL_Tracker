#!/usr/bin/env python3
"""Pull gameweek-by-gameweek history for the FPL managers listed in managers.json.

    python scripts/fetch_managers.py            refresh every tracked manager
    python scripts/fetch_managers.py --add 123  start tracking manager 123, then refresh

Uses the public endpoints entry/{id}/ (team and manager name) and
entry/{id}/history/ (points, ranks, team value, transfers per gameweek).
The FPL API can't be called from a browser (no CORS), so the dashboard can
only show managers fetched here.

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


def fetch_manager(mid: int) -> dict:
    entry = get_json(f"entry/{mid}/")
    hist = get_json(f"entry/{mid}/history/")
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
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", type=int, help="FPL manager (team) ID to start tracking")
    args = ap.parse_args()

    ids = load_ids()
    if args.add:
        fetch_manager(args.add)  # fail loudly on a bad ID before saving it
        if args.add not in ids:
            ids.append(args.add)
            save_ids(ids)
            print(f"Now tracking manager {args.add}")

    managers = []
    for mid in ids:
        try:
            managers.append(fetch_manager(mid))
            print(f"Fetched manager {mid}")
        except RuntimeError as exc:
            # Keep the last good copy rather than dropping the manager.
            print(f"  manager {mid} failed: {exc}", file=sys.stderr)
            old = json.loads(OUT.read_text()).get("managers", []) if OUT.exists() else []
            managers.extend(m for m in old if m["id"] == mid)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "managers": managers,
    }, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
