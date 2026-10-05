"""Inject the additivity results into report_template.html.

Usage: python analysis/build_report.py <analysis out dir> <output html>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def main(out_dir, html_path):
    out_dir = Path(out_dir)
    res = json.loads((out_dir / "results.json").read_text())
    fm = pd.read_csv(out_dir / "mix_frequentist.csv")
    bayes = res["bayes"]
    pm = {m["unit"]: m for m in bayes["per_mix"]}

    mixes = []
    for _, r in fm.iterrows():
        b = pm[r.unit]
        mixes.append(dict(
            model=r.model, kind=r.kind, family=r.family, label=r.label, exp=r.unit.split("|")[1],
            obs=round(r.c_obs, 1), H=round(r.H, 1), G=round(r.G, 1), A=round(r.A, 1),
            cmin=round(r.cmin, 1), cmax=round(r.cmax, 1),
            rH=round(b["rH"], 4), rH_lo=round(b["rH_ci"][0], 4), rH_hi=round(b["rH_ci"][1], 4),
            fH=round(r.r_H, 4), fG=round(r.r_G, 4), fA=round(r.r_A, 4),
            p_rope=round(b["p_rope"], 3), p_minmax=round(b["p_minmax"], 3), p_HA=round(b["p_HA"], 3),
            pos=round(float((np.log(r.c_obs) - np.log(r.H)) / (np.log(r.A) - np.log(r.H))), 3),
        ))

    def iv(x):
        return dict(med=x["median"], lo90=x["ci90"][0], hi90=x["ci90"][1], lo95=x["ci95"][0],
                    hi95=x["ci95"][1], p_rope=x["p_rope"], p_rope5=x["p_rope5"], p_gt0=x["p_gt0"])

    freq = res["freq"]
    data = dict(
        mixes=mixes,
        groups=[dict(key=g, bayes=iv(bayes["harmonic"]["delta"][g]),
                     freq=dict(mean=freq["tests"]["H"][g]["mean"], lo=freq["tests"]["H"][g]["ci95"][0],
                               hi=freq["tests"]["H"][g]["ci95"][1], n=freq["tests"]["H"][g]["n"]))
                for g in bayes["groups"]],
        overall=dict(bayes=iv(bayes["harmonic"]["delta0"]),
                     freq=dict(mean=freq["tests"]["H"]["all"]["mean"], lo=freq["tests"]["H"]["all"]["ci95"][0],
                               hi=freq["tests"]["H"]["all"]["ci95"][1], n=freq["tests"]["H"]["all"]["n"])),
        q=dict(bayes=iv(bayes["free"]["q"]), p_near_h=bayes["free"]["q"]["p_near_harmonic"],
               prof=dict(grid=freq["q_profile"]["grid"], lr=freq["q_profile"]["lr"],
                         q_hat=freq["q_profile"]["q_hat"], ci=freq["q_profile"]["ci95"],
                         p_h=freq["q_profile"]["p_q_minus1"])),
        sd={law: dict(rep={k: iv(v) for k, v in bayes[law]["sd_rep"].items()},
                      mix={k: iv(v) for k, v in bayes[law]["sd_mix"].items()},
                      s={k: iv(v) for k, v in bayes[law]["s"].items()})
            for law in ["harmonic", "geometric", "arithmetic", "free"]},
        delta0={law: iv(bayes[law]["delta0"]) for law in ["harmonic", "geometric", "arithmetic", "free"]},
        pred=bayes["loo"],
        tests={law: freq["tests"][law] for law in ["H", "G", "A"]},
        family=freq["drivers"]["family"],
        drivers={k: v for k, v in freq["drivers"].items() if k != "family"},
        bounds=freq["bounds"], calib=freq["calibration"],
        share=dict(minmax=iv(bayes["share_minmax"]), HA=iv(bayes["share_HA"]), rope=iv(bayes["share_rope"])),
        diag=bayes["diagnostics"], cells=bayes["cells"],
        meta=dict(rows=res["n_rows"], units=res["n_units"], mix_runs=freq["n_mix_runs"],
                  designs=freq["n_designs"], rep_sd=freq["pooled_replicate_sd"],
                  hv_a=freq["H_vs_A_wilcoxon_p"], hv_g=freq["H_vs_G_wilcoxon_p"],
                  h_better=freq["H_better_share"], non_monotone=res["non_monotone_pure"]),
    )
    tpl = (HERE / "report_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), default=float))
    Path(html_path).write_text(html, encoding="utf-8")
    print("wrote", html_path, len(html) // 1024, "KB")


if __name__ == "__main__":
    main(*sys.argv[1:3])
