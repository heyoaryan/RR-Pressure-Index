"""
ClutchRank Dashboard — Backend (single file)

Part 1: ClutchRank engine — same pipeline as prep.py → wp.py → final1.py → final2.py → bag.py.
        Takes the raw CSVs as DataFrames and returns a dashboard_data.json-compatible dict.
Part 2: FastAPI server — serves dashboard_data.json, accepts CSV uploads, runs the engine, returns analytics.

Run:  uvicorn main:app --port 8000
"""

import io
import json
import os
import threading
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import scipy.sparse as sp
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")


# ═════════════════════════════════════════════════════════════════════════════
# PART 1 — CLUTCHRANK ENGINE
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# STEP 1 — PREP  (mirrors prep.py)
# ─────────────────────────────────────────────

def prep(ball_df, matches_df=None, competitions_df=None, player_map_df=None):
    b = ball_df.copy()

    # merge matches
    if matches_df is not None:
        m_cols = [c for c in [
            "match_id", "comp_id", "match_date", "stage",
            "win_team_id", "result", "revised_target",
            "first_inn_revised_overs", "second_inn_revised_overs", "venue_id"
        ] if c in matches_df.columns]
        b = b.merge(matches_df[m_cols], on="match_id", how="left")

    if competitions_df is not None:
        c_cols = [c for c in ["comp_id", "comp_name", "match_format"] if c in competitions_df.columns]
        if "comp_id" in b.columns:
            b = b.merge(competitions_df[c_cols], on="comp_id", how="left")

    # scope: IPL + T20I only
    if "comp_name" in b.columns and "match_format" in b.columns:
        b["is_ipl"] = b.comp_name.str.startswith("IPL", na=False)
        scope = b.is_ipl | (b.match_format == "T20I")
        b = b[scope]
    else:
        b["is_ipl"] = False

    # innings 1-2 only
    if "innings" in b.columns:
        b = b[b.innings <= 2]

    # drop DLS-affected matches
    if "revised_target" in b.columns:
        dls = b.revised_target.notna()
        if "first_inn_revised_overs" in b.columns:
            dls = dls | b.first_inn_revised_overs.notna()
        if "second_inn_revised_overs" in b.columns:
            dls = dls | b.second_inn_revised_overs.notna()
        b = b[~dls]

    b = b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

    # run accounting
    extras = b.get("extras_type", pd.Series(dtype=str))
    b["wide"] = extras == "wide"
    b["nb"]   = extras == "Overstep"
    b["bl"]   = extras.isin(["byes", "legbyes"])
    b["legal"] = ~(b.wide | b.nb)

    ext2 = b.get("extras_2_runs", pd.Series(0, index=b.index)).fillna(0)
    b["team_runs"] = (
        b["runs"].fillna(0)
        + b.wide.astype(int)
        + b.nb.astype(int)
        + ext2
    )

    if "is_wicket" in b.columns:
        b["wk"] = b.is_wicket.astype(bool)
        if "dismissal_type" in b.columns:
            b["wk"] = b.wk & ~b.dismissal_type.isin(["Retire Out"])
    else:
        b["wk"] = False

    if "dismissal_type" in b.columns:
        b["bowler_wk"] = b.wk & ~b.dismissal_type.isin(
            ["RunOut", "Obstracting the field", "Obstructing the field"]
        )
    else:
        b["bowler_wk"] = b.wk

    # cumulative state
    g = b.groupby(["match_id", "innings"])
    b["cum_runs_after"]  = g.team_runs.cumsum()
    b["cum_w_after"]     = g.wk.cumsum()
    b["cum_legal_after"] = g.legal.cumsum()
    b["runs_before"]  = b.cum_runs_after  - b.team_runs
    b["w_before"]     = b.cum_w_after     - b.wk.astype(int)
    b["legal_before"] = b.cum_legal_after - b.legal.astype(int)

    # innings-1 total → target
    tot = b[b.innings == 1].groupby("match_id").team_runs.sum().rename("inn1_total")
    b = b.merge(tot, on="match_id", how="left")
    b["target"] = np.where(b.innings == 2, b.inn1_total + 1, np.nan)

    # keep only matches with both innings
    have = b.groupby("match_id").innings.nunique()
    ok   = have[have == 2].index
    b    = b[b.match_id.isin(ok)]

    # batting team wins
    if "win_team_id" in b.columns and "batting_team_id" in b.columns:
        b["bat_win"] = np.where(
            b.win_team_id == b.batting_team_id, 1.0,
            np.where(b.win_team_id == b.bowling_team_id, 0.0, np.nan)
        )
        b = b[b.bat_win.notna()]
    else:
        # can't compute WP without winner info — flag
        b["bat_win"] = np.nan

    b = b.reset_index(drop=True)
    b["ipl"] = b.is_ipl.astype(int)
    return b


# ─────────────────────────────────────────────
# STEP 2 — WIN PROBABILITY + LEVERAGE  (mirrors wp.py)
# ─────────────────────────────────────────────

OUTCOMES = ["0", "1", "2", "3", "4", "6", "W"]
MONO1 = [1, -1, 1, 0, 0]
MONO2 = [-1, -1, 1, 1, 0, 0]


def feats(inn, runs, wl, legal, target, ipl):
    bl = 120 - legal
    if inn == 1:
        crr = np.where(legal > 0, runs / np.maximum(legal, 1) * 6, 0)
        return np.c_[runs, wl, bl, crr, ipl]
    need = target - runs
    rrr  = np.where(bl > 0, need / np.maximum(bl, 1) * 6, 99)
    crr  = np.where(legal > 0, runs / np.maximum(legal, 1) * 6, 0)
    return np.c_[need, wl, bl, np.clip(rrr, 0, 60), crr, ipl]


def mk_model(inn):
    return HGB(
        max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
        min_samples_leaf=200, l2_regularization=1.0,
        monotonic_cst=(MONO1 if inn == 1 else MONO2),
        random_state=0
    )


