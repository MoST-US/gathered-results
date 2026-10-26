"""Burst factor of each request class: how far a 2-minute burst can exceed the sustainable rate.

MoST measures two capacities per request class r (SCALE paper, Sec. 4):
  * MST_r, the Maximum Sustainable Throughput over 30-minute runs, and
  * MIT_r, the Maximum Instantaneous Throughput over 2-minute runs,
both in requests per minute. The burst factor is their ratio

    B_r = MIT_r / MST_r,

so a client may send bursts up to B_r times the sustainable rate of class r. SCALE exposes a single
currency Q based on the sustainable capacity (SK_r = SK_max / MST_r) and keeps the instantaneous
capacity (IK_r = IK_max / MIT_r) as a background safety threshold. Both K systems price classes
identically only if B_r is the same for every class (IK_r / SK_r = (IK_max / SK_max) / B_r), so a
constant burst factor is what makes one currency sufficient. This module estimates B_r for every
cell and model, tests whether it is constant, and tests whether the burst factor of a mix follows
from those of its classes.

Used by additivity_analysis.py (frequentist part always; Bayesian part unless --skip-bayes).
"""
import numpy as np
import pandas as pd
from scipy import stats

BAND = np.log(1.15)  # a class is "on the model's burst factor" if within +-15 % of it
EQUIV = np.log(1.10)  # equivalence margin between models (TOST)
HEAVY_OUT = "1000-1500"


def _cell_capacities(units):
    pure = units[~units.is_mix].copy()
    pure["logc"] = np.log(pure.c_hat)
    g = pure.groupby(["model", "kind", "cell"]).logc.agg(["mean", "std", "count"]).reset_index()
    pooled = {k: float(np.sqrt(np.nanmean(x["std"] ** 2))) for k, x in g.groupby("kind")}
    g["se"] = [max(s if n > 1 and np.isfinite(s) else pooled[k], pooled[k]) / np.sqrt(n)
               for s, n, k in zip(g["std"], g["count"], g["kind"])]
    return g, pooled


