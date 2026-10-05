"""Additivity / boundedness of serving capacity under request-type mixes.

Question: given the maximum sustainable request rate C_i (req/min) of each pure
interval-matrix cell i, can the capacity of a workload mix with proportions p_i be
predicted from the C_i alone?

Candidate laws (power means of the pure capacities, weighted by the mix proportions):
  * harmonic   (q=-1): 1/C_mix = sum p_i / C_i   -> each request of type i consumes 1/C_i
                        of the server's capacity ("resource additivity");
  * geometric  (q= 0);
  * arithmetic (q=+1): C_mix = sum p_i C_i        -> naive linear interpolation.
Boundedness ("acotability"): min_i C_i <= C_mix <= max_i C_i, and the tighter
Jensen envelope harmonic <= C_mix <= arithmetic.

Every cell/mix run is a binary search over REQ_MIN with a pass/fail SLA evaluation, so
the capacity is never observed directly. The Bayesian model treats it as a latent
threshold: P(pass | r) = logistic((theta - log r) / s), using every evaluation of every
run. The frequentist analysis uses the final bracket [LARGEST_TRUE, SMALLEST_FALSE].

Usage:  python analysis/additivity_analysis.py --out <dir>
Needs:  pandas numpy scipy statsmodels pymc arviz
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import MergeAllCsv  # noqa: E402

MODEL_NAMES = {
    "deepseek-ai_DeepSeek-R1-Distill-Qwen-7B-A40-1gpus": "DeepSeek-R1-Qwen-7B",
    "google_gemma-7b-A40-1gpus": "Gemma-7B",
    "meta-llama_Llama-3.1-8B-Instruct-A40-1gpus": "Llama-3.1-8B",
}
ROPE = np.log(1.10)  # +-10 % is treated as practically additive
ROPE_TIGHT = np.log(1.05)


# --------------------------------------------------------------------------- data
def load():
    columns, rows, _ = MergeAllCsv.merge_all_csv(
        root=str(ROOT / "MIT_MST_results"), source_column="RESULTS_SOURCE"
    )
    d = pd.DataFrame(rows, columns=columns)
    for c in ["REQ_MIN", "LARGEST_TRUE", "SMALLEST_FALSE", "TOTAL_REQUESTS", "SUCCESS_RATE"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["EVALUATION"] = d["EVALUATION"].astype(str).str.lower() == "true"
    d["FINISHED"] = d["FINISHED"].astype(str).str.lower() == "true"
    d["model"] = d.RESULTS_SOURCE.map(MODEL_NAMES)
    kind = d.EXPERIMENT_NAME.str.extract(r"Experiment_(MIX_)?(M[IS]T)")
    d["is_mix"] = kind[0].notna()
    d["kind"] = kind[1]
    d["unit"] = d.RESULTS_SOURCE + "|" + d.EXPERIMENT_NAME + "|" + d.IDENTIFIER
    return d.sort_values(["unit", "DATE"]).reset_index(drop=True)


def parse_mix(s):
    parts = re.findall(r"\(([\d-]+):([\d-]+),([\d.]+)\)", s)
    return {"%s_%s" % (a, b): float(p) for a, b, p in parts}


def realised_props(x):
    """Request-weighted mean of the realised proportions over the iterations of one run."""
    acc, w = {}, 0.0
    for js, n in zip(x.ADDITIVE_TRUE_PROPORTIONS, x.TOTAL_REQUESTS):
        try:
            props = json.loads(js)
        except (TypeError, ValueError):
            continue
        for k, v in props.items():
            acc[k.replace(":", "_")] = acc.get(k.replace(":", "_"), 0.0) + v * n
        w += n
    if not w:
        return None
    tot = sum(acc.values())
    return {k: v / tot for k, v in acc.items()}


def build_units(d):
    units = []
    for uid, x in d.groupby("unit", sort=False):
        last = x.iloc[-1]
        lt, sf = last.LARGEST_TRUE, last.SMALLEST_FALSE
        lo, hi = (lt, sf) if (pd.notna(lt) and pd.notna(sf) and lt < sf) else (
            min(lt, sf), max(lt, sf)) if pd.notna(lt) and pd.notna(sf) else (lt, lt)
        u = dict(unit=uid, model=last.model, kind=last.kind, is_mix=bool(last.is_mix),
                 experiment=last.EXPERIMENT_NAME, cell=last.IDENTIFIER, n_eval=len(x),
                 lt=lt, sf=sf, lo=lo, hi=hi, monotone=bool(lt < sf) if pd.notna(sf) else True,
                 c_hat=float(np.sqrt(lo * hi)))
        if u["is_mix"]:
            design = parse_mix(last.WORKLOAD_MIX)
            props = realised_props(x) or design
            u["design"] = design
            u["props"] = {k: props.get(k, 0.0) for k in design}
            s = sum(u["props"].values())
            u["props"] = {k: v / s for k, v in u["props"].items()}
            u["label"] = " + ".join("%s@%.3g" % (k, v) for k, v in design.items())
        units.append(u)
    return pd.DataFrame(units)


# ------------------------------------------------------------------ frequentist
def power_mean_log(logc, p, q):
    logc, p = np.asarray(logc), np.asarray(p)
    if abs(q) < 1e-9:
        return float(np.sum(p * logc))
    return float(np.log(np.sum(p * np.exp(q * logc))) / q)


def frequentist(units):
    pure = units[~units.is_mix].copy()
    pure["logc"] = np.log(pure.c_hat)
    cell = pure.groupby(["model", "kind", "cell"]).logc.agg(["mean", "std", "count"]).reset_index()
    pooled_sd = float(np.sqrt(np.nanmean(cell["std"] ** 2)))  # run-to-run log-sd, pooled
    cell["se"] = np.where(cell["count"] > 1, cell["std"].fillna(pooled_sd), pooled_sd) / np.sqrt(cell["count"])
    cell["se"] = np.maximum(cell["se"], pooled_sd / np.sqrt(cell["count"]))
    cmap = {(r.model, r.kind, r.cell): (r["mean"], r.se) for _, r in cell.iterrows()}

    mixes = units[units.is_mix].copy()
    rec = []
    for _, m in mixes.iterrows():
        keys = list(m.props)
        mu = np.array([cmap[(m.model, m.kind, k)][0] for k in keys])
        se = np.array([cmap[(m.model, m.kind, k)][1] for k in keys])
        p = np.array([m.props[k] for k in keys])
        logH = power_mean_log(mu, p, -1)
        logA = power_mean_log(mu, p, 1)
        logG = power_mean_log(mu, p, 0)
        w = p / np.exp(mu)
        w = w / w.sum()  # d logH / d mu_i
        se_pred = float(np.sqrt(np.sum((w * se) ** 2)))
        # resolution of the final binary-search bracket (uniform within the bracket)
        se_obs = float(np.log(m.hi / m.lo) / np.sqrt(12)) if m.hi > m.lo else 0.01
        se_obs = max(se_obs, pooled_sd)  # a single run carries run-to-run noise as well
        lo_obs = np.log(m.c_hat)
        rec.append(dict(unit=m.unit, model=m.model, kind=m.kind, label=m.label,
                        n_comp=len(keys), c_obs=m.c_hat, H=np.exp(logH), A=np.exp(logA),
                        G=np.exp(logG), cmin=np.exp(mu.min()), cmax=np.exp(mu.max()),
                        r_H=lo_obs - logH, r_A=lo_obs - logA, r_G=lo_obs - logG,
                        se=float(np.sqrt(se_pred ** 2 + se_obs ** 2)),
                        hetero=float(mu.max() - mu.min()),
                        has_long_out=any(k.endswith("1000-1500") for k in keys),
                        family=("equal-count" if len(set(np.round(list(m.design.values()), 6))) == 1
                                else ("multi-type" if len(keys) > 2 else "load-balanced")),
                        load_share_max=float(w.max()),
                        in_minmax=bool(np.exp(mu.min()) <= m.c_hat <= np.exp(mu.max())),
                        in_HA=bool(np.exp(logH) <= m.c_hat <= np.exp(logA)),
                        mu=mu.tolist(), p=p.tolist(), comps=keys))
    fm = pd.DataFrame(rec)
    out = {"pooled_replicate_sd": pooled_sd, "n_mix_runs": len(fm),
           "n_designs": int(fm.label.nunique()), "cells": cell.to_dict("records")}

    def tests(r, se):
        n = len(r)
        t = stats.ttest_1samp(r, 0)
        w = stats.wilcoxon(r) if n >= 6 else None
        # TOST equivalence with +-10 % margin
        sd = r.std(ddof=1)
        tl = (r.mean() + ROPE) / (sd / np.sqrt(n))
        tu = (r.mean() - ROPE) / (sd / np.sqrt(n))
        p_tost = max(1 - stats.t.cdf(tl, n - 1), stats.t.cdf(tu, n - 1))
        ci = stats.t.interval(0.95, n - 1, loc=r.mean(), scale=sd / np.sqrt(n))
        # DerSimonian-Laird random-effects meta-analysis
        wi = 1 / se ** 2
        fe = np.sum(wi * r) / np.sum(wi)
        Q = float(np.sum(wi * (r - fe) ** 2))
        tau2 = max(0.0, (Q - (n - 1)) / (np.sum(wi) - np.sum(wi ** 2) / np.sum(wi)))
        ws = 1 / (se ** 2 + tau2)
        re_ = np.sum(ws * r) / np.sum(ws)
        re_se = np.sqrt(1 / np.sum(ws))
        return dict(n=n, mean=float(r.mean()), median=float(np.median(r)), sd=float(sd),
                    ci95=[float(ci[0]), float(ci[1])], t=float(t.statistic), p_t=float(t.pvalue),
                    p_wilcoxon=float(w.pvalue) if w else None, p_tost=float(p_tost),
                    rmse=float(np.sqrt(np.mean(r ** 2))), mae=float(np.mean(np.abs(r))),
                    re_mean=float(re_), re_ci=[float(re_ - 1.96 * re_se), float(re_ + 1.96 * re_se)],
                    Q=Q, p_Q=float(1 - stats.chi2.cdf(Q, n - 1)), tau=float(np.sqrt(tau2)),
                    I2=float(max(0.0, (Q - (n - 1)) / Q)) if Q > 0 else 0.0)

    out["tests"] = {}
    for law in ["H", "G", "A"]:
        out["tests"][law] = {"all": tests(fm["r_" + law].values, fm.se.values)}
        for (mo, k), g in fm.groupby(["model", "kind"]):
            out["tests"][law]["%s|%s" % (mo, k)] = tests(g["r_" + law].values, g.se.values)
        for k, g in fm.groupby("kind"):
            out["tests"][law][k] = tests(g["r_" + law].values, g.se.values)

    # which law predicts better: paired comparison of absolute errors
    out["H_vs_A_wilcoxon_p"] = float(stats.wilcoxon(np.abs(fm.r_H), np.abs(fm.r_A)).pvalue)
    out["H_vs_G_wilcoxon_p"] = float(stats.wilcoxon(np.abs(fm.r_H), np.abs(fm.r_G)).pvalue)
    out["H_better_share"] = float(np.mean(np.abs(fm.r_H) < np.abs(fm.r_A)))

    # calibration regression log C_obs = a + b log H (H0: a=0, b=1), cluster-robust by model
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools import add_constant
    X = add_constant(np.log(fm.H.values))
    y = np.log(fm.c_obs.values)
    ols = OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(fm.model)[0]})
    ols_plain = OLS(y, X).fit()
    ftest = ols_plain.f_test("const = 0, x1 = 1")
    out["calibration"] = dict(a=float(ols.params[0]), b=float(ols.params[1]),
                              b_ci=ols.conf_int()[1].tolist(), a_ci=ols.conf_int()[0].tolist(),
                              r2=float(ols_plain.rsquared), F=float(ftest.fvalue), p_F=float(ftest.pvalue))

    # profile least squares for the power-mean exponent q (group offsets profiled out)
    grid = np.linspace(-3, 3, 601)
    sse = []
    for q in grid:
        r = np.array([np.log(c) - power_mean_log(mu, p, q) for c, mu, p in zip(fm.c_obs, fm.mu, fm.p)])
        res = r - fm.assign(r=r).groupby(["model", "kind"]).r.transform("mean").values
        sse.append(np.sum(res ** 2))
    sse = np.array(sse)
    n, k = len(fm), fm.groupby(["model", "kind"]).ngroups + 1
    lr = n * np.log(sse / sse.min())
    inside = grid[lr <= stats.chi2.ppf(0.95, 1)]
    out["q_profile"] = dict(q_hat=float(grid[sse.argmin()]), ci95=[float(inside.min()), float(inside.max())],
                            grid=grid[::10].tolist(), lr=lr[::10].tolist(),
                            p_q_minus1=float(1 - stats.chi2.cdf(lr[np.argmin(abs(grid + 1))], 1)),
                            p_q_0=float(1 - stats.chi2.cdf(lr[np.argmin(abs(grid))], 1)),
                            p_q_plus1=float(1 - stats.chi2.cdf(lr[np.argmin(abs(grid - 1))], 1)))

    # boundedness
    def cp(kk, nn):
        lo = stats.beta.ppf(0.025, kk, nn - kk + 1) if kk > 0 else 0.0
        hi = stats.beta.ppf(0.975, kk + 1, nn - kk) if kk < nn else 1.0
        return [float(lo), float(hi)]
    out["bounds"] = dict(minmax=[int(fm.in_minmax.sum()), len(fm), cp(fm.in_minmax.sum(), len(fm))],
                         HA=[int(fm.in_HA.sum()), len(fm), cp(fm.in_HA.sum(), len(fm))],
                         above_A=int((fm.c_obs > fm.A).sum()), below_H=int((fm.c_obs < fm.H).sum()))

    # what drives deviations from harmonic additivity
    rho, prho = stats.spearmanr(fm.hetero, fm.r_H)
    mw = stats.mannwhitneyu(fm.r_H[fm.has_long_out], fm.r_H[~fm.has_long_out])
    kw = stats.kruskal(*[g.r_H.values for _, g in fm.groupby("kind")])
    fam = {f: tests(g.r_H.values, g.se.values) for f, g in fm.groupby("family")}
    kwf = stats.kruskal(*[g.r_H.values for _, g in fm.groupby("family")])
    out["drivers"] = dict(spearman_hetero=[float(rho), float(prho)], family=fam,
                          family_kw_p=float(kwf.pvalue),
                          long_out_mw_p=float(mw.pvalue), kind_kw_p=float(kw.pvalue))
    return fm, out


# --------------------------------------------------------------------- bayesian
def split_rhat(x):
    """Split-R-hat of draws shaped (chain, draw, ...), maximised over the trailing dims."""
    c, n = x.shape[:2]
    h = n // 2
    x = np.concatenate([x[:, :h], x[:, h:2 * h]], axis=0).reshape(2 * c, h, -1)
    w = x.var(axis=1, ddof=1).mean(axis=0)
    b = h * x.mean(axis=1).var(axis=0, ddof=1)
    return float(np.nanmax(np.sqrt(((h - 1) / h * w + b / h) / w)))


def bayesian(d, units, draws=1500, tune=1500, chains=4, debug=False):
    import pymc as pm
    import pytensor.tensor as pt
    import arviz as az

    mixes = units[units.is_mix].reset_index(drop=True)
    need = {(m.model, m.kind, k) for _, m in mixes.iterrows() for k in m.props}
    pure = units[(~units.is_mix) & units.apply(lambda r: (r.model, r.kind, r.cell) in need, axis=1)]
    pure = pure.reset_index(drop=True)
    cells = sorted(need)
    cidx = {c: i for i, c in enumerate(cells)}
    groups = sorted(set(zip(mixes.model, mixes.kind)))
    gidx = {g: i for i, g in enumerate(groups)}
    kinds = ["MIT", "MST"]

    nP, nM, nC = len(pure), len(mixes), len(cells)
    pure_cell = np.array([cidx[(r.model, r.kind, r.cell)] for _, r in pure.iterrows()])
    pure_kind = np.array([kinds.index(k) for k in pure.kind])
    mix_group = np.array([gidx[(m.model, m.kind)] for _, m in mixes.iterrows()])
    mix_kind = np.array([kinds.index(k) for k in mixes.kind])
    # component matrix: W[m, c] = proportion of cell c in mix m
    W = np.zeros((nM, nC))
    for i, m in mixes.iterrows():
        for k, p in m.props.items():
            W[i, cidx[(m.model, m.kind, k)]] = p
    mask = W > 0
    logW = np.log(np.where(mask, W, 1.0))

    mu_init = np.array([np.log(pure.c_hat[pure_cell == i]).mean() for i in range(nC)])
    uid = {u: i for i, u in enumerate(pure.unit)}
    uid.update({u: nP + i for i, u in enumerate(mixes.unit)})
    obs = d[d.unit.isin(uid)]
    o_unit = obs.unit.map(uid).values
    o_logr = np.log(obs.REQ_MIN.values)
    o_y = obs.EVALUATION.values.astype(int)
    o_kind = np.array([kinds.index(k) for k in obs.kind])

    c0 = float(np.log(500))  # centring constant keeps exp() in range for any plausible q

    def log_power_mean(mu, q):
        # log M_q = log(sum_i p_i C_i^q) / q, written densely (W has zeros for absent cells)
        return pt.log(pt.dot(W, pt.exp(q * (mu - c0)))) / q + c0

    def build(q_mode):
        with pm.Model() as model:
            mu = pm.Normal("mu", mu=np.log(500), sigma=3, shape=nC, initval=mu_init)
            sd_rep = pm.HalfNormal("sd_rep", 0.3, shape=2)
            sd_mix = pm.HalfNormal("sd_mix", 0.3, shape=2)
            # width of the pass/fail transition (log scale); log-normal keeps it off 0, where
            # near-separable pass/fail data would otherwise create a funnel
            s = pm.LogNormal("s", np.log(0.05), 0.5, shape=2)
            delta0 = pm.Normal("delta0", 0, 0.5)
            sd_delta = pm.HalfNormal("sd_delta", 0.2)
            zg = pm.Normal("zg", 0, 1, shape=len(groups))
            delta = pm.Deterministic("delta", delta0 + sd_delta * zg)
            if q_mode == "free":
                q = pm.Normal("q", 0, 2)
                q = pt.switch(pt.abs(q) < 1e-4, 1e-4, q)
            else:
                q = pt.as_tensor_variable(float(q_mode))
            zp = pm.Normal("zp", 0, 1, shape=nP)
            zm = pm.Normal("zm", 0, 1, shape=nM)
            theta_p = mu[pure_cell] + sd_rep[pure_kind] * zp
            pred = log_power_mean(mu, q)
            theta_m = pred + delta[mix_group] + sd_mix[mix_kind] * zm
            pm.Deterministic("theta_m", theta_m)
            pm.Deterministic("logH", log_power_mean(mu, -1.0))
            pm.Deterministic("logA", log_power_mean(mu, 1.0))
            pm.Deterministic("logmin", pt.min(pt.switch(mask, mu[None, :], np.inf), axis=1))
            pm.Deterministic("logmax", pt.max(pt.switch(mask, mu[None, :], -np.inf), axis=1))
            theta = pt.concatenate([theta_p, theta_m])
            # Bernoulli-logit written as a stable softplus: pytensor's log1pexp gradient turns
            # NaN at the very large logits produced by the low-capacity cells
            x = -(2 * o_y - 1) * (theta[o_unit] - o_logr) / s[o_kind]
            pm.Potential("y", -pt.sum(pt.maximum(x, 0) + pt.log1p(pt.exp(-pt.abs(x)))))
        return model

    if debug:
        return build, locals()
    fits, diag = {}, {}
    for name, qm in [("free", "free"), ("harmonic", -1.0), ("geometric", 1e-4), ("arithmetic", 1.0)]:
        with build(qm):
            idata = pm.sample(draws=draws, tune=tune, chains=chains, target_accept=0.95,
                              random_seed=20261005, progressbar=False)
        fits[name] = idata
        diag[name] = dict(divergences=int(idata.sample_stats["diverging"].values.sum()),
                          max_rhat=max(split_rhat(idata.posterior[v].values)
                                       for v in ["mu", "delta", "sd_mix", "sd_rep", "s", "theta_m"]))
        print(name, diag[name], file=sys.stderr)

    # Predictive score of each law: how well does "law + group bias + residual scale" predict
    # the pass/fail outcomes of a mix run? The run's own residual is integrated out (drawn from
    # its N(0, sd_mix) prior) so a law cannot hide its misfit in that residual; the score is the
    # Monte-Carlo log predictive density per mix run, summed over runs.
    mix_obs = obs.unit.map(uid).values - nP
    sel = mix_obs >= 0
    mo, lr_, yk, kk = mix_obs[sel], o_logr[sel], o_y[sel], o_kind[sel]
    rng = np.random.default_rng(7)
    loo = {}
    for name, idata in fits.items():
        post_ = idata.posterior
        S = post_.sizes["chain"] * post_.sizes["draw"]
        take = rng.choice(S, size=min(S, 1000), replace=False)
        th = post_["theta_m"].values.reshape(S, nM)[take]
        zm_ = post_["zm"].values.reshape(S, nM)[take]
        sdm = post_["sd_mix"].values.reshape(S, 2)[take][:, mix_kind]
        sk = post_["s"].values.reshape(S, 2)[take]
        center = th - sdm * zm_  # law prediction + group bias, residual removed
        lls = []
        for _ in range(8):
            t_new = center + sdm * rng.standard_normal(center.shape)
            x = -(2 * yk - 1) * (t_new[:, mo] - lr_) / sk[:, kk]
            ll_obs = -(np.maximum(x, 0) + np.log1p(np.exp(-np.abs(x))))
            ll = np.zeros((len(take), nM))
            np.add.at(ll.T, mo, ll_obs.T)
            lls.append(ll)
        ll = np.concatenate(lls)
        lpd = np.log(np.mean(np.exp(ll - ll.max(0)), axis=0)) + ll.max(0)
        loo[name] = dict(elpd=float(lpd.sum()), pointwise=lpd)
    base = loo["harmonic"]["pointwise"]
    for name in loo:
        diff = loo[name]["pointwise"] - base
        loo[name]["diff_vs_harmonic"] = float(diff.sum())
        loo[name]["diff_se"] = float(np.sqrt(len(diff)) * diff.std(ddof=1))
        del loo[name]["pointwise"]
    post = fits["harmonic"].posterior
    th = post["theta_m"].stack(s=("chain", "draw")).values  # (nM, S)
    H = post["logH"].stack(s=("chain", "draw")).values
    A = post["logA"].stack(s=("chain", "draw")).values
    lmin = post["logmin"].stack(s=("chain", "draw")).values
    lmax = post["logmax"].stack(s=("chain", "draw")).values
    rH = th - H
    rA = th - A

    def hdi(x, a=0.9):
        lo, hi = np.quantile(x, [(1 - a) / 2, 1 - (1 - a) / 2])
        return [float(lo), float(hi)]

    per_mix = []
    for i, m in mixes.iterrows():
        per_mix.append(dict(unit=m.unit, model=m.model, kind=m.kind, label=m.label,
                            rH=float(np.median(rH[i])), rH_ci=hdi(rH[i]),
                            rA=float(np.median(rA[i])), rA_ci=hdi(rA[i]),
                            theta=float(np.median(th[i])), theta_ci=hdi(th[i]),
                            H=float(np.median(H[i])), H_ci=hdi(H[i]),
                            A=float(np.median(A[i])), lmin=float(np.median(lmin[i])),
                            lmax=float(np.median(lmax[i])),
                            p_rope=float(np.mean(np.abs(rH[i]) < ROPE)),
                            p_minmax=float(np.mean((th[i] >= lmin[i]) & (th[i] <= lmax[i]))),
                            p_HA=float(np.mean((th[i] >= H[i]) & (th[i] <= A[i]))),
                            p_above_H=float(np.mean(rH[i] > 0))))

    def summ(x):
        x = np.asarray(x).ravel()
        return dict(median=float(np.median(x)), ci90=hdi(x), ci95=hdi(x, 0.95),
                    p_gt0=float(np.mean(x > 0)), p_rope=float(np.mean(np.abs(x) < ROPE)),
                    p_rope5=float(np.mean(np.abs(x) < ROPE_TIGHT)),
                    hist=np.histogram(x, bins=60)[0].tolist(),
                    edges=np.histogram(x, bins=60)[1].tolist())

    res = {"groups": ["%s|%s" % g for g in groups], "per_mix": per_mix, "diagnostics": diag, "loo": loo}
    for law, idata in fits.items():
        p = {v: idata.posterior[v] for v in ["delta0", "delta", "sd_mix", "sd_rep", "s"]
             + (["q"] if law == "free" else [])}
        p = type("P", (), p)
        res[law] = dict(delta0=summ(p.delta0.values),
                        delta={"%s|%s" % g: summ(p.delta.values[..., j]) for j, g in enumerate(groups)},
                        sd_mix={k: summ(p.sd_mix.values[..., j]) for j, k in enumerate(kinds)},
                        sd_rep={k: summ(p.sd_rep.values[..., j]) for j, k in enumerate(kinds)},
                        s={k: summ(p.s.values[..., j]) for j, k in enumerate(kinds)})
        if law == "free":
            res[law]["q"] = summ(p.q.values)
            res[law]["q"]["p_lt0"] = float(np.mean(p.q.values < 0))
            res[law]["q"]["p_near_harmonic"] = float(np.mean(np.abs(p.q.values + 1) < 0.5))
    # pooled share of mixes inside each bound (posterior of the proportion)
    res["share_minmax"] = summ(((th >= lmin) & (th <= lmax)).mean(axis=0))
    res["share_HA"] = summ(((th >= H) & (th <= A)).mean(axis=0))
    res["share_rope"] = summ((np.abs(rH) < ROPE).mean(axis=0))
    # posterior cell capacities
    mu_post = fits["harmonic"].posterior["mu"].stack(s=("chain", "draw")).values
    res["cells"] = [dict(model=c[0], kind=c[1], cell=c[2], cap=float(np.exp(np.median(mu_post[i]))),
                         ci=[float(np.exp(v)) for v in hdi(mu_post[i])]) for i, c in enumerate(cells)]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="analysis_out")
    ap.add_argument("--skip-bayes", action="store_true")
    ap.add_argument("--draws", type=int, default=1500)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    d = load()
    units = build_units(d)
    units.to_pickle(out / "units.pkl")
    fm, freq = frequentist(units)
    fm.to_csv(out / "mix_frequentist.csv", index=False)
    res = {"freq": freq, "n_rows": len(d), "n_units": len(units),
           "non_monotone_pure": int((~units[~units.is_mix].monotone).sum()),
           "mix_rows": fm.drop(columns=["mu", "p"]).to_dict("records")}
    if not args.skip_bayes:
        res["bayes"] = bayesian(d, units, draws=args.draws, tune=args.draws)
    (out / "results.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in freq.items() if k not in ("cells",)}, indent=1, default=float))


if __name__ == "__main__":
    main()
