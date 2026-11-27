"""Numbers of the ACM TAAS SCALE article: RQ1 (repeatability), RQ2 (transferability) and the
request-count baseline of RQ3.

Usage (from the repository root):
  python analysis/taas_rq_analysis.py

Inputs:
  MIT_MST_results/            pure-profile MoST runs (merged with MergeAllCsv)
  analysis/output/mix_frequentist.csv   mixture runs (produced by additivity_analysis.py / run_all.py)
Outputs (analysis/output/taas/):
  pure_units.csv              one row per pure MoST search: final LARGEST_TRUE, SMALLEST_FALSE, bracket width
  rq1_repeatability.csv       per model and regime: replicate agreement (Table tab:rq1)
  rq2_transfer.csv            per regime and model pair: order and magnitude transfer (Table tab:rq2)
  rq3_request_count.csv       per model and regime: request-count vs CU errors on mixtures (Table tab:rq3)

Definitions:
  T_k(p) of a search is the LARGEST_TRUE of its last iteration; the final bracket width is (SF-LT)/SF.
  The per-profile T_k(p) used for RQ2 is the geometric mean of the replicates.
  Composition error eps = T_obs / T_pred - 1. CU prediction = harmonic law (column H of
  mix_frequentist.csv); request-count prediction = request-weighted arithmetic mean (column A).
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "output" / "taas"
MODELS = {
    "deepseek-ai_DeepSeek-R1-Distill-Qwen-7B-A40-1gpus": "DeepSeek",
    "google_gemma-7b-A40-1gpus": "Gemma",
    "meta-llama_Llama-3.1-8B-Instruct-A40-1gpus": "Llama",
}
pd.set_option("display.width", 250)


def load_pure():
    sys.path.insert(0, str(ROOT))
    import MergeAllCsv

    cols, rows, _ = MergeAllCsv.merge_all_csv(root=str(ROOT / "MIT_MST_results"), source_column="RESULTS_SOURCE")
    d = pd.DataFrame(rows, columns=cols)
    d = d[~d.EXPERIMENT_NAME.str.contains("MIX")]
    for c in ["REQ_MIN", "LARGEST_TRUE", "SMALLEST_FALSE"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["model"] = d.RESULTS_SOURCE.map(MODELS)
    d["kind"] = d.EXPERIMENT_NAME.str.extract(r"Experiment_(M[IS]T)")[0]
    d = d.dropna(subset=["model", "kind"]).sort_values(["RESULTS_SOURCE", "EXPERIMENT_NAME", "IDENTIFIER", "DATE"])
    u = (
        d.groupby(["model", "kind", "EXPERIMENT_NAME", "IDENTIFIER"])
        .agg(
            lt=("LARGEST_TRUE", "last"),
            sf=("SMALLEST_FALSE", "last"),
            n=("REQ_MIN", "size"),
            fin=("FINISHED", "last"),
            term=("TERMINATION_REASON", "last"),
            rel=("BINARY_SEARCH_RELATIVE_DISTANCE", "last"),
        )
        .reset_index()
    )
    u["rel"] = pd.to_numeric(u.rel, errors="coerce")
    u["width"] = (u["sf"] - u["lt"]) / u["sf"]
    return u


def pair_diffs(w):
    """Relative differences |a-b|/mean(a,b) over all replicate pairs, and Spearman rho per pair."""
    diffs, rhos = [], []
    for a, b in itertools.combinations(w.columns, 2):
        diffs += list((abs(w[a] - w[b]) / ((w[a] + w[b]) / 2)).values)
        rhos.append(w[a].rank().corr(w[b].rank()))
    return np.array(diffs), rhos


def rq1(u):
    rows = []
    for (m, k), g in list(u.groupby(["model", "kind"])) + [(("All", k), u[u.kind == k]) for k in ["MIT", "MST"]]:
        diffs, rhos, sq, dof, ov = [], [], 0.0, 0, []
        for _, gm in g.groupby("model"):
            w = gm.pivot(index="IDENTIFIER", columns="EXPERIMENT_NAME", values="lt")
            dd, rr = pair_diffs(w)
            diffs += list(dd)
            rhos += rr
            L = np.log(w)
            sq += ((L.sub(L.mean(axis=1), axis=0)) ** 2).values.sum()
            dof += L.shape[0] * (L.shape[1] - 1)
            br = gm.groupby("IDENTIFIER").agg(lo=("lt", "max"), hi=("sf", "min"))
            ov += list(br.lo <= br.hi)
        diffs = np.array(diffs)
        rows.append(
            dict(
                model=m,
                kind=k,
                reps=g.groupby("IDENTIFIER").EXPERIMENT_NAME.nunique().max() if m != "All" else np.nan,
                width_med=100 * g.width.median(),
                diff_med=100 * np.median(diffs),
                share_le5=100 * (diffs <= 0.05).mean(),
                share_le10=100 * (diffs <= 0.10).mean(),
                diff_max=100 * diffs.max(),
                sd_log=np.sqrt(sq / dof),
                rho_min=min(rhos),
                overlap=100 * np.mean(ov),
                searches=len(g),
                hit_limit=int(g.term.fillna("").str.contains("LIMIT").sum()),
            )
        )
    return pd.DataFrame(rows)


def per_profile_T(u):
    u = u.assign(logT=np.log(u["lt"]))
    return u.groupby(["kind", "model", "IDENTIFIER"]).logT.mean().unstack("model")


def rq2(u):
    T = per_profile_T(u)
    rows = []
    for k in ["MST", "MIT"]:
        L = T.loc[k]
        n, m = L.shape
        R = L.rank()
        W = 12 * ((R.sum(axis=1) - m * (n + 1) / 2) ** 2).sum() / (m**2 * (n**3 - n))
        spread = np.exp(L.max() - L.min()).round(0).to_dict()
        logc = L.max() - L
        for a, b in itertools.combinations(L.columns, 2):
            s = (L[b] - L[a]).mean()
            e1 = np.abs(np.exp(L[a] + s - L[b]) - 1)
            ref = L[b].idxmax()
            e2 = np.abs(np.exp(L[a] + L[b][ref] - L[a][ref] - L[b]) - 1)
            rows.append(
                dict(
                    kind=k,
                    pair=f"{a}-{b}",
                    rho=L[a].rank().corr(L[b].rank()),
                    r_logc=logc[a].corr(logc[b]),
                    beta=np.polyfit(logc[a], logc[b], 1)[0],
                    rescaled_med=100 * np.median(e1),
                    rescaled_le10=100 * np.mean(e1 <= 0.10),
                    rescaled_max=100 * e1.max(),
                    lightest_med=100 * np.median(e2),
                    kendall_W=W,
                    spread_Tmax_Tmin=str(spread),
                )
            )
    return pd.DataFrame(rows)


def same_output_spread(u):
    T = np.exp(per_profile_T(u)).stack().rename("T").reset_index()
    T["out"] = T.IDENTIFIER.str.split("_").str[1]
    r = T.groupby(["model", "kind", "out"])["T"].agg(lambda x: x.max() / x.min()).rename("R").reset_index()
    print("\nSame output interval, max/min T across input intervals: median %.2f (MIT %.2f, MST %.2f), max %.2f"
          % (r.R.median(), r[r.kind == "MIT"].R.median(), r[r.kind == "MST"].R.median(), r.R.max()))


def rq3_request_count():
    d = pd.read_csv(ROOT / "analysis" / "output" / "mix_frequentist.csv")
    d = d[d.n_comp > 1].copy()  # drop the single-profile control run
    d["eH"] = d.c_obs / d.H - 1
    d["eA"] = d.c_obs / d.A - 1
    d["fA"] = d.A / d.c_obs

    def s(g):
        return pd.Series(
            dict(
                runs=len(g),
                cu_med=100 * g.eH.abs().median(),
                cu_le10=100 * (g.eH.abs() <= 0.10).mean(),
                req_med=100 * g.eA.abs().median(),
                req_le10=100 * (g.eA.abs() <= 0.10).mean(),
                req_over=100 * (g.fA > 1).mean(),
                req_factor_med=g.fA.median(),
                req_factor_max=g.fA.max(),
            )
        )

    t = pd.concat(
        [
            d.groupby(["model", "kind"]).apply(s).reset_index(),
            d.groupby("kind").apply(s).reset_index().assign(model="All"),
            s(d).to_frame().T.assign(model="All", kind="All"),
        ]
    )
    print("\nWorst request-count overestimates:")
    print(d.nlargest(3, "fA")[["model", "kind", "label", "c_obs", "H", "A", "fA"]].to_string(index=False))
    return t


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    u = load_pure()
    u.to_csv(OUT / "pure_units.csv", index=False)
    print(f"{len(u)} pure searches, {int(u.n.sum())} iterations")
    for name, df in [("rq1_repeatability", rq1(u)), ("rq2_transfer", rq2(u)), ("rq3_request_count", rq3_request_count())]:
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"\n== {name}\n" + df.to_string(index=False, float_format=lambda x: "%.3f" % x))
    same_output_spread(u)


if __name__ == "__main__":
    main()