def terminal_or_pred(inn, runs, wl, legal, m1, m2, ipl, target=None):
    runs = np.asarray(runs, float); wl = np.asarray(wl)
    legal = np.asarray(legal);      ipl = np.asarray(ipl)
    out = np.zeros(len(runs))
    if inn == 2:
        need  = target - runs
        won   = need <= 0
        ended = (wl >= 10) | (legal >= 120)
        tie   = ended & (need == 1)
        live  = ~won & ~ended
        out[won] = 1.0; out[tie] = 0.5
        if live.any():
            out[live] = m2.predict_proba(feats(2, runs[live], wl[live], legal[live], target[live], ipl[live]))[:, 1]
    else:
        ended = (wl >= 10) | (legal >= 120)
        live  = ~ended
        if live.any():
            out[live] = m1.predict_proba(feats(1, runs[live], wl[live], legal[live], None, ipl[live]))[:, 1]
        if ended.any():
            tg = runs[ended] + 1
            out[ended] = 1 - m2.predict_proba(
                feats(2, np.zeros(ended.sum()), np.zeros(ended.sum()), np.zeros(ended.sum()), tg, ipl[ended])
            )[:, 1]
    return out


def compute_wp_li(b):
    """Add wp, exp_abs, LI, P columns to b. Requires bat_win."""
    if b.bat_win.isna().all():
        b["wp"] = 0.5; b["exp_abs"] = 0.0; b["LI"] = 1.0; b["P"] = False
        return b

    # outcome distribution by phase (legal balls)
    lb    = b[b.legal].copy()
    lb["phase"] = pd.cut(lb.overid, [0, 6, 15, 20], labels=[0, 1, 2]).astype(int)
    lb["o"]     = np.where(lb.wk, "W", lb.runs.astype(str))
    dist = (
        lb[lb.o.isin(OUTCOMES)]
        .groupby("phase").o.value_counts(normalize=True)
        .unstack()[OUTCOMES].fillna(0)
    )
    dist = dist.div(dist.sum(1), axis=0)

    n      = len(b)
    wp     = np.zeros(n)
    EXP    = np.zeros(n)
    phase  = pd.cut(b.overid, [0, 6, 15, 20], labels=[0, 1, 2]).astype(int).values
    y      = b.bat_win.values
    grp    = b.match_id.values
    mask1  = (b.innings == 1).values
    mask2  = ~mask1
    X1     = feats(1, b.runs_before.values, b.w_before.values, b.legal_before.values, None,  b.ipl.values)
    X2     = feats(2, b.runs_before.values, b.w_before.values, b.legal_before.values,
                   b.target.fillna(0).values, b.ipl.values)

    gkf = GroupKFold(5)
    for k, (tr, te) in enumerate(gkf.split(b, y, grp)):
        t1 = tr[mask1[tr]]; t2 = tr[mask2[tr]]
        m1 = mk_model(1).fit(X1[t1], y[t1])
        m2 = mk_model(2).fit(X2[t2], y[t2])
        te1 = te[mask1[te]]; te2 = te[mask2[te]]
        wp[te1] = m1.predict_proba(X1[te1])[:, 1]
        wp[te2] = m2.predict_proba(X2[te2])[:, 1]

        for inn, idx in ((1, te1), (2, te2)):
            d  = b.iloc[idx]
            ph = phase[idx]
            acc = np.zeros(len(idx))
            for oi, o in enumerate(OUTCOMES):
                r   = 0 if o == "W" else int(o)
                wl2 = d.w_before.values + (1 if o == "W" else 0)
                tgt = d.target.values if inn == 2 else None
                wp_after = terminal_or_pred(
                    inn, d.runs_before.values + r, wl2,
                    d.legal_before.values + 1, m1, m2, d.ipl.values, tgt
                )
                for j, pj in enumerate(ph):
                    if pj in dist.index:
                        p = dist.loc[pj, o]
                    else:
                        p = 1 / len(OUTCOMES)
                    acc[j] += p * abs(wp_after[j] - wp[idx[j]])
            EXP[idx] = acc

    b = b.copy()
    b["wp"]      = wp
    b["exp_abs"] = EXP
    mean_abs     = EXP.mean() if EXP.mean() > 0 else 1.0
    b["LI"]      = EXP / mean_abs

    # WP after (for WPA — used in lambda estimation)
    b["wp_next"] = b.groupby(["match_id", "innings"]).wp.shift(-1)
    last = b.wp_next.isna()
    first2 = b[b.innings == 2].groupby("match_id").wp.first()
    b.loc[last & (b.innings == 1), "wp_next"] = \
        b.loc[last & (b.innings == 1), "match_id"].map(first2).values
    b.loc[last & (b.innings == 2), "wp_next"] = \
        b.loc[last & (b.innings == 2), "bat_win"]
    b["wpa"] = b.wp_next - b.wp

    # Pressure flag
    b["ph"]  = pd.cut(b.overid, [0, 6, 15, 20], labels=[0, 1, 2]).astype(int)
    b["P"]   = (
        (b.LI >= 1.5) &
        b.wp.between(0.15, 0.85) &
        ((b.legal_before >= 36) | (b.w_before >= 3) | (b.innings == 2))
    )
    return b


# ─────────────────────────────────────────────
# STEP 3 — CONTEXT BASELINE + LAMBDA  (mirrors final1.py)
# ─────────────────────────────────────────────

