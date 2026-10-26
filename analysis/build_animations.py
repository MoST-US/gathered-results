"""Build the didactic animations page (Spanish) from the additivity analysis output.

Usage: python analysis/build_animations.py <analysis out dir> <output html> [es|en]

Only frequentist per-run results (mix_frequentist.csv) are needed: the page uses real
capacities, mixes and repeated runs; the SLA and KV-cache scenes are illustrations whose inputs
are stated on the page.
"""
import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
HEAVY = "600-1000_1000-1500"


def main(out_dir, html_path, lang="es"):
    fm = pd.read_csv(Path(out_dir) / "mix_frequentist.csv")
    fm["mu"] = fm.mu.map(ast.literal_eval)
    fm["p"] = fm.p.map(ast.literal_eval)
    fm["comps"] = fm.comps.map(ast.literal_eval)
    fm["heavy"] = fm.label.str.contains(HEAVY)
    fm["design"] = fm.model + "|" + fm.kind + "|" + fm.label

    # scene 2: one real pair of cells (DeepSeek MIT: short/short + long/long)
    pair = fm[(fm.model == "DeepSeek-R1-Qwen-7B") & (fm.kind == "MIT")
              & fm.comps.map(lambda c: sorted(c) == sorted(["1-100_1-100", HEAVY]))]
    first = pair.iloc[0]
    caps = dict(zip(first.comps, np.exp(first.mu)))
    pair_pts = [dict(heavy_share=float(dict(zip(r.comps, r.p))[HEAVY]), obs=float(r.c_obs))
                for _, r in pair.iterrows()]

    # scenes 4 and 5: one point per design (repeats averaged)
    designs = []
    for key, g in fm.groupby("design"):
        r = g.iloc[0]
        designs.append(dict(model=r.model, kind=r.kind, heavy=bool(r.heavy), label=r.label,
                            mu=[round(v, 5) for v in r.mu],
                            p=[round(float(v), 5) for v in np.mean(np.stack(g.p.values), axis=0)],
                            obs=round(float(np.exp(np.log(g.c_obs).mean())), 2),
                            rH=round(float(g.r_H.mean()), 5), runs=len(g)))

    # scene 8: repeated runs relative to their design's median
    repeats = []
    for key, g in fm.groupby("design"):
        if len(g) < 2:
            continue
        med = np.median(np.log(g.c_obs))
        for c in g.c_obs:
            repeats.append(dict(kind=g.kind.iloc[0], heavy=bool(g.heavy.iloc[0]), model=g.model.iloc[0],
                                label=g.label.iloc[0], dev=round(float(np.log(c) - med), 4),
                                n=len(g)))

    burst = None
    rj = Path(out_dir) / "results.json"
    if rj.exists():
        R = json.loads(rj.read_text())
        if R.get("burst"):
            med = {m: v["median"] for m, v in R["burst"]["per_model"].items()}
            burst = [dict(model=c["model"], inp=c["inp"], out=c["out"], B=round(c["B"], 3), mit=round(c["mit"], 1),
                          mst=round(c["mst"], 1), model_median=round(med[c["model"]], 3)) for c in R["burst"]["cells"]]

    data = dict(burst=burst, pair=dict(model="DeepSeek-R1-Qwen-7B", kind="MIT", c_light=float(caps["1-100_1-100"]),
                          c_heavy=float(caps[HEAVY]), points=pair_pts),
                designs=designs, repeats=repeats)
    name = "animations_template_en.html" if lang == "en" else "animations_template.html"
    tpl = (HERE / name).read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    Path(html_path).write_text(html, encoding="utf-8")
    print("wrote", html_path, len(html) // 1024, "KB,", len(designs), "designs,", len(repeats), "repeat runs")


if __name__ == "__main__":
    main(*sys.argv[1:4])
