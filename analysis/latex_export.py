"""Export the additivity and burst-factor results as LaTeX assets for the SCALE paper.

Usage: python analysis/latex_export.py [--results analysis/output] [--out analysis/latex]

Writes
  macros.tex                 \\newcommand constants with every number quoted in the text
  tables/*.tex               booktabs tables (\\input them inside a table environment)
  figures/*.pdf              vector figures sized for LNCS (12.2 cm text width)
  section_additivity_burst.tex   draft of the evaluation subsections, written with the macros
  preview.tex                compilable LNCS document that pulls everything together
  derived.json               design-level statistics computed here (also quoted by the macros)

Needs: pandas numpy scipy statsmodels matplotlib
"""
import argparse
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
HEAVY = "600-1000_1000-1500"
TEN = np.log(1.1)
MODELS = ["DeepSeek-R1-Qwen-7B", "Gemma-7B", "Llama-3.1-8B"]
MODEL_TEX = {"DeepSeek-R1-Qwen-7B": "DeepSeek-R1-Distill-Qwen-7B", "Gemma-7B": "Gemma-7B",
             "Llama-3.1-8B": "Llama-3.1-8B-Instruct"}
MODEL_MACRO = {"DeepSeek-R1-Qwen-7B": "DeepSeek", "Gemma-7B": "Gemma", "Llama-3.1-8B": "Llama"}
COLORS = {"DeepSeek-R1-Qwen-7B": "#2a78d6", "Gemma-7B": "#eb6834", "Llama-3.1-8B": "#1baf7a"}
LIGHT, HEAVYC = "#2a78d6", "#eb6834"
IN_RANGES = ["1-100", "100-300", "300-600", "600-1000"]
OUT_RANGES = ["1-100", "100-300", "300-600", "600-1000", "1000-1500"]


# ------------------------------------------------------------------------------ formatting
def pct(logratio, d=1, sign=True):
    """Log-ratio -> signed percentage string for LaTeX (math minus)."""
    v = 100 * (np.exp(logratio) - 1)
    s = f"{abs(v):.{d}f}"
    if sign:
        s = ("+" if v >= 0 else r"\ensuremath{-}") + s
    return s + r"\,\%"


def num(x, d=2, sign=False):
    s = f"{abs(x):.{d}f}"
    if x < 0:
        return r"\ensuremath{-}" + s
    return ("+" if sign and x > 0 else "") + s


def share(x, d=0):
    return f"{100 * x:.{d}f}" + r"\,\%"


def pval(p):
    if p < 1e-4:
        m, e = f"{p:.0e}".split("e")
        return r"\ensuremath{" + m + r"\times 10^{" + str(int(e)) + "}}"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def big(n):
    return f"{int(round(n)):,}".replace(",", "{,}")


# ------------------------------------------------------------------------ design-level stats
def design_frame(fm):
    fm = fm.copy()
    fm["heavy"] = fm.label.str.contains(HEAVY)
    if "design" not in fm:
        fm["design"] = fm.model + "|" + fm.kind + "|" + fm.label
    fd = fm.groupby("design").agg(model=("model", "first"), kind=("kind", "first"),
                                  heavy=("heavy", "first"), family=("family", "first"),
                                  runs=("unit", "size"), r=("r_H", "mean"), rA=("r_A", "mean"),
                                  rG=("r_G", "mean")).reset_index()
    return fm, fd


def derived_stats(fm, fd):
    from statsmodels.formula.api import ols
    from statsmodels.stats.anova import anova_lm
    out = {}

    def summ(x):
        return dict(n=int(len(x)), mean=float(x.mean()), mae=float(x.abs().mean()), sd=float(x.std()),
                    within10=float(np.mean(x.abs() < TEN)))
    out["kind"] = {k: summ(g.r) for k, g in fd.groupby("kind")}
    out["kind_heavy"] = {f"{k}|{'heavy' if h else 'light'}": summ(g.r) for (k, h), g in fd.groupby(["kind", "heavy"])}
    a, b = fd[fd.kind == "MIT"].r, fd[fd.kind == "MST"].r
    out["mit_vs_mst"] = dict(p_mean=float(stats.mannwhitneyu(a, b).pvalue),
                             p_levene=float(stats.levene(a, b).pvalue),
                             p_abs=float(stats.mannwhitneyu(a.abs(), b.abs()).pvalue))
    la, lb = fd[(fd.kind == "MIT") & ~fd.heavy].r, fd[(fd.kind == "MST") & ~fd.heavy].r
    out["mit_vs_mst_light"] = dict(p_levene=float(stats.levene(la, lb).pvalue))
    an = anova_lm(ols("r ~ C(model) + C(kind) + heavy", data=fd).fit(), typ=2)
    out["anova"] = {k: dict(F=float(r.F), p=float(r["PR(>F)"])) for k, r in an.iterrows() if k != "Residual"}
    an_l = anova_lm(ols("r ~ C(model) + C(kind)", data=fd[~fd.heavy]).fit(), typ=2)
    out["anova_light"] = {k: dict(F=float(r.F), p=float(r["PR(>F)"])) for k, r in an_l.iterrows() if k != "Residual"}
    out["model_kind_heavy"] = {f"{m}|{k}|{'heavy' if h else 'light'}": dict(n=int(len(g)), mean=float(g.r.mean()))
                               for (m, k, h), g in fd.groupby(["model", "kind", "heavy"])}
    out["laws"] = {law: dict(mean=float(fd[c].mean()), rmse=float(np.sqrt(np.mean(fd[c] ** 2))),
                             within10=float(np.mean(fd[c].abs() < TEN)))
                   for law, c in [("harmonic", "r"), ("geometric", "rG"), ("arithmetic", "rA")]}
    fam = {f: summ(g.r) for f, g in fd.groupby("family") if f != "single-type"}
    out["family"] = fam
    groups = [g.r.values for f, g in fd.groupby("family") if f != "single-type"]
    out["family_kw_p"] = float(stats.kruskal(*groups).pvalue)
    return out