def frequentist(units, fm):
    """Per-cell burst factors, their constancy, portability across models and mixes."""
    g, pooled = _cell_capacities(units)
    w = g.pivot_table(index=["model", "cell"], columns="kind", values=["mean", "se"])
    cells = pd.DataFrame({
        "model": [i[0] for i in w.index], "cell": [i[1] for i in w.index],
        "mit": np.exp(w["mean"]["MIT"].values), "mst": np.exp(w["mean"]["MST"].values),
        "logB": (w["mean"]["MIT"] - w["mean"]["MST"]).values,
        "se": np.sqrt(w["se"]["MIT"] ** 2 + w["se"]["MST"] ** 2).values,
    })
    cells["inp"] = cells.cell.str.split("_").str[0]
    cells["out"] = cells.cell.str.split("_").str[1]
    cells["B"] = np.exp(cells.logB)
    med = cells.groupby("model").logB.transform("median")
    cells["dev"] = cells.logB - med  # departure from the model's typical burst factor
    cells["on_band"] = cells.dev.abs() < BAND

    out = {"pooled_replicate_sd": pooled, "band": float(BAND)}
    per_model = {}
    for m, x in cells.groupby("model"):
        q1, q3 = np.quantile(x.B, [0.25, 0.75])
        per_model[m] = dict(n=len(x), median=float(np.exp(x.logB.median())), gmean=float(np.exp(x.logB.mean())),
                            q1=float(q1), q3=float(q3), min=float(x.B.min()), max=float(x.B.max()),
                            on_band=float(x.on_band.mean()), sd_log=float(x.logB.std()))
    out["per_model"] = per_model
    allc = cells.logB
    out["overall"] = dict(n=len(cells), median=float(np.exp(allc.median())), gmean=float(np.exp(allc.mean())),
                          q1=float(np.exp(np.quantile(allc, 0.25))), q3=float(np.exp(np.quantile(allc, 0.75))),
                          on_band=float(cells.on_band.mean()),
                          mad_log=float(stats.median_abs_deviation(allc)))

    # what drives the burst factor: two-way layout of input and output ranges plus model
    from statsmodels.formula.api import ols
    from statsmodels.stats.anova import anova_lm
    fit = ols("logB ~ C(model) + C(inp) + C(out)", data=cells).fit()
    an = anova_lm(fit, typ=2)
    out["anova"] = {k: dict(F=float(r.F), p=float(r["PR(>F)"]), df=float(r.df))
                    for k, r in an.iterrows() if k != "Residual"}
    out["anova_r2"] = float(fit.rsquared)
    # same layout without the two outlying Gemma cells (see the MST SLA discussion)
    robust = cells[~((cells.model == "Gemma-7B") & (cells.out == HEAVY_OUT) & cells.inp.isin(["300-600", "600-1000"]))]
    fit_r = ols("logB ~ C(model) + C(inp) + C(out)", data=robust).fit()
    an_r = anova_lm(fit_r, typ=2)
    out["anova_robust"] = {k: dict(F=float(r.F), p=float(r["PR(>F)"]), df=float(r.df))
                           for k, r in an_r.iterrows() if k != "Residual"}
    # output-length effect: short answers (1-100 tokens) versus the rest
    short = cells.out == "1-100"
    out["short_output"] = dict(B_short=float(np.exp(cells.logB[short].mean())),
                               B_rest=float(np.exp(cells.logB[~short].mean())),
                               ratio=float(np.exp(cells.logB[short].mean() - cells.logB[~short].mean())),
                               p_mw=float(stats.mannwhitneyu(cells.logB[short], cells.logB[~short]).pvalue))
    out["by_output"] = {o: float(np.exp(x.logB.mean())) for o, x in cells.groupby("out")}
    out["by_input"] = {i: float(np.exp(x.logB.mean())) for i, x in cells.groupby("inp")}

    # portability: are the models' typical burst factors equivalent? (medians over cells; paired by
    # cell, Wilcoxon for difference, TOST on the paired log differences for equivalence)
    models = sorted(cells.model.unique())
    piv = cells.pivot(index="cell", columns="model", values="logB")
    pairs = []
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            dlt = (piv[a] - piv[b]).dropna()
            n, mu, sd = len(dlt), float(dlt.median()), float(dlt.std(ddof=1))
            m_ = float(dlt.mean())
            tl = (m_ + EQUIV) / (sd / np.sqrt(n))
            tu = (m_ - EQUIV) / (sd / np.sqrt(n))
            p_tost = float(max(1 - stats.t.cdf(tl, n - 1), stats.t.cdf(tu, n - 1)))
            rho, prho = stats.spearmanr(piv[a], piv[b])
            pairs.append(dict(a=a, b=b, median_ratio=float(np.exp(mu)), mean_ratio=float(np.exp(m_)),
                              p_wilcoxon=float(stats.wilcoxon(dlt).pvalue), p_tost=p_tost,
                              spearman=float(rho), p_spearman=float(prho)))
    out["portability"] = pairs

    # mixes measured with the same composition in both tests (equal-count designs)
    mix = fm.copy()
    mix["compkey"] = mix.comps.map(lambda c: "|".join(sorted(c)) if isinstance(c, list) else c)
    mix["pkey"] = [tuple(sorted((ci, round(float(pi), 2)) for ci, pi in zip(c, p)))
                   for c, p in zip(mix.comps, mix.p)]
    rows = []
    for (m, ck), x in mix.groupby(["model", "compkey"]):
        a, b = x[x.kind == "MIT"], x[x.kind == "MST"]
        if a.empty or b.empty:
            continue
        for pk in set(a.pkey) & set(b.pkey):
            aa, bb = a[a.pkey == pk], b[b.pkey == pk]
            obs = float(np.log(aa.c_obs).mean() - np.log(bb.c_obs).mean())
            pred = float(np.log(aa.H).mean() - np.log(bb.H).mean())
            rows.append(dict(model=m, label=aa.label.iloc[0], runs_mit=len(aa), runs_mst=len(bb),
                             logB_obs=obs, logB_pred=pred, heavy="600-1000_1000-1500" in ck))
    mb = pd.DataFrame(rows)
    if len(mb):
        err = mb.logB_obs - mb.logB_pred
        light = mb[~mb.heavy]
        el = light.logB_obs - light.logB_pred
        out["mixes"] = dict(n=len(mb), mean_err=float(err.mean()), mae=float(err.abs().mean()),
                            median_err=float(err.median()), within15=float(np.mean(err.abs() < BAND)),
                            n_light=len(light), mae_light=float(el.abs().mean()) if len(el) else None,
                            within15_light=float(np.mean(el.abs() < BAND)) if len(el) else None,
                            B_obs_median=float(np.exp(mb.logB_obs.median())),
                            rows=mb.to_dict("records"))
    else:
        out["mixes"] = dict(n=0, rows=[])

    # SCALE implication: pricing a burst with the sustainable currency Q mis-states its
    # instantaneous load by B_ref / B_r for class r (B_ref = the model's typical burst factor)
    cells["burst_misprice"] = np.exp(-cells.dev)
    out["misprice"] = dict(within15=float(cells.on_band.mean()),
                           max_over=float(cells.burst_misprice.max()),
                           max_under=float(cells.burst_misprice.min()))
    out["cells"] = cells.drop(columns=["burst_misprice"]).to_dict("records")
    return out