def add_context(b):
    b = b.copy()
    b["bl"]   = 120 - b.legal_before
    b["need"] = b.target - b.runs_before
    b["rrr"]  = (b.need / b.bl.clip(lower=1) * 6).fillna(0)

    b["rb"] = np.where(
        b.innings == 2,
        pd.cut(b.rrr.fillna(0), [-1e9, 6, 8, 10, 12, 15, 1e9], labels=False),
        -1
    )
    b["ob"] = ((b.overid - 1) // 2).clip(0, 9)
    b["wb"] = b.w_before.clip(0, 7)

    key = ["innings", "ob", "wb", "rb"]
    b["er"]  = b.groupby(key)["runs"].transform("mean")
    b["ew"]  = b.groupby(key)["wk"].transform(lambda s: s.astype(float).mean())
    b["etr"] = b.groupby(key)["team_runs"].transform("mean")
    b["ebw"] = b.groupby(key)["bowler_wk"].transform(lambda s: s.astype(float).mean())

    # lambda (run value of a wicket) by phase from WP regression
    P = b[b.P & b.bat_ok & b.legal] if "bat_ok" in b.columns else b[b.P & b.legal]
    LAMP = {}
    for ph in [0, 1, 2]:
        g = P[P.ph == ph]
        if len(g) >= 50:
            lr = LinearRegression().fit(np.c_[g.runs, g.wk.astype(float)], g.wpa)
            lam = -lr.coef_[1] / lr.coef_[0] if lr.coef_[0] != 0 else 7.0
        else:
            lam = {0: 5.8, 1: 7.6, 2: 4.4}.get(ph, 6.0)
        LAMP[ph] = float(lam)

    b["lam"] = b.ph.map(LAMP)

    # eligibility flags
    if "striker_id" not in b.columns and "striker_name" in b.columns:
        b["striker_id"]  = b.striker_name
    if "bowler_id" not in b.columns and "bowler_name" in b.columns:
        b["bowler_id"]   = b.bowler_name
    if "batting_team_id" not in b.columns and "batting_team" in b.columns:
        b["batting_team_id"] = b.batting_team

    b["bat_ok"]  = True  # all bat rows eligible unless we have specific disqual
    b["bowl_ok"] = True

    # value components
    b["rb_run"] = b.runs  - b.er
    b["rb_wk"]  = -(b.wk.astype(float) - b.ew)
    b["rw_run"] = -(b.team_runs - b.etr)
    b["rw_wk"]  = b.bowler_wk.astype(float) - b.ebw

    return b, LAMP


# ─────────────────────────────────────────────
# STEP 4 — OPPONENT ADJUSTMENT  (mirrors final2.py)
# ─────────────────────────────────────────────

def opponent_adjust(b):
    b = b.copy()
    bats  = sorted(b.striker_id.unique())
    bowls = sorted(b.bowler_id.unique())

    def design(df):
        bi = pd.Categorical(df.striker_id, categories=bats)
        bo = pd.Categorical(df.bowler_id,  categories=bowls)
        r  = np.arange(len(df))
        Xb = sp.csr_matrix((np.ones(len(df)), (r, bi.codes)), shape=(len(df), len(bats)))
        Xo = sp.csr_matrix((np.ones(len(df)), (r, bo.codes)), shape=(len(df), len(bowls)))
        ctx = sp.csr_matrix(df.is_ipl.values.astype(float)[:, None])
        return sp.hstack([Xb, Xo, ctx]).tocsr()

    fit = b[(~b.P) & b.bat_ok & b.bowl_ok & b.legal]
    if len(fit) < 100:
        b["a_rb_run"] = b.rb_run; b["a_rb_wk"] = b.rb_wk
        b["a_rw_run"] = b.rw_run; b["a_rw_wk"] = b.rw_wk
        b["VB"] = b.rb_run + b.lam * b.rb_wk
        b["VW"] = b.rw_run + b.lam * b.rw_wk
        return b

    X = design(fit)
    nb_, no_ = len(bats), len(bowls)
    eff = {}
    for comp, alpha in [("rb_run", 40), ("rb_wk", 40), ("rw_run", 40), ("rw_wk", 40)]:
        y = fit[comp].values
        rd = Ridge(alpha=alpha).fit(X, y)
        eff[comp] = (
            pd.Series(rd.coef_[:nb_],      index=bats),
            pd.Series(rd.coef_[nb_:nb_+no_], index=bowls)
        )

    b["a_rb_run"] = b.rb_run - b.bowler_id.map(eff["rb_run"][1]).fillna(0)
    b["a_rb_wk"]  = b.rb_wk  - b.bowler_id.map(eff["rb_wk"][1]).fillna(0)
    b["a_rw_run"] = b.rw_run - b.striker_id.map(eff["rw_run"][0]).fillna(0)
    b["a_rw_wk"]  = b.rw_wk  - b.striker_id.map(eff["rw_wk"][0]).fillna(0)

    b["VB"] = b.a_rb_run + b.lam * b.a_rb_wk
    b["VW"] = b.a_rw_run + b.lam * b.a_rw_wk
    return b


# ─────────────────────────────────────────────
# STEP 5 — RATINGS  (mirrors final2.py ratings())
# ─────────────────────────────────────────────

CFG = {
    "bat":  dict(ok="bat_ok",  pid="striker_id",  runc="a_rb_run", wkc="a_rb_wk", tot="VB"),
    "bowl": dict(ok="bowl_ok", pid="bowler_id",   runc="a_rw_run", wkc="a_rw_wk", tot="VW"),
}


def eb_shrink(df, col, pidc, mask, minn=30):
    x    = df[mask]
    g    = x.groupby(pidc)[col]
    mean = g.mean(); n = g.size()
    s2   = x[col].var() if len(x) > 1 else 1.0
    el   = n >= minn
    if el.sum() < 2:
        tau2 = max(s2, 1e-9)
    else:
        tau2 = max(mean[el].var() - (s2 / n[el]).mean(), 1e-9)
    k  = s2 / tau2
    mu = x[col].mean()
    return mean, n, mu + (mean - mu) * n / (n + k), k, tau2


def ratings(b, role, thr=1.5, elig=(75, 15, 100), weights=(0.8, 0.0, 0.2)):
    c   = CFG[role]
    pid = c["pid"]
    d   = b[b[c["ok"]]]

    pm = (
        (d.LI >= thr) & d.wp.between(0.15, 0.85) &
        ((d.legal_before >= 36) | (d.w_before >= 3) | (d.innings == 2))
    )

    out = pd.DataFrame(index=sorted(d[pid].unique()))

    for comp in ("runc", "wkc"):
        col = c[comp]
        m, n, eb, k, t2 = eb_shrink(d, col, pid, pm)
        out["m_"  + comp] = m
        out["eb_" + comp] = eb
        out["k_"  + comp] = k

    out["pb"]     = d[pm].groupby(pid).size()
    lam           = d[pm].groupby(pid).lam.mean()
    out["pv_eb"]  = out.eb_runc + lam * out.eb_wkc
    out["pvraw100"] = (out.m_runc + lam * out.m_wkc) * 100
    out["pv100"]  = out.pv_eb * 100

    # usual (non-pressure) level
    nonp = d[~pm]
    out["nb"]     = nonp.groupby(pid).size()
    mu, nu, ebu, ku, _ = eb_shrink(d, c["tot"], pid, ~pm)
    out["usual_eb"]  = ebu
    out["usual100"]  = ebu * 100
    out["lift100"]   = out.pv100 - out.usual100

    # consistency
    st  = d[pm].groupby([pid, "match_id"])[c["tot"]].sum().reset_index()
    st["pos"] = st[c["tot"]] > 0
    out["stints"]   = st.groupby(pid).size()
    ps              = st.groupby(pid).pos.mean()
    p0              = st.pos.mean() if len(st) > 0 else 0.5
    out["cons_raw"] = ps
    out["cons_eb"]  = (ps * out.stints + p0 * 12) / (out.stints + 12)

    # eligibility
    out["elig"] = (
        (out.pb     >= elig[0]) &
        (out.stints >= elig[1]) &
        (out.nb     >= elig[2])
    )

    e = out[out.elig]
    if len(e) >= 2:
        def z(s):
            sd = s.std()
            return (s - s.mean()) / sd if sd > 0 else s * 0
        out.loc[e.index, "score"] = (
            weights[0] * z(e.pv_eb) +
            weights[1] * z(e.lift100) +
            weights[2] * z(e.cons_eb)
        )

    return out


# ─────────────────────────────────────────────
# STEP 6 — BOOTSTRAP BAGS  (mirrors bag.py, 50 resamples for speed)
# ─────────────────────────────────────────────

def bootstrap_ratings(b, role, base_out, NB=200, weights=(0.8, 0.0, 0.2)):
    mids = b.match_id.unique()
    idx  = {m: np.where(b.match_id.values == m)[0] for m in mids}
    rng  = np.random.default_rng(7)  # same seed as bag.py so results match dashboard_data.json

    S  = {}   # scores per player
    T  = {}   # top-10 hit count
    RK = {}   # ranks

    for i in range(NB):
        pick = rng.choice(mids, len(mids), replace=True)
        ii   = np.concatenate([idx[m] for m in pick])
        bs   = b.iloc[ii].copy()
        bs["match_id"] = np.repeat(
            np.arange(len(pick)), [len(idx[m]) for m in pick]
        )
        try:
            o = ratings(bs, role, weights=weights)
            e = o[o.elig].sort_values("score", ascending=False)
            for r_, (p, row) in enumerate(e.iterrows(), 1):
                S.setdefault(p, []).append(row["score"])
                RK.setdefault(p, []).append(r_)
                if r_ <= 10:
                    T[p] = T.get(p, 0) + 1
        except Exception:
            pass

    e_base = base_out[base_out.elig].sort_values("score", ascending=False)
    result = pd.DataFrame(index=e_base.index)
    result["point_score"] = e_base["score"]
    result["bag_score"]   = [
        np.mean(S[p]) if p in S and len(S[p]) >= 0.25 * NB else np.nan
        for p in e_base.index
    ]
    result["top10_freq"]  = [T.get(p, 0) / NB for p in e_base.index]
    result["mean_rank"]   = [np.mean(RK.get(p, [99])) for p in e_base.index]
    result["median_rank"] = [np.median(RK.get(p, [99])) for p in e_base.index]
    result["p10_rank"]    = [np.percentile(RK.get(p, [99]), 10) for p in e_base.index]
    result["p90_rank"]    = [np.percentile(RK.get(p, [99]), 90) for p in e_base.index]
    result["final_score"] = 0.5 * result.point_score.fillna(0) + 0.5 * result.bag_score.fillna(0)

    result = result.join(e_base[[
        "pb", "stints", "pvraw100", "pv100", "usual100", "lift100", "cons_eb", "cons_raw"
    ]])
    return result.sort_values("final_score", ascending=False)


# ─────────────────────────────────────────────
# STEP 7 — BUILD DASHBOARD JSON  (mirrors mkjson.py)
# ─────────────────────────────────────────────

def player_name(b, pid_col, name_col, pid):
    rows = b[b[pid_col] == pid]
    if len(rows) and name_col in rows.columns:
        return str(rows[name_col].iloc[0])
    return str(pid)


def build_dashboard_json(b, T_bat, T_bowl):
    """
    b        : fully processed ball DataFrame
    T_bat    : result from bootstrap_ratings for bat
    T_bowl   : result from bootstrap_ratings for bowl
    Returns  : dict matching dashboard_data.json schema
    """
    out = {}

    # ── batters ──
    bat_rows = []
    for pid, r in T_bat.head(10).iterrows():
        name = player_name(b, "striker_id", "striker_name", pid)
        # per-player pressure ball stats
        d  = b[b.P & (b.striker_id == pid) & b.bat_ok]
        l  = d[d.legal]
        sr       = float(l.runs.sum() / len(l) * 100)       if len(l) > 0 else 0.0
        exp_sr   = float(l.er.mean() * 100)                  if len(l) > 0 else 0.0
        out_pct  = float(l.wk.mean() * 100)                  if len(l) > 0 else 0.0
        exp_out  = float(l.ew.mean() * 100)                  if len(l) > 0 else 0.0
        dots     = float((l.runs == 0).mean() * 100)         if len(l) > 0 else 0.0
        ipl_b    = int(d.is_ipl.sum())
        t20i_b   = int((~d.is_ipl).sum())

        bat_rows.append({
            "name":        name,
            "point_score": round(float(r.point_score), 2),
            "bag_score":   round(float(r.bag_score),   2) if not pd.isna(r.bag_score) else 0.0,
            "top10_freq":  round(float(r.top10_freq),  2),
            "mean_rank":   round(float(r.mean_rank),   2),
            "final_score": round(float(r.final_score), 2),
            "pb":          int(r.pb),
            "stints":      int(r.stints),
            "pvraw100":    round(float(r.pvraw100),    2),
            "pv100":       round(float(r.pv100),       2),
            "usual100":    round(float(r.usual100),    2),
            "lift100":     round(float(r.lift100),     2),
            "cons_eb":     round(float(r.cons_eb),     2),
            "cons_raw":    round(float(r.cons_raw),    2),
            "ipl":         ipl_b,
            "t20i":        t20i_b,
            "sr":          round(sr,     2),
            "exp_sr":      round(exp_sr, 2),
            "out_pct":     round(out_pct, 2),
            "exp_out":     round(exp_out, 2),
            "dots":        round(dots,   2),
            "median_rank": round(float(r.median_rank), 1),
            "p10_rank":    round(float(r.p10_rank),    1),
            "p90_rank":    round(float(r.p90_rank),    1),
        })
    out["bat"] = bat_rows

    # ── bowlers ──
    bowl_rows = []
    for pid, r in T_bowl.head(10).iterrows():
        name = player_name(b, "bowler_id", "bowler_name", pid)
        d  = b[b.P & (b.bowler_id == pid) & b.bowl_ok]
        l  = d[d.legal]
        econ    = float(d.team_runs.sum() / len(l) * 6)      if len(l) > 0 else 0.0
        exp_ec  = float(d.etr.mean() * 6)                     if len(d) > 0 else 0.0
        wk_pct  = float(l.bowler_wk.mean() * 100)             if len(l) > 0 else 0.0
        exp_wk  = float(l.ebw.mean() * 100)                   if len(l) > 0 else 0.0
        dots    = float((l.runs == 0).mean() * 100)           if len(l) > 0 else 0.0
        ipl_b   = int(d.is_ipl.sum())
        t20i_b  = int((~d.is_ipl).sum())

        bowl_rows.append({
            "name":        name,
            "point_score": round(float(r.point_score), 2),
            "bag_score":   round(float(r.bag_score),   2) if not pd.isna(r.bag_score) else 0.0,
            "top10_freq":  round(float(r.top10_freq),  2),
            "mean_rank":   round(float(r.mean_rank),   2),
            "final_score": round(float(r.final_score), 2),
            "pb":          int(r.pb),
            "stints":      int(r.stints),
            "pvraw100":    round(float(r.pvraw100),    2),
            "pv100":       round(float(r.pv100),       2),
            "usual100":    round(float(r.usual100),    2),
            "lift100":     round(float(r.lift100),     2),
            "cons_eb":     round(float(r.cons_eb),     2),
            "cons_raw":    round(float(r.cons_raw),    2),
            "ipl":         ipl_b,
            "t20i":        t20i_b,
            "econ":        round(econ,   2),
            "exp_econ":    round(exp_ec, 2),
            "wk_pct":      round(wk_pct, 2),
            "exp_wk":      round(exp_wk, 2),
            "dots":        round(dots,   2),
            "median_rank": round(float(r.median_rank), 1),
            "p10_rank":    round(float(r.p10_rank),    1),
            "p90_rank":    round(float(r.p90_rank),    1),
        })
    out["bowl"] = bowl_rows

    # ── lift tables ──
    out["lift_bat"] = [
        [r["name"],
         f"{r['usual100']:.0f}",
         f"{r['pv100']:.0f}",
         f"{r['lift100']:+.0f}"]
        for _, r in pd.DataFrame(bat_rows).iterrows()
    ]
    out["lift_bowl"] = [
        [r["name"],
         f"{r['usual100']:.0f}",
         f"{r['pv100']:.0f}",
         f"{r['lift100']:+.0f}"]
        for _, r in pd.DataFrame(bowl_rows).iterrows()
    ]

    # ── next in line (11-16) ──
    out["next_bat"] = [
        [i + 11, player_name(b, "striker_id", "striker_name", pid),
         f"{r.final_score:.2f}", f"{r.top10_freq*100:.0f}%"]
        for i, (pid, r) in enumerate(T_bat.iloc[10:16].iterrows())
    ]
    out["next_bowl"] = [
        [i + 11, player_name(b, "bowler_id", "bowler_name", pid),
         f"{r.final_score:.2f}", f"{r.top10_freq*100:.0f}%"]
        for i, (pid, r) in enumerate(T_bowl.iloc[10:16].iterrows())
    ]

    # ── overview stats ──
    out["overview"] = {
        "n_match":    int(b.match_id.nunique()),
        "n_ball":     int(len(b)),
        "n_pressure": int(b.P.sum()),
        "share":      round(float(b.P.mean()), 4),
        "n_ipl":      int(b[b.is_ipl].match_id.nunique()),
        "n_t20i":     int(b[~b.is_ipl].match_id.nunique()),
    }

    return out


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def run_pipeline(ball_df, matches_df=None, competitions_df=None,
                 player_map_df=None, progress_cb=None):
    """
    Full pipeline. progress_cb(msg) called with status strings if provided.
    Returns dashboard JSON dict.
    """
    def log(msg):
        if progress_cb:
            progress_cb(msg)

    log("Step 1/6 — Preparing data…")
    b = prep(ball_df, matches_df, competitions_df, player_map_df)

    if b.bat_win.isna().all():
        raise ValueError("Cannot compute win probability — missing win_team_id or batting_team_id columns in matches/ball_by_ball data.")

    log(f"Step 2/6 — Training WP model + computing leverage ({b.match_id.nunique()} matches)…")
    b = compute_wp_li(b)

    log("Step 3/6 — Computing context baselines + wicket run-values…")
    b, LAMP = add_context(b)

    log("Step 4/6 — Opponent quality adjustment (ridge regression)…")
    b = opponent_adjust(b)

    log("Step 5/6 — Computing EB ratings…")
    base_bat  = ratings(b, "bat")
    base_bowl = ratings(b, "bowl")

    log("Step 6/6 — Bootstrap stability (200 resamples)…")
    T_bat  = bootstrap_ratings(b, "bat",  base_bat)
    T_bowl = bootstrap_ratings(b, "bowl", base_bowl)

    log("Building dashboard output…")
    return build_dashboard_json(b, T_bat, T_bowl)


# ═════════════════════════════════════════════════════════════════════════════
# PART 2 — FASTAPI SERVER
# ═════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="T20 Cricket Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── in-memory store ──────────────────────────────────────────────────────────
store: dict = {}


# ── helpers ──────────────────────────────────────────────────────────────────

def safe_json(obj):
    """Recursively convert numpy types to Python native for JSON."""
    if isinstance(obj, dict):
        return {k: safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [safe_json(i) for i in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if pd.isna(obj) if not isinstance(obj, (list, dict, np.ndarray)) else False:
        return None
    return obj


def read_csv(upload: UploadFile) -> pd.DataFrame:
    content = upload.file.read()
    return pd.read_csv(io.BytesIO(content))


def build_analytics(store: dict) -> dict:
    """
    Compute all analytics from whatever tables are present.
    Returns a dict with keys: overview, batter_stats, bowler_stats,
    team_stats, match_stats, run_distribution, wicket_types,
    phase_stats, over_economy, top_scorers, top_wickets.
    """
    b = store.get("ball_by_ball")
    m = store.get("matches")
    c = store.get("competitions")
    pm = store.get("competition_team_player_mapping")

    if b is None:
        return {}

    df = b.copy()

    # ── merge matches ────────────────────────────────────────────────────────
    if m is not None:
        m_cols = [col for col in [
            "match_id", "comp_id", "match_date", "stage",
            "win_team_id", "result", "venue_country",
            "revised_target", "first_inn_revised_overs",
            "second_inn_revised_overs", "home_team", "away_team"
        ] if col in m.columns]
        df = df.merge(m[m_cols], on="match_id", how="left")

    if c is not None:
        c_cols = [col for col in ["comp_id", "comp_name", "match_format", "season"] if col in c.columns]
        if "comp_id" in df.columns:
            df = df.merge(c[c_cols], on="comp_id", how="left")

    # ── basic flags ──────────────────────────────────────────────────────────
    df["wide"] = df.get("extras_type", pd.Series(dtype=str)) == "wide"
    df["nb"] = df.get("extras_type", pd.Series(dtype=str)) == "Overstep"
    df["legal"] = ~(df["wide"] | df["nb"])
    df["wk"] = df.get("is_wicket", False).astype(bool)
    if "dismissal_type" in df.columns:
        df["wk"] = df["wk"] & ~df["dismissal_type"].isin(["Retire Out"])

    extras2 = df.get("extras_2_runs", pd.Series(0, index=df.index)).fillna(0)
    df["team_runs"] = (
        df.get("runs", 0).fillna(0)
        + df["wide"].astype(int)
        + df["nb"].astype(int)
        + extras2
    )

    # ── phase ────────────────────────────────────────────────────────────────
    if "innings_ball_num" in df.columns:
        df["ball_in_inn"] = df["innings_ball_num"]
    elif "overid" in df.columns and "over_ball_num" in df.columns:
        df["ball_in_inn"] = (df["overid"] - 1) * 6 + df["over_ball_num"]
    else:
        df["ball_in_inn"] = np.arange(len(df))

    df["over_num"] = df["ball_in_inn"].apply(lambda x: min(int((x - 1) / 6) + 1 if x > 0 else 1, 20))
    df["phase"] = pd.cut(
        df["over_num"],
        bins=[0, 6, 15, 20],
        labels=["Powerplay (1-6)", "Middle (7-15)", "Death (16-20)"]
    )

    total_matches = df["match_id"].nunique() if "match_id" in df.columns else 0
    total_deliveries = len(df)
    total_runs = int(df["team_runs"].sum())
    total_wickets = int(df["wk"].sum())
    total_fours = int(df.get("is_four", pd.Series(False)).sum())
    total_sixes = int(df.get("is_six", pd.Series(False)).sum())

    # ── OVERVIEW ─────────────────────────────────────────────────────────────
    overview = {
        "total_matches": total_matches,
        "total_deliveries": total_deliveries,
        "total_runs": total_runs,
        "total_wickets": total_wickets,
        "total_fours": total_fours,
        "total_sixes": total_sixes,
        "avg_match_runs": round(total_runs / max(total_matches, 1), 1),
        "run_rate": round(total_runs / max(df["legal"].sum(), 1) * 6, 2),
    }

    # ── COMPETITION breakdown ────────────────────────────────────────────────
    comp_stats = []
    if "comp_name" in df.columns:
        for comp, cdf in df.groupby("comp_name"):
            matches = cdf["match_id"].nunique() if "match_id" in cdf.columns else 0
            runs = int(cdf["team_runs"].sum())
            wkts = int(cdf["wk"].sum())
            comp_stats.append({
                "competition": str(comp),
                "matches": matches,
                "runs": runs,
                "wickets": wkts,
                "run_rate": round(runs / max(cdf["legal"].sum(), 1) * 6, 2),
            })
        comp_stats.sort(key=lambda x: x["matches"], reverse=True)

    # ── BATTER STATS ─────────────────────────────────────────────────────────
    batter_stats = []
    if "striker_name" in df.columns:
        bat_df = df[df["legal"]].copy()
        bat_grp = bat_df.groupby("striker_name")
        bat_runs = bat_grp["runs"].sum()
        bat_balls = bat_grp.size()
        bat_dismissed = bat_df[bat_df["wk"]].groupby("striker_name").size()
        bat_fours = bat_df[bat_df.get("is_four", pd.Series(False)).astype(bool)].groupby("striker_name").size()
        bat_sixes = bat_df[bat_df.get("is_six", pd.Series(False)).astype(bool)].groupby("striker_name").size()
        innings = bat_df.groupby("striker_name")["match_id"].nunique() if "match_id" in bat_df.columns else pd.Series(dtype=int)

        for player in bat_runs.index:
            r = int(bat_runs.get(player, 0))
            bl = int(bat_balls.get(player, 1))
            d = int(bat_dismissed.get(player, 0))
            inn = int(innings.get(player, 1)) if len(innings) > 0 else 1
            avg = round(r / max(d, 1), 2)
            sr = round(r / max(bl, 1) * 100, 2)
            if bl < 10:
                continue
            batter_stats.append({
                "player": str(player),
                "innings": inn,
                "runs": r,
                "balls": bl,
                "avg": avg,
                "strike_rate": sr,
                "fours": int(bat_fours.get(player, 0)),
                "sixes": int(bat_sixes.get(player, 0)),
                "dismissals": d,
            })
        batter_stats.sort(key=lambda x: x["runs"], reverse=True)

    # ── BOWLER STATS ─────────────────────────────────────────────────────────
    bowler_stats = []
    if "bowler_name" in df.columns:
        bowl_df = df.copy()
        bowl_grp = bowl_df.groupby("bowler_name")
        bowl_runs = bowl_grp["team_runs"].sum()
        bowl_legal = bowl_df[bowl_df["legal"]].groupby("bowler_name").size()
        bowl_wkts = bowl_df[bowl_df["wk"]].groupby("bowler_name").size()
        bowl_dots = bowl_df[(bowl_df["legal"]) & (bowl_df["team_runs"] == 0)].groupby("bowler_name").size()

        for player in bowl_runs.index:
            r = int(bowl_runs.get(player, 0))
            bl = int(bowl_legal.get(player, 1))
            w = int(bowl_wkts.get(player, 0))
            dots = int(bowl_dots.get(player, 0))
            if bl < 12:
                continue
            overs = round(bl / 6, 1)
            econ = round(r / max(overs, 0.1), 2)
            avg_w = round(r / max(w, 1), 2)
            dot_pct = round(dots / max(bl, 1) * 100, 1)
            bowler_stats.append({
                "player": str(player),
                "overs": overs,
                "balls": bl,
                "runs": r,
                "wickets": w,
                "economy": econ,
                "avg": avg_w,
                "dot_pct": dot_pct,
            })
        bowler_stats.sort(key=lambda x: x["wickets"], reverse=True)

    # ── TEAM STATS ───────────────────────────────────────────────────────────
    team_stats = []
    team_col = "batting_team_id" if "batting_team_id" in df.columns else None
    if team_col and "batting_type" not in df.columns:
        pass

    # Use home_team / away_team from matches for team batting
    if "batting_team_id" in df.columns:
        tgrp = df.groupby("batting_team_id")
        t_runs = tgrp["team_runs"].sum()
        t_legal = df[df["legal"]].groupby("batting_team_id").size()
        t_wkts = df[df["wk"]].groupby("batting_team_id").size()
        t_matches = df.groupby("batting_team_id")["match_id"].nunique() if "match_id" in df.columns else pd.Series(dtype=int)
        # get team names from mapping
        tname_map = {}
        if pm is not None and "team_id" in pm.columns and "team_name" in pm.columns:
            for _, row in pm.drop_duplicates("team_id").iterrows():
                tname_map[row["team_id"]] = row["team_name"]
        elif m is not None:
            for _, row in m.iterrows():
                if "home_team_id" in m.columns and "home_team" in m.columns:
                    tname_map[row.get("home_team_id")] = row.get("home_team", "")
                    tname_map[row.get("away_team_id")] = row.get("away_team", "")

        for tid in t_runs.index:
            r = int(t_runs.get(tid, 0))
            bl = int(t_legal.get(tid, 1))
            w = int(t_wkts.get(tid, 0))
            mt = int(t_matches.get(tid, 0)) if len(t_matches) > 0 else 0
            name = tname_map.get(tid, str(tid))
            team_stats.append({
                "team": name,
                "matches": mt,
                "runs": r,
                "wickets": w,
                "run_rate": round(r / max(bl, 1) * 6, 2),
            })
        team_stats.sort(key=lambda x: x["runs"], reverse=True)

    # ── PHASE STATS ──────────────────────────────────────────────────────────
    phase_stats = []
    if "phase" in df.columns:
        for phase, pdf in df.groupby("phase", observed=True):
            legal = pdf[pdf["legal"]]
            r = int(pdf["team_runs"].sum())
            bl = int(legal.shape[0])
            w = int(pdf["wk"].sum())
            phase_stats.append({
                "phase": str(phase),
                "runs": r,
                "balls": bl,
                "wickets": w,
                "run_rate": round(r / max(bl, 1) * 6, 2),
                "dot_pct": round(legal[legal["team_runs"] == 0].shape[0] / max(bl, 1) * 100, 1),
                "boundary_pct": round(
                    (pdf.get("is_four", pd.Series(False)).sum() + pdf.get("is_six", pd.Series(False)).sum()) / max(bl, 1) * 100, 1
                ),
            })

    # ── OVER ECONOMY (avg runs per over, by over number) ─────────────────────
    over_economy = []
    if "over_num" in df.columns:
        ov_grp = df.groupby("over_num")
        ov_runs = ov_grp["team_runs"].sum()
        ov_matches = df.groupby("over_num")["match_id"].nunique() if "match_id" in df.columns else ov_grp.size() / 6
        for ov in sorted(ov_runs.index):
            matches_with_over = int(ov_matches.get(ov, 1))
            over_economy.append({
                "over": int(ov),
                "avg_runs": round(float(ov_runs.get(ov, 0)) / max(matches_with_over, 1), 2),
                "total_runs": int(ov_runs.get(ov, 0)),
            })

    # ── WICKET TYPES ─────────────────────────────────────────────────────────
    wicket_types = []
    if "dismissal_type" in df.columns:
        wk_df = df[df["wk"]]
        for dtype, cnt in wk_df["dismissal_type"].value_counts().items():
            wicket_types.append({"type": str(dtype), "count": int(cnt)})

    # ── RUN DISTRIBUTION (runs off bat per ball) ──────────────────────────────
    run_dist = []
    if "runs" in df.columns:
        for val, cnt in df[df["legal"]]["runs"].value_counts().sort_index().items():
            run_dist.append({"runs": int(val), "count": int(cnt)})

    # ── MATCH RESULTS ─────────────────────────────────────────────────────────
    match_results = []
    if m is not None and "result" in m.columns:
        for _, row in m.head(50).iterrows():
            match_results.append({
                "match_id": int(row.get("match_id", 0)),
                "date": str(row.get("match_date", "")),
                "home": str(row.get("home_team", "")),
                "away": str(row.get("away_team", "")),
                "result": str(row.get("result", "")),
                "stage": str(row.get("stage", "")),
            })

    return {
        "overview": overview,
        "comp_stats": comp_stats[:20],
        "batter_stats": batter_stats[:200],
        "bowler_stats": bowler_stats[:200],
        "team_stats": team_stats[:30],
        "phase_stats": phase_stats,
        "over_economy": over_economy,
        "wicket_types": wicket_types,
        "run_distribution": run_dist,
        "match_results": match_results,
    }


# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "T20 Analytics API running"}


# ── CLUTCHRANK DATA ───────────────────────────────────────────────────────
# Looks for dashboard_data.json. The first entry resolves robustly relative to
# this file (dashboard/backend -> project root), regardless of the CWD.
_HERE = Path(__file__).parent
_DATA_PATHS = [
    _HERE.parent.parent / "dashboard_data.json",      # project root (code/)
    Path(__file__).parent.parent.parent / "dashboard_data.json",  # same, explicit
    _HERE / "../../dashboard_data.json",
    _HERE / "../dashboard_data.json",
    _HERE / "dashboard_data.json",
]

@app.get("/pressure")
def get_pressure():
    for p in _DATA_PATHS:
        resolved = p.resolve()
        if resolved.exists():
            with open(resolved, "r", encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(status_code=404, detail="dashboard_data.json not found next to backend")


# ── PRESSURE PIPELINE JOB TRACKING ───────────────────────────────────────────
_job: dict = {"status": "idle", "msg": "", "result": None, "error": None}


@app.post("/pressure/run")
async def run_pressure(
    ball_by_ball: UploadFile                    = File(...),
    matches: Optional[UploadFile]               = File(None),
    competitions: Optional[UploadFile]          = File(None),
    competition_team_player_mapping: Optional[UploadFile] = File(None),
):
    """
    Accepts CSVs, runs the full ClutchRank pipeline in a background thread,
    returns immediately with {"status":"running"}.
    Poll GET /pressure/status for progress, GET /pressure/result for final data.
    """
    if _job["status"] == "running":
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress.")

    def read(upload):
        if upload and upload.filename:
            content = upload.file.read()
            return pd.read_csv(io.BytesIO(content), low_memory=False)
        return None

    ball_df  = read(ball_by_ball)
    match_df = read(matches)
    comp_df  = read(competitions)
    pm_df    = read(competition_team_player_mapping)

    if ball_df is None:
        raise HTTPException(status_code=400, detail="ball_by_ball.csv is required.")

    _job.update({"status": "running", "msg": "Starting pipeline…", "result": None, "error": None})

    def worker():
        try:
            def cb(msg):
                _job["msg"] = msg

            result = run_pipeline(ball_df, match_df, comp_df, pm_df, progress_cb=cb)
            _job["result"] = result
            _job["status"] = "done"
            _job["msg"]    = "Complete"
        except Exception as e:
            _job["status"] = "error"
            _job["error"]  = str(e)
            _job["msg"]    = f"Error: {e}"

    threading.Thread(target=worker, daemon=True).start()
    return {"status": "running", "msg": "Pipeline started"}


@app.get("/pressure/status")
def pressure_status():
    return {
        "status": _job["status"],
        "msg":    _job["msg"],
        "error":  _job["error"],
    }


@app.get("/pressure/result")
def pressure_result():
    if _job["status"] != "done":
        raise HTTPException(status_code=404, detail=f"No result yet — status: {_job['status']}")
    return _job["result"]


@app.post("/upload")
async def upload_files(
    ball_by_ball: Optional[UploadFile] = File(None),
    matches: Optional[UploadFile] = File(None),
    competitions: Optional[UploadFile] = File(None),
    competition_team_player_mapping: Optional[UploadFile] = File(None),
    playing_eleven: Optional[UploadFile] = File(None),
    teams: Optional[UploadFile] = File(None),
):
    uploaded = []
    try:
        if ball_by_ball and ball_by_ball.filename:
            store["ball_by_ball"] = read_csv(ball_by_ball)
            uploaded.append("ball_by_ball")
        if matches and matches.filename:
            store["matches"] = read_csv(matches)
            uploaded.append("matches")
        if competitions and competitions.filename:
            store["competitions"] = read_csv(competitions)
            uploaded.append("competitions")
        if competition_team_player_mapping and competition_team_player_mapping.filename:
            store["competition_team_player_mapping"] = read_csv(competition_team_player_mapping)
            uploaded.append("competition_team_player_mapping")
        if playing_eleven and playing_eleven.filename:
            store["playing_eleven"] = read_csv(playing_eleven)
            uploaded.append("playing_eleven")
        if teams and teams.filename:
            store["teams"] = read_csv(teams)
            uploaded.append("teams")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading CSV: {str(e)}")

    rows = {k: len(v) for k, v in store.items()}
    return {"uploaded": uploaded, "rows": rows}


@app.get("/analytics")
def get_analytics():
    if not store:
        raise HTTPException(status_code=404, detail="No data loaded. Upload CSVs first.")
    result = build_analytics(store)
    return safe_json(result)


@app.get("/status")
def get_status():
    return {
        "loaded": list(store.keys()),
        "rows": {k: len(v) for k, v in store.items()},
    }


@app.delete("/reset")
def reset():
    store.clear()
    return {"status": "reset"}