# ------------------------------------------------------------------------------- macros
def macros(R, D):
    f, b, B = R["freq"], R.get("bayes"), R["burst"]
    BB = R.get("burst_bayes")
    M = {}
    M["NEvaluations"] = big(R["n_rows"])
    M["NMixRuns"] = big(f["n_mix_runs"])
    M["NDesigns"] = big(f["n_design_units"])
    M["NRepeatRuns"] = big(sum(v["runs"] for v in f["mix_replicates"].values()))
    M["NRepeatDesigns"] = big(sum(v["designs"] for v in f["mix_replicates"].values()))
    M["NDuplicates"] = big(R["duplicate_units_removed"])
    M["NPureRuns"] = big(R["n_units"] - f["n_mix_runs"])
    # additivity law
    qp = f["q_profile"]
    M["QHatFreq"] = num(qp["q_hat"], 2)
    M["QFreqLo"], M["QFreqHi"] = num(qp["ci95"][0], 2), num(qp["ci95"][1], 2)
    M["HarmonicWinShare"] = share(f["H_better_share"])
    M["CalibSlope"] = num(f["calibration"]["b"], 2)
    M["CalibSlopeLo"], M["CalibSlopeHi"] = num(f["calibration"]["b_ci"][0], 2), num(f["calibration"]["b_ci"][1], 2)
    M["CalibRsq"] = num(f["calibration"]["r2"], 2)
    t = f["tests"]["H"]["all"]
    M["BiasFreq"] = pct(t["mean"])
    M["BiasFreqLo"], M["BiasFreqHi"] = pct(t["ci95"][0]), pct(t["ci95"][1])
    M["BiasTostP"] = pval(t["p_tost"])
    M["ArithMeanErr"] = pct(D["laws"]["arithmetic"]["mean"], 0)
    M["GeomMeanErr"] = pct(D["laws"]["geometric"]["mean"], 0)
    M["BoundsIn"], M["BoundsN"] = big(f["bounds"]["minmax"][0]), big(f["bounds"]["minmax"][1])
    M["BoundsShare"] = share(f["bounds"]["minmax"][0] / f["bounds"]["minmax"][1], 1)
    M["AboveArith"] = big(f["bounds"]["above_A"])
    if b:
        q = b["free"]["q"]
        M["QHatBayes"] = num(q["median"], 2)
        M["QBayesLo"], M["QBayesHi"] = num(q["ci95"][0], 2), num(q["ci95"][1], 2)
        d0 = b["harmonic"]["delta0"]
        M["BiasBayes"] = pct(d0["median"])
        M["BiasBayesLo"], M["BiasBayesHi"] = pct(d0["ci90"][0]), pct(d0["ci90"][1])
        M["BiasBayesPRope"] = share(d0["p_rope"])
        L = b["loo"]
        for k, n in [("free", "Free"), ("geometric", "Geom"), ("arithmetic", "Arith")]:
            M[f"Pred{n}"] = num(L[k]["diff_vs_harmonic"], 1, sign=True)
            M[f"Pred{n}SE"] = num(L[k]["diff_se"], 1)
        H = b["harmonic"]
        for k in ["MIT", "MST"]:
            M[f"SdMix{k}"] = share(np.exp(H["sd_mix"][k]["median"]) - 1)
            M[f"SdRun{k}"] = share(np.exp(H["sd_run"][k]["median"]) - 1, 1)
            M[f"SdRep{k}"] = share(np.exp(H["sd_rep"][k]["median"]) - 1, 1)
            band = np.exp(1.645 * np.hypot(np.hypot(H["sd_mix"][k]["median"], H["sd_run"][k]["median"]), d0["median"])) - 1
            M[f"Band{k}"] = r"\ensuremath{\pm}" + f"{100 * band:.0f}" + r"\,\%"
        for m in MODELS:
            for k in ["MIT", "MST"]:
                M[f"Bias{MODEL_MACRO[m]}{k}"] = pct(H["delta"][f"{m}|{k}"]["median"])
        M["BayesDraws"] = "600"
        dg = b["diagnostics"]
        M["MaxRhat"] = num(max(dg["harmonic"]["max_rhat"], dg["free"]["max_rhat"], dg["pure_cells"]["max_rhat"]), 2)
    # MIT vs MST and heavy classes (design level)
    for k in ["MIT", "MST"]:
        M[f"Mae{k}"] = share(np.exp(D["kind"][k]["mae"]) - 1)
        M[f"BiasDesign{k}"] = pct(D["kind"][k]["mean"])
        M[f"WithinTen{k}"] = share(D["kind"][k]["within10"])
        M[f"WithinTen{k}Light"] = share(D["kind_heavy"][f"{k}|light"]["within10"])
        M[f"WithinTen{k}Heavy"] = share(D["kind_heavy"][f"{k}|heavy"]["within10"])
    M["MitMstMeanP"] = pval(D["mit_vs_mst"]["p_mean"])
    M["MitMstLeveneP"] = pval(D["mit_vs_mst"]["p_levene"])
    M["MitMstAbsP"] = pval(D["mit_vs_mst"]["p_abs"])
    M["MitMstLeveneLightP"] = pval(D["mit_vs_mst_light"]["p_levene"])
    M["ModelEffectP"] = pval(D["anova"]["C(model)"]["p"])
    M["ModelEffectF"] = num(D["anova"]["C(model)"]["F"], 1)
    M["KindEffectP"] = pval(D["anova"]["C(kind)"]["p"])
    M["ModelEffectLightP"] = pval(D["anova_light"]["C(model)"]["p"])
    M["FamilyKwP"] = pval(D["family_kw_p"])
    for m in MODELS:
        for k in ["MIT", "MST"]:
            M[f"Heavy{MODEL_MACRO[m]}{k}"] = pct(D["model_kind_heavy"][f"{m}|{k}|heavy"]["mean"], 0)
    # burst factor
    M["BurstMedian"] = num(B["overall"]["median"], 2)
    M["BurstQOne"], M["BurstQThree"] = num(B["overall"]["q1"], 2), num(B["overall"]["q3"], 2)
    M["BurstOnBand"] = share(B["overall"]["on_band"])
    M["BurstNCells"] = big(B["overall"]["n"])
    for m in MODELS:
        pm = B["per_model"][m]
        # Bayesian median when available, so that the value and its credible interval agree
        M[f"Burst{MODEL_MACRO[m]}"] = num(BB["per_model"][m]["median"] if BB else pm["median"], 2)
        M[f"BurstMax{MODEL_MACRO[m]}"] = num(pm["max"], 1)
        M[f"BurstOnBand{MODEL_MACRO[m]}"] = share(pm["on_band"])
        if BB:
            M[f"Burst{MODEL_MACRO[m]}Lo"] = num(BB["per_model"][m]["ci95"][0], 2)
            M[f"Burst{MODEL_MACRO[m]}Hi"] = num(BB["per_model"][m]["ci95"][1], 2)
    M["BurstModelP"] = pval(B["anova"]["C(model)"]["p"])
    M["BurstOutP"] = pval(B["anova"]["C(out)"]["p"])
    M["BurstInP"] = pval(B["anova"]["C(inp)"]["p"])
    M["BurstOutRobustP"] = pval(B["anova_robust"]["C(out)"]["p"])
    M["BurstModelRobustP"] = pval(B["anova_robust"]["C(model)"]["p"])
    M["BurstShort"] = num(B["short_output"]["B_short"], 2)
    M["BurstRest"] = num(B["short_output"]["B_rest"], 2)
    M["BurstShortRatio"] = pct(np.log(B["short_output"]["ratio"]), 0)
    M["BurstShortP"] = pval(B["short_output"]["p_mw"])
    M["BurstPaperExample"] = "1.4"
    M["BurstMixN"] = big(B["mixes"]["n"])
    M["BurstMixErr"] = pct(B["mixes"]["mean_err"], 0)
    M["BurstMixWithin"] = share(B["mixes"]["within15"])
    if BB:
        eq = [p_["p_equiv"] for p_ in BB["pairs"]]
        M["BurstEquivMin"] = share(min(eq))
        rat = [p_["ratio"] for p_ in BB["pairs"]]
        M["BurstPairMaxDiff"] = pct(max(abs(np.log(r)) for r in rat), 1, sign=False)
        M["BurstPairCi"] = pct(max(abs(np.log(c)) for p_ in BB["pairs"] for c in p_["ci95"]), 1, sign=False)
    lines = ["% Generated by analysis/latex_export.py -- do not edit by hand.",
             "% \\input{macros} in the preamble; every macro is prefixed with \\scale.",
             "\\providecommand{\\xspace}{}"]
    for k, v in M.items():
        lines.append(f"\\newcommand{{\\scale{k}}}{{{v}\\xspace}}")
    return "\n".join(lines) + "\n", M


