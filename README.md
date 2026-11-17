# ClutchRank — SupeRR Selector S2

Ranks the 10 best T20 batters and 10 best bowlers **under pressure**, using IPL + T20I ball-by-ball data (2022 onwards).

- **Methodology report:** [`ClutchRank_Methodology.pdf`](ClutchRank_Methodology.pdf)
- **Interactive site:** `dashboard/frontend/index.html` (static; open it directly or deploy the folder)

## How it works (one paragraph)

A win-probability (WP) model gives every ball a **Leverage Index** (LI): the expected swing in WP from that ball, relative to an average ball.
A **pressure ball** is one with LI ≥ 1.5, WP between 15% and 85%, and past the free-hit phase (after over 6, 3+ wickets down, or any chase ball).
Each ball is valued as runs added/saved vs an average player in the same situation, corrected for opposition (ridge regression on non-pressure balls) and shrunk for sample size (empirical Bayes).

```
rating = 0.70·z(pressure value) + 0.15·z(consistency) + 0.15·z(clutch lift)
clutch lift = shrunk pressure value − shrunk normal (non-pressure) value
final = ½ · full-data rating + ½ · mean rating over 200 bootstrap resamples of matches
```

## Reproduce

```
data → wp model → leverage index → pressure flag → per-ball value → ratings → bootstrap → website + PDF
```

1. Get the Data Pack (`ball_by_ball.csv`, `matches.csv`, `competitions.csv`, …). By default `prep.py` looks in
   `~/Downloads/SupeRR Selector Season 2 | Problem Statement | Data Pack/SupeRR Selector Season 2 | Data Pack/`;
   point it elsewhere with `DATA_DIR=/path/to/folder`.
2. Install: `pip install -r analysis/requirements.txt` (Python 3.11).
3. Run, from inside `analysis/`, in this order (about 3 minutes in total; writes ~500 MB of `.pkl` intermediates):

| # | Script | What it does | Output |
|---|---|---|---|
| 1 | `prep.py` | Load CSVs; keep IPL + T20I, innings 1–2, decisive results, no DLS; rebuild score / wickets / balls state per ball | `balls.pkl` |
| 2 | `wp.py` | Win-probability model per innings (gradient boosting, 5-fold grouped by match, out-of-fold) + Leverage Index | `balls_wp.pkl` |
| 3 | `ledger.py` | Flag pressure balls (3 conditions) | `balls_final.pkl` |
| 4 | `final1.py` | Context-expected runs/wickets, wicket run value λ by phase | `balls_v.pkl` |
| 5 | `final2.py` | Opposition adjustment (ridge), shrinkage, `ratings()` function | `balls_v2.pkl`, `R.pkl` |
| 6 | `bag.py` | 200 bootstrap resamples → **final top-10 tables** | `final_tables.pkl` |
| 7 | `stab.py` | Sensitivity table (thresholds, weights, eligibility, k, IPL-only, T20I-only, no associates) | `sens.pkl` |
| 8 | `rel.py` | Split-half reliability (20 random splits) | `rel.pkl` |
| 9 | `export.py` | Everything the site and PDF show | `../dashboard_data.json` |
| 10 | `charts.py` | Report charts | `fig_*.png` |
| 11 | `report_pdf.py` | Methodology PDF (`SITE_URL=https://… python3 report_pdf.py` to print the link) | `../ClutchRank_Methodology.pdf` |

Then, from the repo root:

```bash
python3 dashboard/build_data.py          # website data.js + the static (no-JS) top-10 table
cd analysis && python3 check_order.py    # site == static HTML == PDF order; prints the Unstop list
```

`bag.py`, `stab.py` and `rel.py` use fixed random seeds, so a re-run gives the same lists.
(`evid.py`, `mkjson.py` and `report.js` are the older .docx report path, kept for reference only.)

## Website

`dashboard/frontend/` is fully static: `index.html` + `data.js` + `img/`. Pages: Overview · Pressure · Batters · Bowlers ·
Pressure vs Normal · Confidence · Method · Validation (← → keys, or `index.html#bowlers` etc.).
Player photos are stored in `img/` (`<name-slug>.icc.png` = ICC national-team headshot, `.ipl.png` = IPL headshot where ICC has none);
a missing photo falls back to initials. With JavaScript off, a static top-10 table is shown.

The old dashboard (CSV upload / "Explore Data") is kept as `dashboard/frontend/index_legacy.html` and needs the backend:
`pip install -r dashboard/backend/requirements.txt && bash dashboard/start.sh`, then http://localhost:3000/index_legacy.html.

## Deployment

| Part | Where | Config |
|---|---|---|
| Frontend (`dashboard/frontend/`) | Vercel — Root Directory `dashboard/frontend`, Framework "Other", no build | `dashboard/frontend/vercel.json` |
| Backend (`dashboard/backend/`, legacy page only) | Render — Blueprint from repo | `render.yaml` |
