#!/usr/bin/env python3
"""Print a short Markdown summary of the latest gameweek, for the refresh notification."""

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "docs" / "data" / "fpl.json"


def main() -> int:
    d = json.loads(DATA.read_text())
    teams = {t["id"]: t["short"] for t in d["teams"]}
    gi = len(d["gws"]) - 1
    gw, meta = d["gws"][gi], d["gw_meta"][gi]
    week = sorted(d["players"], key=lambda p: -p["pts"][gi])[:3]
    leader = d["players"][0]

    status = "finished" if meta["finished"] else "in progress"
    print(f"**Gameweek {gw}** ({status}) · average manager score **{meta['avg']}**, highest **{meta['high']}**")
    print()
    print("Top scorers this gameweek:")
    for i, p in enumerate(week, 1):
        print(f"{i}. {p['name']} ({teams[p['team']]}, {p['pos']}): {p['pts'][gi]} pts")
    print()
    print(f"Season leader: {leader['name']} ({teams[leader['team']]}) on {leader['total']} pts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