# -------------------------------------------------------------------------------- tables
def table_laws(R, D):
    b = R.get("bayes")
    rows = []
    q = {"harmonic": "$-1$", "geometric": "$0$", "arithmetic": "$+1$"}
    for law in ["harmonic", "geometric", "arithmetic"]:
        L = D["laws"][law]
        pred = (num(b["loo"][law]["diff_vs_harmonic"], 1, sign=True) + r" $\pm$ " + num(b["loo"][law]["diff_se"], 1)) if b else "--"
        if law == "harmonic" and b:
            pred = "0 (reference)"
        rows.append(f"{law.capitalize()} & {q[law]} & {pct(L['mean'])} & {share(np.exp(L['rmse']) - 1)} & {share(L['within10'])} & {pred} \\\\")
    if b:
        fq = b["free"]["q"]
        rows.append(r"Free exponent & " + f"{num(fq['median'], 2)} [{num(fq['ci95'][0], 2)}, {num(fq['ci95'][1], 2)}]"
                    + r" & -- & -- & -- & " + num(b["loo"]["free"]["diff_vs_harmonic"], 1, sign=True) + r" $\pm$ "
                    + num(b["loo"]["free"]["diff_se"], 1) + r" \\")
    return ("% Combination laws: design-level errors (frequentist) and predictive score (Bayesian).\n"
            "\\begin{tabular}{lcrrrr}\n\\toprule\n"
            "Law & $q$ & Mean error & RMSE & Within $\\pm$10\\,\\% & $\\Delta$ log pred. density \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


def table_bias(R):
    f, b = R["freq"], R.get("bayes")
    rows = []
    for m in MODELS:
        for k in ["MIT", "MST"]:
            t = f["tests"]["H"][f"{m}|{k}"]
            fr = f"{pct(t['mean'])} [{pct(t['ci95'][0])}, {pct(t['ci95'][1])}]"
            if b:
                dl = b["harmonic"]["delta"][f"{m}|{k}"]
                br = f"{pct(dl['median'])} [{pct(dl['ci90'][0])}, {pct(dl['ci90'][1])}] & {share(dl['p_rope'])}"
            else:
                br = "-- & --"
            rows.append(f"{MODEL_TEX[m]} & {k} & {t['n']} & {fr} & {br} \\\\")
    t = f["tests"]["H"]["all"]
    if b:
        d0 = b["harmonic"]["delta0"]
        br = f"{pct(d0['median'])} [{pct(d0['ci90'][0])}, {pct(d0['ci90'][1])}] & {share(d0['p_rope'])}"
    else:
        br = "-- & --"
    rows.append("\\midrule\nAll & both & " + f"{t['n']} & {pct(t['mean'])} [{pct(t['ci95'][0])}, {pct(t['ci95'][1])}] & {br} \\\\")
    return ("% Bias of mix capacity w.r.t. the harmonic prediction per model and MoST test.\n"
            "\\begin{tabular}{llrccc}\n\\toprule\n"
            " & & & Frequentist & \\multicolumn{2}{c}{Bayesian} \\\\\n\\cmidrule(lr){4-4}\\cmidrule(lr){5-6}\n"
            "Model & Test & Designs & Mean [95\\,\\% CI] & $\\delta$ [90\\,\\% CrI] & $P(|\\delta|<10\\,\\%)$ \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


def table_mitmst(R, D):
    b = R.get("bayes")
    K = D["kind"]
    KH = D["kind_heavy"]
    H = b["harmonic"] if b else None

    def sd(k, w, d=0):
        return share(np.exp(H[w][k]["median"]) - 1, d) if H else "--"
    rows = [
        ("Mean bias", pct(K["MIT"]["mean"]), pct(K["MST"]["mean"]), "p = " + pval(D["mit_vs_mst"]["p_mean"])),
        ("Mean absolute error", share(np.exp(K["MIT"]["mae"]) - 1), share(np.exp(K["MST"]["mae"]) - 1), "p = " + pval(D["mit_vs_mst"]["p_abs"])),
        ("SD of log error", num(K["MIT"]["sd"], 2), num(K["MST"]["sd"], 2), "Levene p = " + pval(D["mit_vs_mst"]["p_levene"])),
        ("Within $\\pm$10\\,\\%, all mixes", share(K["MIT"]["within10"]), share(K["MST"]["within10"]), ""),
        ("Within $\\pm$10\\,\\%, without heavy class", share(KH["MIT|light"]["within10"]), share(KH["MST|light"]["within10"]), "Levene p = " + pval(D["mit_vs_mst_light"]["p_levene"])),
        ("Within $\\pm$10\\,\\%, with heavy class", share(KH["MIT|heavy"]["within10"]), share(KH["MST|heavy"]["within10"]), ""),
        ("$\\sigma_{\\mathrm{rep}}$ (repeat pure cell)", sd("MIT", "sd_rep", 1), sd("MST", "sd_rep", 1), ""),
        ("$\\sigma_{\\mathrm{run}}$ (repeat mix design)", sd("MIT", "sd_run", 1), sd("MST", "sd_run", 1), ""),
        ("$\\sigma_{\\mathrm{mix}}$ (design departure)", sd("MIT", "sd_mix"), sd("MST", "sd_mix"), ""),
    ]
    body = "\n".join(f"{a} & {c} & {d} & {e} \\\\" for a, c, d, e in rows)
    return ("% MIT (2-min) versus MST (30-min): same law, different precision. Design-level unless noted.\n"
            "\\begin{tabular}{lccl}\n\\toprule\n & MIT & MST & Test \\\\\n\\midrule\n" + body
            + "\n\\bottomrule\n\\end{tabular}\n")


def table_heavy(D):
    rows = []
    for m in MODELS:
        c = [pct(D["model_kind_heavy"][f"{m}|{k}|{h}"]["mean"], 0) for h in ["light", "heavy"] for k in ["MIT", "MST"]]
        rows.append(f"{MODEL_TEX[m]} & " + " & ".join(c) + " \\\\")
    return ("% Mean departure from the harmonic law with and without the heaviest class (600-1000 in, 1000-1500 out).\n"
            "\\begin{tabular}{lrrrr}\n\\toprule\n & \\multicolumn{2}{c}{Without heavy class} & \\multicolumn{2}{c}{With heavy class} \\\\\n"
            "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\nModel & MIT & MST & MIT & MST \\\\\n\\midrule\n" + "\n".join(rows)
            + f"\n\\midrule\nANOVA model effect & \\multicolumn{{2}}{{c}}{{p = {pval(D['anova_light']['C(model)']['p'])}}} & \\multicolumn{{2}}{{c}}{{all mixes: p = {pval(D['anova']['C(model)']['p'])}}} \\\\"
            + "\n\\bottomrule\n\\end{tabular}\n")


def table_burst_matrix(B):
    cells = pd.DataFrame(B["cells"])
    lines = ["% Burst factor B = MIT/MST per request class (rows: input tokens, columns: output tokens).",
             "\\begin{tabular}{ll" + "r" * len(OUT_RANGES) + "}", "\\toprule",
             " & & \\multicolumn{" + str(len(OUT_RANGES)) + "}{c}{Output tokens} \\\\",
             "\\cmidrule(lr){3-" + str(2 + len(OUT_RANGES)) + "}",
             "Model & Input & " + " & ".join(OUT_RANGES) + " \\\\", "\\midrule"]
    for j, m in enumerate(MODELS):
        x = cells[cells.model == m]
        med = B["per_model"][m]["median"]
        for i, inp in enumerate(reversed(IN_RANGES)):
            vals = []
            for o in OUT_RANGES:
                v = x[(x.inp == inp) & (x.out == o)].B.values[0]
                s = f"{v:.2f}"
                if abs(np.log(v / med)) >= np.log(1.15):
                    s = "\\textbf{" + s + "}"
                vals.append(s)
            lead = f"\\multirow{{4}}{{*}}{{{MODEL_TEX[m].split('-')[0]}}}" if i == 0 else ""
            lines.append(f"{lead} & {inp} & " + " & ".join(vals) + " \\\\")
        if j < len(MODELS) - 1:
            lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def table_burst_summary(B, BB):
    rows = []
    for m in MODELS:
        p = B["per_model"][m]
        med = BB["per_model"][m]["median"] if BB else p["median"]
        ci = f" [{BB['per_model'][m]['ci95'][0]:.2f}, {BB['per_model'][m]['ci95'][1]:.2f}]" if BB else ""
        rows.append(f"{MODEL_TEX[m]} & {med:.2f}{ci} & {p['q1']:.2f}--{p['q3']:.2f} & {p['min']:.2f}--{p['max']:.2f} & {share(p['on_band'])} \\\\")
    o = B["overall"]
    rows.append(f"\\midrule\nAll & {o['median']:.2f} & {o['q1']:.2f}--{o['q3']:.2f} & -- & {share(o['on_band'])} \\\\")
    return ("% Burst factor per model: median over the 20 request classes, spread and share within +-15 % of the median.\n"
            "\\begin{tabular}{lcccc}\n\\toprule\nModel & Median $B$ [95\\,\\% CrI] & IQR & Range & Within $\\pm$15\\,\\% \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


# ------------------------------------------------------------------------------- figures
def figures(fm, fd, R, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.linewidth": 0.6, "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
    W = 4.8  # LNCS text width in inches

    # 1. measured vs harmonic prediction, and the profile of q
    fig, ax = plt.subplots(1, 2, figsize=(W, 2.3), gridspec_kw=dict(width_ratios=[1.15, 1]))
    lo, hi = fm[["c_obs", "H"]].min().min() / 1.4, fm[["c_obs", "H"]].max().max() * 1.4
    xs = np.geomspace(lo, hi, 50)
    ax[0].fill_between(xs, xs / 1.1, xs * 1.1, color="#3b3592", alpha=0.12, lw=0)
    ax[0].plot(xs, xs, color="#3b3592", lw=0.8, ls="--")
    for m in MODELS:
        for k, mk in [("MIT", "o"), ("MST", "s")]:
            x = fm[(fm.model == m) & (fm.kind == k)]
            ax[0].scatter(x.H, x.c_obs, s=9, marker=mk, facecolor=COLORS[m] if k == "MIT" else "none",
                          edgecolor=COLORS[m], lw=0.7, label=f"{m.split('-')[0]} {k}")
    ax[0].set(xscale="log", yscale="log", xlim=(lo, hi), ylim=(lo, hi),
              xlabel="harmonic prediction (req/min)", ylabel="measured mix capacity (req/min)")
    ax[0].legend(fontsize=5.5, ncol=1, loc="lower right", handletextpad=0.2, borderaxespad=0.2)
    qp = R["freq"]["q_profile"]
    g, lr = np.array(qp["grid"]), np.array(qp["lr"])
    sel = (g >= -2.5) & (g <= 2)
    ax[1].plot(g[sel], np.minimum(lr[sel], 80), color="k", lw=1)
    if R.get("bayes"):
        qb = R["bayes"]["free"]["q"]
        ax[1].axvspan(qb["ci95"][0], qb["ci95"][1], color="#3b3592", alpha=0.25, lw=0)
    ax[1].axhline(3.84, color="0.5", lw=0.6, ls=":")
    for v, n in [(-1, "harmonic"), (0, "geometric"), (1, "arithmetic")]:
        ax[1].axvline(v, color="0.6", lw=0.5, ls="--")
        ax[1].text(v + 0.08, 78, n, ha="left", va="top", fontsize=5.5, rotation=90, color="0.35")
    ax[1].set(xlabel="power-mean exponent $q$", ylabel="profile LR statistic", ylim=(0, 80))
    fig.tight_layout()
    fig.savefig(out / "fig_additivity.pdf")
    plt.close(fig)

    # 2. MIT vs MST: design-level departures, light vs heavy class
    fig, ax = plt.subplots(figsize=(W, 1.7))
    rng = np.random.default_rng(1)
    for i, k in enumerate(["MIT", "MST"]):
        x = fd[fd.kind == k]
        y = i + rng.uniform(-0.28, 0.28, len(x))
        ax.scatter(np.clip(x.r, np.log(0.4), np.log(3.4)), y, s=8, c=np.where(x.heavy, HEAVYC, LIGHT), lw=0, alpha=0.85)
        ax.plot([x.r.mean()] * 2, [i - 0.36, i + 0.36], color="k", lw=1.5)
    ax.axvspan(-TEN, TEN, color="#3b3592", alpha=0.1, lw=0)
    ax.axvline(0, color="0.5", lw=0.6)
    ticks = [0.5, 0.8, 1, 1.25, 2, 3]
    ax.set_xticks(np.log(ticks), [f"{100 * (t - 1):+.0f}%" for t in ticks])
    ax.set_yticks([0, 1], ["MIT", "MST"])
    ax.set_xlabel("measured capacity vs harmonic prediction (one point per mix design)")
    ax.scatter([], [], c=LIGHT, s=8, label="without heavy class")
    ax.scatter([], [], c=HEAVYC, s=8, label="with heavy class")
    ax.legend(fontsize=6, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "fig_mit_mst.pdf")
    plt.close(fig)

    # 3. burst factor heatmaps
    B = pd.DataFrame(R["burst"]["cells"])
    fig, ax = plt.subplots(1, 3, figsize=(W, 1.9), sharey=True)
    vmin, vmax = 2.8, 6.0
    for j, m in enumerate(MODELS):
        x = B[B.model == m].pivot(index="inp", columns="out", values="B").reindex(index=IN_RANGES, columns=OUT_RANGES)
        im = ax[j].imshow(x.values, origin="lower", cmap="Blues", vmin=vmin, vmax=vmax, aspect="auto")
        for (r, c), v in np.ndenumerate(x.values):
            ax[j].text(c, r, f"{v:.1f}", ha="center", va="center", fontsize=5.5,
                       color="white" if v > 4.6 else "black", fontweight="bold" if v > 6 else "normal")
        ax[j].set_xticks(range(len(OUT_RANGES)), [o.split("-")[0] for o in OUT_RANGES], fontsize=6)
        ax[j].set_title(m, fontsize=7)
        ax[j].set_xlabel("output tokens (from)", fontsize=6.5)
    ax[0].set_yticks(range(len(IN_RANGES)), [i.split("-")[0] for i in IN_RANGES], fontsize=6)
    ax[0].set_ylabel("input tokens (from)", fontsize=6.5)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("$B$ = MIT / MST", fontsize=6.5)
    cb.ax.tick_params(labelsize=6)
    fig.savefig(out / "fig_burst.pdf", bbox_inches="tight")
    plt.close(fig)

    # 4. burst factor of mixes: observed vs predicted from the components
    mb = pd.DataFrame(R["burst"]["mixes"]["rows"])
    if len(mb):
        fig, ax = plt.subplots(figsize=(2.4, 2.2))
        lim = (2.8, 7)
        ax.plot(lim, lim, color="#3b3592", lw=0.8, ls="--")
        ax.fill_between(lim, np.array(lim) / 1.15, np.array(lim) * 1.15, color="#3b3592", alpha=0.12, lw=0)
        for m in MODELS:
            x = mb[mb.model == m]
            ax.scatter(np.exp(x.logB_pred), np.exp(x.logB_obs), s=14, color=COLORS[m], label=m.split("-")[0],
                       marker="o", edgecolor="white", lw=0.4)
        ax.set(xlim=lim, ylim=lim, xlabel="$B$ predicted from components", ylabel="$B$ measured")
        ax.legend(fontsize=6, loc="upper left")
        fig.tight_layout()
        fig.savefig(out / "fig_burst_mix.pdf")
        plt.close(fig)


# --------------------------------------------------------------------------- section text
SECTION = r"""% Draft evaluation subsections for the SCALE paper. Generated by analysis/latex_export.py;
% edit freely after copying into the paper. Requires: \input{macros}, booktabs, multirow, graphicx, xspace.

\subsection{Additivity of Capacity Units (RQ3)}
\label{sec:additivity}

SCALE charges every request $r$ its Capacity Units $SK_r = SK_{max}/MST_r$ and admits a workload as long
as the Capacity Units consumed per minute do not exceed $SK_{max}$. For a mix in which class $i$
represents a share $p_i$ of the requests, this accounting predicts a capacity
\begin{equation}
  C_{\mathrm{mix}} \;=\; \Big(\sum_i \frac{p_i}{C_i}\Big)^{-1},
  \label{eq:harmonic}
\end{equation}
i.e., the weighted \emph{harmonic} mean of the class capacities $C_i$. This is the utilisation law of
operational analysis, in which $1/C_i$ is the service demand of class $i$~\cite{TODO-denning-buzen}.
The law is classical; what is not obvious is whether it survives the non-linear effects of LLM serving
(continuous batching, KV-cache pressure, prefill--decode interference). RQ3 therefore asks:
\emph{do the Capacity Units of different request classes add up when the classes are mixed?}

\paragraph{Setup.} We ran MoST on \scaleNDesigns mix designs (\scaleNMixRuns runs) of two to five request
classes on the three A40 deployments, in both MIT and MST mode, using two design families: equal
request shares and \emph{load-balanced} shares ($p_i \propto C_i$, so that every class consumes the
same fraction of the server). \scaleNRepeatDesigns designs were repeated two to six times
(\scaleNRepeatRuns runs) to assess stability. We compare Eq.~\eqref{eq:harmonic} with the geometric and
arithmetic means of the class capacities by embedding all three in the power mean
$M_q = (\sum_i p_i C_i^{\,q})^{1/q}$ ($q=-1$ harmonic, $q=0$ geometric, $q=+1$ arithmetic). Capacities
are latent in MoST, since only pass/fail verdicts at the probed rates are observed; the Bayesian
analysis therefore models each run's capacity as the threshold of a logistic pass/fail curve, fitted
in two stages (pure classes first, mixes second) with design and run random effects. The frequentist
analysis uses the final binary-search bracket and takes the mix design as the unit of inference.

\paragraph{The harmonic law holds.} The data select the harmonic law (Table~\ref{tab:laws},
Fig.~\ref{fig:additivity}): the estimated exponent is $q=\scaleQHatBayes$ (95\,\% CrI
$[\scaleQBayesLo, \scaleQBayesHi]$; profile likelihood \scaleQHatFreq, 95\,\% CI
$[\scaleQFreqLo, \scaleQFreqHi]$), the harmonic prediction is closer than the arithmetic one for
\scaleHarmonicWinShare of the runs, and leaving $q$ free does not improve the out-of-sample predictive
density (\scalePredFree $\pm$ \scalePredFreeSE log units), whereas the geometric (\scalePredGeom) and
arithmetic (\scalePredArith) laws are clearly worse. A naive arithmetic average of capacities
overestimates mix capacity by \scaleArithMeanErr on average. Regressing log measured capacity on the
log harmonic prediction gives a slope of \scaleCalibSlope (95\,\% CI $[\scaleCalibSlopeLo,
\scaleCalibSlopeHi]$, $R^2=\scaleCalibRsq$). Mix capacity is also bounded by its classes:
\scaleBoundsIn of \scaleBoundsN runs lie between the capacities of their slowest and fastest class,
and none exceeds the arithmetic mean.

\paragraph{A small, model-dependent bias.} Mixes deliver slightly less than their Capacity Units
promise: \scaleBiasBayes on average (90\,\% CrI $[\scaleBiasBayesLo, \scaleBiasBayesHi]$; frequentist
\scaleBiasFreq, 95\,\% CI $[\scaleBiasFreqLo, \scaleBiasFreqHi]$), which is practically equivalent to
zero within $\pm$10\,\% (TOST $p=\scaleBiasTostP$; $P(|\delta|<10\,\%)=\scaleBiasBayesPRope$).
Table~\ref{tab:bias} breaks the bias down by model and test. In SCALE terms, an oversubscription ratio
$\rho$ applied on top of an accounting that is \scaleBiasBayes optimistic commits about
$\rho/(1+\delta)$ of the physical capacity; providers should either reserve a margin of a few percent
on $SK_{max}$ or account for it when setting $\rho$.

\paragraph{Same law, different precision in MIT and MST.} Both MoST tests follow the same law with the
same mean bias (\scaleBiasDesignMIT vs.\ \scaleBiasDesignMST, $p=\scaleMitMstMeanP$), but individual
predictions are about twice as precise for the 2-minute MIT test as for the 30-minute MST test
(mean absolute error \scaleMaeMIT vs.\ \scaleMaeMST, Levene $p=\scaleMitMstLeveneP$; Table~\ref{tab:mitmst},
Fig.~\ref{fig:mitmst}). Repeated runs are very stable (\scaleSdRunMIT and \scaleSdRunMST between repeats
of a design, \scaleSdRepMIT and \scaleSdRepMST between repeats of a pure class), so the spread reflects
genuine design-specific departures (\scaleSdMixMIT in MIT, \scaleSdMixMST in MST) rather than
measurement noise. A 90\,\% planning band around Eq.~\eqref{eq:harmonic} is \scaleBandMIT for MIT and
\scaleBandMST for MST. This matters for SCALE because its user-facing currency $Q$ is derived from the
sustainable capacities, precisely where additivity is least precise. Because the departures are tied to
the design and not to noise, they do not average out across users who send the same kind of mix.

\paragraph{The heaviest class breaks additivity, depending on the model.} Without the heaviest class
(600--1000 input and 1000--1500 output tokens), the three models behave alike (ANOVA model effect
$p=\scaleModelEffectLightP$) and \scaleWithinTenMITLight of the MIT designs are predicted within
$\pm$10\,\%. With it, the model matters ($p=\scaleModelEffectP$; Table~\ref{tab:heavy}): Gemma mixes depart from the
prediction by \scaleHeavyGemmaMST in MST and Llama mixes by \scaleHeavyLlamaMST. The share of
designs within $\pm$10\,\% drops to \scaleWithinTenMITHeavy (MIT) and \scaleWithinTenMSTHeavy (MST).
Two effects are consistent with this pattern. First, the KV-cache footprint per token differs widely
(about 448\,KB for Gemma-7B with multi-head attention versus 128\,KB and 56\,KB for the grouped-query
attention of Llama-3.1-8B and DeepSeek-R1-Distill-Qwen-7B), which affects heavy requests most. Second,
MoST evaluates its MST criteria (response-time trend, backlog, success rate) over all the requests of a
run: in a mix, the many short requests can mask the slow ones. Gemma's heavy class alone fails the MST
criteria at 8\,req/min while completing every request, yet equal-share mixes containing it pass at about
40\,req/min. Resources may thus add up while the QoE verdict does not, which argues for per-class QoE
criteria when MoST is applied to mixed workloads.

\begin{table}[t]
  \centering
  \caption{Combination laws for mix capacity. Errors are log-ratios of measured to predicted capacity
  averaged over the \scaleNDesigns mix designs; the last column is the out-of-sample log predictive
  density relative to the harmonic law ($\pm$ standard error).}
  \label{tab:laws}
  \input{tables/tab_laws}
\end{table}

\begin{table}[t]
  \centering
  \caption{Bias of mix capacity relative to the harmonic prediction, by model and MoST test.}
  \label{tab:bias}
  \resizebox{\textwidth}{!}{\input{tables/tab_bias}}
\end{table}

\begin{table}[t]
  \centering
  \caption{MIT versus MST: the same law with different precision.}
  \label{tab:mitmst}
  \input{tables/tab_mitmst}
\end{table}

\begin{table}[t]
  \centering
  \caption{Mean departure from the harmonic law by model, with and without the heaviest request class.}
  \label{tab:heavy}
  \input{tables/tab_heavy}
\end{table}

\begin{figure}[t]
  \centering
  \includegraphics[width=\textwidth]{figures/fig_additivity}
  \caption{Left: measured mix capacity versus the harmonic prediction of Eq.~\eqref{eq:harmonic}
  (filled: MIT, hollow: MST; band: $\pm$10\,\%). Right: profile likelihood of the power-mean exponent
  $q$, with the Bayesian 95\,\% credible interval shaded.}
  \label{fig:additivity}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\textwidth]{figures/fig_mit_mst}
  \caption{Departure of every mix design from the harmonic law in MIT and MST (black tick: mean;
  band: $\pm$10\,\%). Orange designs contain the heaviest request class.}
  \label{fig:mitmst}
\end{figure}

\subsection{Burst factor (RQ4)}
\label{sec:burst}

SCALE exposes a single currency based on the sustainable capacity and keeps the instantaneous capacity
$IK_{max}$ as a background safety threshold for bursts. We define the \emph{burst factor} of a request
class as the ratio of its instantaneous to its sustainable throughput,
\begin{equation}
  B_r \;=\; \frac{MIT_r}{MST_r},
  \label{eq:burst}
\end{equation}
i.e., how many times its sustainable rate a client may reach during a 2-minute burst. Since
$IK_r/SK_r = (IK_{max}/SK_{max})/B_r$, the sustainable and instantaneous Capacity Units rank and price
request classes identically if and only if $B_r$ is constant across classes. A constant burst factor is
therefore what justifies exposing one currency. RQ4 asks: \emph{is the burst factor constant across
request classes and deployments, and can it be used to size the burst allowance of a plan?}

\paragraph{The burst factor is nearly constant.} Across the \scaleBurstNCells request classes of the
three deployments, the median burst factor is \scaleBurstMedian (interquartile range
\scaleBurstQOne--\scaleBurstQThree; Table~\ref{tab:burst}, Fig.~\ref{fig:burst}), and the per-model
medians are almost identical: \scaleBurstDeepSeek for DeepSeek (95\,\% CrI
$[\scaleBurstDeepSeekLo, \scaleBurstDeepSeekHi]$), \scaleBurstGemma for Gemma
($[\scaleBurstGemmaLo, \scaleBurstGemmaHi]$) and \scaleBurstLlama for Llama
($[\scaleBurstLlamaLo, \scaleBurstLlamaHi]$). The model has no detectable effect
(ANOVA $p=\scaleBurstModelP$): the posterior ratio between the burst factors of any two models lies
within \scaleBurstPairCi of one (95\,\% CrI), and the probability that they are equivalent within
$\pm$10\,\% is at least \scaleBurstEquivMin. Moreover, \scaleBurstOnBand of the classes lie within
$\pm$15\,\% of their model's median. The burst factor is thus a highly portable property of a MoST-characterised deployment,
which strengthens the portability claim of RQ1 with a quantity that can be compared across models in
absolute terms, unlike $K$.

\paragraph{Systematic exceptions.} Once Gemma's two heaviest-output cells are set aside, the output
length has a clear effect ($p=\scaleBurstOutRobustP$): classes with short answers (1--100 output
tokens) tolerate larger bursts ($B=\scaleBurstShort$ vs.\ \scaleBurstRest, \scaleBurstShortRatio,
$p=\scaleBurstShortP$). The two Gemma cells with long inputs and long outputs reach $B$ up to
\scaleBurstMaxGemma; they coincide with the MST anomaly discussed in Sect.~\ref{sec:additivity}.
For mixes measured in both tests (\scaleBurstMixN designs), the measured burst factor exceeds the one
predicted from the class capacities by \scaleBurstMixErr on average, because mixes depart more from
additivity in MST than in MIT (Fig.~\ref{fig:burstmix}).

\paragraph{Implications for SCALE.} A single burst factor of about \scaleBurstMedian\ supports SCALE's
design choice of one user-facing currency: pricing bursts with sustainable Capacity Units mis-states
their instantaneous load by less than 15\,\% for \scaleBurstOnBand of the classes. It also gives a
direct rule for the Token Bucket: a plan with a sustainable rate $s$ can be granted a burst rate of up
to about $B\cdot s$ over 2-minute windows, with short-answer classes allowing about
\scaleBurstShortRatio more. Note that the illustrative capacity profile of the introduction
(30{,}000 requests per 30 minutes and 1{,}400 requests per minute, i.e., $B\approx\scaleBurstPaperExample$)
is far more conservative than the measured burst factor.

\begin{table}[t]
  \centering
  \caption{Burst factor $B=MIT/MST$ per model: median over the request classes (Bayesian 95\,\%
  credible interval), interquartile range, range, and share of classes within $\pm$15\,\% of the
  median.}
  \label{tab:burst}
  \input{tables/tab_burst_summary}
\end{table}

\begin{table}[t]
  \centering
  \caption{Burst factor per request class. Bold: more than 15\,\% away from the model's median.}
  \label{tab:burstmatrix}
  \resizebox{\textwidth}{!}{\input{tables/tab_burst_matrix}}
\end{table}

\begin{figure}[t]
  \centering
  \includegraphics[width=\textwidth]{figures/fig_burst}
  \caption{Burst factor $B=MIT/MST$ of every request class (rows: input tokens; columns: output
  tokens; labels give the lower bound of each interval).}
  \label{fig:burst}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=0.5\textwidth]{figures/fig_burst_mix}
  \caption{Burst factor of mixes measured in both tests versus the value predicted from their classes
  (band: $\pm$15\,\%).}
  \label{fig:burstmix}
\end{figure}
"""

PREVIEW = r"""\documentclass[runningheads]{llncs}
\usepackage[T1]{fontenc}
\usepackage{graphicx,booktabs,multirow,xspace,amsmath}
\input{macros}
\begin{document}
\title{SCALE -- additivity and burst-factor analysis (preview)}
\author{Generated assets}
\institute{analysis/latex}
\maketitle
\section{Evaluation (draft)}
\input{section_additivity_burst}
\end{document}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(HERE / "output"))
    ap.add_argument("--out", default=str(HERE / "latex"))
    args = ap.parse_args()
    res_dir, out = Path(args.results), Path(args.out)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    R = json.loads((res_dir / "results.json").read_text())
    fm = pd.read_csv(res_dir / "mix_frequentist.csv")
    fm, fd = design_frame(fm)
    D = derived_stats(fm, fd)
    (out / "derived.json").write_text(json.dumps(D, indent=1))
    text, M = macros(R, D)
    (out / "macros.tex").write_text(text, encoding="utf-8")
    T = {"tab_laws": table_laws(R, D), "tab_bias": table_bias(R), "tab_mitmst": table_mitmst(R, D),
         "tab_heavy": table_heavy(D), "tab_burst_matrix": table_burst_matrix(R["burst"]),
         "tab_burst_summary": table_burst_summary(R["burst"], R.get("burst_bayes"))}
    for k, v in T.items():
        (out / "tables" / f"{k}.tex").write_text(v, encoding="utf-8")
    figures(fm, fd, R, out / "figures")
    (out / "section_additivity_burst.tex").write_text(SECTION, encoding="utf-8")
    (out / "preview.tex").write_text(PREVIEW, encoding="utf-8")
    print("wrote", len(M), "macros,", len(T), "tables and the figures to", out)


if __name__ == "__main__":
    main()
