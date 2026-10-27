# FPL Weekly Tracker

Fantasy Premier League points for every player, gameweek by gameweek, with a dashboard that refreshes itself every week.

**Dashboard:** https://kprinsloo-sports.github.io/FPL_Tracker/

## What's in here

| Path | What it is |
|---|---|
| `scripts/fetch_fpl.py` | Pulls player, team and per-gameweek stats from the public FPL API (standard library only) |
| `data/<season>/gw/gwNN.json` | Every player's stats for one gameweek: points, minutes, goals, assists, clean sheets, bonus, BPS and more |
| `data/<season>/prices.json` | Each player's price per gameweek (in £0.1m), backfilled from their match history then recorded on every refresh |
| `data/<season>/points_by_gameweek.csv` | One row per player, one column per gameweek. Opens straight in Excel |
| `scripts/fetch_managers.py` | Pulls rank, points and team value per gameweek for the manager IDs in `managers.json` |
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
- Average points per position per gameweek
- Heatmap of each club's total points per gameweek
- Sortable, searchable player table with form and a weekly points sparkline

## Tracking a manager's rank

The **Manager rank by gameweek** chart shows overall and gameweek rank, points, team value and chips for any FPL manager you track.
Your manager ID is the number in the address of your Points page: `fantasy.premierleague.com/entry/<ID>/event/9`.

To start tracking one, go to **Actions → Refresh FPL data → Run workflow**, paste the ID into `manager_id` and run it. (Or add the ID to `managers.json` and commit.)
It shows on the dashboard a minute later and refreshes with everything else each week. Type the ID into the chart's box, or open `…/FPL_Tracker/#manager=<ID>`.
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