def bayesian(d, units, draws=600, tune=600, chains=4, seed=20261005):
    """Pure-cell capacities of every cell in both tests (pure runs only), and the posterior of
    every burst factor log B = mu_MIT - mu_MST, of each model's median burst factor and of the
    share of cells within +-15 % of it."""
    import pymc as pm
    import pytensor.tensor as pt

    pure = units[~units.is_mix].reset_index(drop=True)
    keys = sorted(set(zip(pure.model, pure.kind, pure.cell)))
    kidx = {k: i for i, k in enumerate(keys)}
    kinds = ["MIT", "MST"]
    pc = np.array([kidx[(m, k, c)] for m, k, c in zip(pure.model, pure.kind, pure.cell)])
    pk = np.array([kinds.index(k) for k in pure.kind])
    uid = {u: i for i, u in enumerate(pure.unit)}
    obs = d[d.unit.isin(uid)]
    ou = obs.unit.map(uid).values
    lr = np.log(obs.REQ_MIN.values)
    y = obs.EVALUATION.values.astype(int)
    ok = np.array([kinds.index(k) for k in obs.kind])
    mu0 = np.array([np.log(pure.c_hat[pc == i]).mean() for i in range(len(keys))])

    with pm.Model():
        mu = pm.Normal("mu", np.log(500), 3, shape=len(keys), initval=mu0)
        sd_rep = pm.HalfNormal("sd_rep", 0.3, shape=2)
        s = pm.LogNormal("s", np.log(0.05), 0.5, shape=2)
        z = pm.Normal("z", 0, 1, shape=len(pure))
        th = mu[pc] + sd_rep[pk] * z
        x = -(2 * y - 1) * (th[ou] - lr) / s[ok]
        pm.Potential("y", -pt.sum(pt.maximum(x, 0) + pt.log1p(pt.exp(-pt.abs(x)))))
        idata = pm.sample(draws=draws, tune=tune, chains=chains, target_accept=0.95,
                          random_seed=seed, progressbar=False)
    mu_d = idata.posterior["mu"].values.reshape(-1, len(keys))
    div = int(idata.sample_stats["diverging"].values.sum())

    def q(x, a):
        return [float(v) for v in np.quantile(x, [(1 - a) / 2, 1 - (1 - a) / 2])]

    models = sorted({k[0] for k in keys})
    cells = sorted({k[2] for k in keys})
    res_cells, per_model = [], {}
    for m in models:
        lb = np.stack([mu_d[:, kidx[(m, "MIT", c)]] - mu_d[:, kidx[(m, "MST", c)]] for c in cells], axis=1)
        medB = np.median(lb, axis=1)  # model's typical burst factor, per draw
        on = (np.abs(lb - medB[:, None]) < BAND).mean(axis=1)
        per_model[m] = dict(median=float(np.exp(np.median(medB))), ci95=[float(np.exp(v)) for v in q(medB, .95)],
                            on_band=float(np.median(on)), on_band_ci95=q(on, .95))
        for j, c in enumerate(cells):
            res_cells.append(dict(model=m, cell=c, B=float(np.exp(np.median(lb[:, j]))),
                                  ci95=[float(np.exp(v)) for v in q(lb[:, j], .95)],
                                  p_on_band=float(np.mean(np.abs(lb[:, j] - medB) < BAND))))
    # pairwise equivalence of the models' typical burst factors
    meds = {m: np.median(np.stack([mu_d[:, kidx[(m, "MIT", c)]] - mu_d[:, kidx[(m, "MST", c)]]
                                   for c in cells], 1), 1) for m in models}
    pairs = []
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            dd = meds[a] - meds[b]
            pairs.append(dict(a=a, b=b, ratio=float(np.exp(np.median(dd))),
                              ci95=[float(np.exp(v)) for v in q(dd, .95)],
                              p_equiv=float(np.mean(np.abs(dd) < EQUIV))))
    from additivity_analysis import split_rhat
    return dict(per_model=per_model, cells=res_cells, pairs=pairs,
                diagnostics=dict(divergences=div, max_rhat=split_rhat(idata.posterior["mu"].values)))
