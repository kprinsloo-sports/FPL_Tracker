"""Predicted FPL points for the next few gameweeks ("Option 2" model).

For every player and upcoming fixture, expected points are built up from the
2026/27 scoring rules:

  appearance     1 pt for playing, 1 more for 60+ minutes
  goals          season xG per 90 x expected minutes x goal value (GK 10, DEF 6, MID 5, FWD 4)
  assists        season xA per 90 x expected minutes x 3
  clean sheet    P(60+ min) x P(opponent scores 0) x (GK/DEF 4, MID 1)
  goals conceded GK/DEF lose 1 per 2 conceded
  saves          GK 1 per 3 saves
  def. contrib.  2 pts for 10+ actions (DEF) or 12+ (MID/FWD)
  bonus, cards   season rate per 90

The fixture scales attack by the opponent's defence and clean-sheet odds by
the opponent's attack. Team strengths come from the cached gameweeks: xG for
(sum of the team's players' xG) and xG against (the most xGC any one of their
players recorded, i.e. a full match). Per-90 rates are shrunk towards the
position average over PRIOR_MINS so small samples don't run wild.
Count stats (def. contrib., saves, goals conceded) are treated as Poisson.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

HORIZON = 3
PRIOR_MINS = 90
PRIOR_MATCHES = 3  # league-average matches blended into each team's strength
HOME = 1.1  # home sides create ~10% more xG, and concede ~10% less

GOAL = {"GKP": 10, "DEF": 6, "MID": 5, "FWD": 4}
CLEAN = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
DC_NEEDED = {"DEF": 10, "MID": 12, "FWD": 12}
RATES = ["expected_goals", "expected_assists", "bonus", "defensive_contribution", "saves", "yellow_cards", "red_cards"]


def poisson_at_least(mean: float, k: int) -> float:
    term = total = math.exp(-mean)
    for i in range(1, k):
        term *= mean / i
        total += term
    return max(0.0, 1 - total)


def poisson_floor_div(mean: float, n: int, cap: int = 15) -> float:
    """E[floor(X / n)] for X ~ Poisson(mean)."""
    term, total = math.exp(-mean), 0.0
    for i in range(1, cap + 1):
        term *= mean / i
        total += term * (i // n)
    return total


def team_strengths(gameweeks: dict[int, dict], team_of: dict[str, int], matches: dict[tuple[int, int], int]):
    xg_for, xg_against, played = defaultdict(float), defaultdict(float), defaultdict(int)
    for gw, payload in gameweeks.items():
        gw_for, gw_against, on = defaultdict(float), defaultdict(float), set()
        for pid, row in payload["players"].items():
            team = team_of.get(pid)
            if not team or not row.get("minutes"):
                continue
            on.add(team)
            gw_for[team] += row.get("expected_goals", 0)
            gw_against[team] = max(gw_against[team], row.get("expected_goals_conceded", 0))
        for team in on:
            xg_for[team] += gw_for[team]
            xg_against[team] += gw_against[team]
            played[team] += matches.get((gw, team), 1)
    games = sum(played.values()) or 1
    avg = (sum(xg_for.values()) / games) or 1.3
    teams = set(team_of.values())
    att = {t: (xg_for[t] + PRIOR_MATCHES * avg) / ((played[t] + PRIOR_MATCHES) * avg) for t in teams}
    dfn = {t: (xg_against[t] + PRIOR_MATCHES * avg) / ((played[t] + PRIOR_MATCHES) * avg) for t in teams}
    return avg, att, dfn


def build_predictions(bootstrap: dict, gameweeks: dict[int, dict], fixtures: list[dict]) -> dict | None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    upcoming = sorted(e["id"] for e in bootstrap["events"] if not e.get("finished") and (e.get("deadline_time") or "") > now)[:HORIZON]
    if not upcoming:
        return None
    positions = {p["id"]: p["singular_name_short"] for p in bootstrap["element_types"]}
    team_of = {str(el["id"]): el["team"] for el in bootstrap["elements"]}
    short = {t["id"]: t["short_name"] for t in bootstrap["teams"]}

    matches = defaultdict(int)
    for fx in fixtures:
        if fx.get("event") and fx.get("finished"):
            matches[(fx["event"], fx["team_h"])] += 1
            matches[(fx["event"], fx["team_a"])] += 1
    avg, att, dfn = team_strengths(gameweeks, team_of, matches)

    # Each team's fixtures per upcoming gameweek, as (opponent, at home).
    schedule = defaultdict(list)
    for fx in fixtures:
        if fx.get("event") in upcoming:
            schedule[(fx["event"], fx["team_h"])].append((fx["team_a"], True))
            schedule[(fx["event"], fx["team_a"])].append((fx["team_h"], False))

    gws = sorted(gameweeks)
    recent = gws[-4:]

    def totals(pid: str, span: list[int]) -> dict[str, float]:
        out = defaultdict(float)
        for gw in span:
            for k, v in gameweeks[gw]["players"].get(pid, {}).items():
                out[k] += v
        return out

    season = {str(el["id"]): totals(str(el["id"]), gws) for el in bootstrap["elements"]}

    # Position-average per-90 rates, the prior each player is shrunk towards.
    prior = {}
    for pos in GOAL:
        rows = [season[str(el["id"])] for el in bootstrap["elements"] if positions.get(el["element_type"]) == pos]
        mins = sum(r["minutes"] for r in rows) or 1
        prior[pos] = {k: sum(r[k] for r in rows) / mins * 90 for k in RATES}

    players = {}
    for el in bootstrap["elements"]:
        pid, pos, team = str(el["id"]), positions.get(el["element_type"]), el["team"]
        if pos not in GOAL:
            continue
        s = season[pid]
        rate = {k: (s[k] + prior[pos][k] * PRIOR_MINS / 90) / (s["minutes"] + PRIOR_MINS) * 90 for k in RATES}

        # Minutes and availability from the last 4 gameweeks, scaled by FPL's injury flag.
        last = [gameweeks[gw]["players"].get(pid, {}).get("minutes", 0) for gw in recent]
        chance = el.get("chance_of_playing_next_round")
        avail = (chance / 100 if chance is not None else 1.0) if el.get("status", "a") in ("a", "d") else 0.0
        p_play = avail * sum(m > 0 for m in last) / len(last)
        p_60 = avail * sum(m >= 60 for m in last) / len(last)
        played = [m for m in last if m > 0]
        mins = (sum(played) / len(played)) if played else 0.0
        share = mins / 90  # fraction of a match when they play

        row = []
        for gw in upcoming:
            pts = 0.0
            for opp, home in schedule.get((gw, team), []):
                boost = HOME if home else 1 / HOME
                attack = boost * dfn.get(opp, 1.0)  # how leaky the opponent is
                conceded = avg * att.get(opp, 1.0) / boost  # goals the player's team should concede
                xp = 1 * p_play + 1 * p_60
                xp += p_play * share * attack * (rate["expected_goals"] * GOAL[pos] + rate["expected_assists"] * 3)
                xp += p_60 * math.exp(-conceded) * CLEAN[pos]
                xp += p_play * share * (rate["bonus"] - rate["yellow_cards"] - 3 * rate["red_cards"])
                if pos in ("GKP", "DEF"):
                    xp -= p_play * poisson_floor_div(conceded * share, 2)
                if pos == "GKP":
                    xp += p_play * poisson_floor_div(rate["saves"] * share * att.get(opp, 1.0) / boost, 3)
                else:
                    xp += p_play * 2 * poisson_at_least(rate["defensive_contribution"] * share, DC_NEEDED[pos])
                pts += xp
            row.append(round(pts, 1))
        players[pid] = row

    opponents = {
        str(t): [[short.get(opp, "?") + (" (H)" if home else " (A)") for opp, home in schedule.get((gw, t), [])] for gw in upcoming]
        for t in short
    }
    return {"gws": upcoming, "players": players, "opp": opponents}
