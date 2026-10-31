# FPL Weekly Tracker

Fantasy Premier League points for every player, gameweek by gameweek, with a dashboard that refreshes itself every week.

**Dashboard:** https://kprinsloo-sports.github.io/FPL_Tracker/

## What's in here

| Path | What it is |
|---|---|
| `scripts/fetch_fpl.py` | Pulls player, team and per-gameweek stats from the public FPL API (standard library only) |
| `data/<season>/gw/gwNN.json` | Every player's stats for one gameweek: points, minutes, goals, assists, clean sheets, bonus, BPS and more |
| `data/<season>/prices.json` | Each player's price per gameweek (in £0.1m), backfilled from their match history then recorded on every refresh |
| `data/<season>/ownership.json` | Each player's % owned by managers per gameweek; earlier weeks are backfilled from match history against today's manager total, then recorded exactly on every refresh |
| `data/<season>/points_by_gameweek.csv` | One row per player, one column per gameweek. Opens straight in Excel |
| `scripts/fetch_managers.py` | Pulls rank, points, team value and squad picks per gameweek for the manager IDs in `managers.json` |
| `managers.json` | The FPL manager (team) IDs shown on the rank chart |
| `docs/` | The dashboard (static HTML + Chart.js), served by GitHub Pages |
| `docs/data/fpl.json` | The data file the dashboard reads |
| `.github/workflows/refresh.yml` | Weekly refresh: fetch, commit new data, redeploy the dashboard |

## The dashboard

- Headline tiles: latest gameweek, average manager score (with change vs last week), player of the week, season top scorer
- Average and highest manager score per gameweek
- Top 10 players in any gameweek, filtered by position and team
- Compare up to 8 players week by week, weekly or cumulative
- Player price by gameweek: starts with the 5 most-owned players, search to add anyone
- Percentage owned by managers per gameweek: same layout, starts with the 5 most-owned players, search to add anyone
- Average points per position per gameweek
- Heatmap of each club's total points per gameweek, red (low) to green (high)
- Sortable, searchable player table with form and a weekly points sparkline

## Top performers tab

Four tables (goalkeepers, defenders, midfielders, forwards) with the top 30 players over the **last 4 gameweeks** or the **whole season**.
Every stat FPL publishes per gameweek is summed for the period (points, minutes, starts, goals, assists, xG, xA, xGI, xGC, clean sheets, saves,
defensive contributions, tackles, recoveries, bonus, BPS, ICT, Team of the Week appearances, cards and more), plus per-90 and value rates,
FPL form, price change and net transfers. Click any column header to sort that table by it; click again for lowest first.
Rate columns and lowest-first sorts only include players with at least 45 minutes per gameweek in the period, so cameos don't top the list.
Players in your current squad (the manager selected on the My team tab) are highlighted with an **XI** or **Bench** tag (C/TC for your captain); squad players outside the top 30 are listed under each table with their rank.
The data comes from `docs/data/stats.json`, built by `scripts/fetch_fpl.py`.

**Predicted points** for the next 3 gameweeks (plus a "Next 3" total) sit next to price and ownership; hover a cell to see the fixture.
`scripts/predict.py` builds them on each refresh from the 2026/27 scoring rules: season xG, xA, bonus, cards, saves and defensive
contributions per 90 (shrunk towards the position average for small samples), minutes and availability from the last 4 gameweeks and
FPL's injury flag, clean-sheet and goals-conceded odds, and each opponent's attack and defence strength (from team xG for and against, with
a home boost). Blank gameweeks score 0 and double gameweeks add both fixtures.

## Standings tab

The Premier League table built from FPL's fixture results: played, won, drawn, lost, goals for and against, goal difference, points, the last 5 results and each team's next match. Places 1–4 (Champions League), 5 (Europa League), 6 (Conference League qualifying) and 18–20 (relegation) are marked; cup winners and extra European spots can move those lines at the end of the season. Open it directly at `…/FPL_Tracker/#standings`.

## My team tab

The **My team** tab shows one FPL manager at a time:

- overall and gameweek rank per gameweek (chips marked), plus points, team value and bank
- points per gameweek by position, after captaincy, auto-subs and chips
- every player in the squad with their points each week, coloured red (0 pts) to green (11+ pts) when they were in the starting XI, outlined on the bench, grey when they weren't in the team, with the captain marked; switch to "Everyone you've owned" to include sold players

### Tracking a manager
Your manager ID is the number in the address of your Points page: `fantasy.premierleague.com/entry/<ID>/event/9`.

To start tracking one, go to **Actions → Refresh FPL data → Run workflow**, paste the ID into `manager_id` and run it. (Or add the ID to `managers.json` and commit.)
It shows on the dashboard a minute later and refreshes with everything else each week. Type the ID into the box on the My team tab, or open `…/FPL_Tracker/#manager=<ID>`.
The FPL API blocks requests from browsers, which is why managers are fetched by the workflow rather than live on the page.

## Refresh schedule

The workflow runs every **Tuesday at 06:00 UTC**, once Monday night games are done and bonus points are confirmed.
It caches finished gameweeks and always re-pulls the latest two, so late bonus changes and corrections are picked up.
You can also run it any time from **Actions → Refresh FPL data → Run workflow**.

### Notifications

Every scheduled or manual refresh posts a comment on the **Weekly refresh log** issue (labelled `refresh-log`) with the latest gameweek's top scorers and a link to the dashboard, and @-mentions the repo owner, so GitHub sends an email and app notification. If a refresh fails, it posts a warning with a link to the run log instead. The dashboard header also shows when the data was last updated.

## One-time setup

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Actions → Refresh FPL data → Run workflow** to pull the season so far.

## Running locally

```bash
python scripts/fetch_fpl.py
python -m http.server --directory docs
# open http://localhost:8000
```

Offline test against fake data:

```bash
python tests/make_fixtures.py
python -m http.server 8765 --directory tests/fixtures &
FPL_API_BASE=http://localhost:8765 python scripts/fetch_fpl.py
```
