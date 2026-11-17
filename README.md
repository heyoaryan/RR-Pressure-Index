# Pressure Index — SupeRR Selector S2

```
code/
├── dashboard/              ← the dashboard (frontend/index.html = submission)
│   ├── backend/main.py     FastAPI server + Pressure Index engine (single file)
│   ├── frontend/index.html dashboard UI
│   └── start.sh            starts both servers
├── dashboard_data.json     data the dashboard shows (keep next to dashboard/)
└── analysis/               original analysis pipeline that produced the report numbers
```

## Open the dashboard

Just open `dashboard/frontend/index.html` in a browser — fully static, no server needed.
It's a 7-page deck (Overview · Pressure · Batters · Bowlers · Confidence · Method · Validation):
use the tabs, the Next button, or ← → keys; ↑ ↓ switches player on the Batters/Bowlers pages.
Each page has its own link, e.g. `index.html#bowlers`.

After re-running the analysis, rebuild the data file:

```bash
python3 dashboard/build_data.py
```

Player photos load live from URLs (needs internet), set in the `PHOTOS` map in `index.html`:
each player's ICC headshot in their national-team kit (`icc:` = ICC player id, from icc-cricket.com).
Vaibhav Sooryavanshi, Krunal Pandya and Sunil Narine have no ICC headshot, so they fall back to
their IPL headshot (`ipl:`). Any player can instead use `url:'https://…'`. If nothing loads → initials.

The old dashboard (with CSV upload / "Explore Data") is kept as `dashboard/frontend/index_legacy.html`;
it needs the backend: `bash dashboard/start.sh`, then http://localhost:3000/index_legacy.html
(`pip install -r dashboard/backend/requirements.txt` first).

## Re-run the analysis

Run from inside `analysis/`, in this order:

```bash
cd analysis
python3 prep.py      # load CSVs, filter, rebuild match state
python3 wp.py        # win-probability model + Leverage Index
python3 ledger.py    # flag pressure balls
python3 final1.py    # expected values, wicket run value
python3 final2.py    # opposition adjustment, shrinkage, ratings
python3 stab.py      # stability + sensitivity
python3 bag.py       # bootstrap → final top-10 tables
python3 evid.py      # evidence tables + charts
python3 mkjson.py    # export rows.json
node report.js       # build the .docx report (needs `npm install` once)
```

The scripts write intermediate `.pkl` files (~500 MB) into `analysis/`. The whole run takes about 2–3 minutes.

`prep.py` reads the CSVs from:
`~/Downloads/SupeRR Selector Season 2 | Problem Statement | Data Pack/SupeRR Selector Season 2 | Data Pack/`
If you move the Data Pack, edit the path at the top of `prep.py`.

## Deployment

| Part | Where | Config |
|---|---|---|
| Frontend (`dashboard/frontend/`) | Vercel — Root Directory `dashboard/frontend`, Framework "Other", no build | `dashboard/frontend/vercel.json` |
| Backend (`dashboard/backend/`) | Render — Blueprint from repo | `render.yaml` |

`index_legacy.html` calls `http://localhost:8000` when opened locally and
`https://pressure-index-api.onrender.com` when deployed. If Render gives the service a different
URL, update the `API` constant in `index_legacy.html`, or open `/legacy?api=https://<your-url>`.
The Render free tier sleeps after 15 min idle, so the first request can take ~30–60 s.
