"""Assemble the static artifact site in docs/ (GitHub Pages root, also browsable offline from Zenodo).

Usage: python analysis/build_site.py [--results analysis/output] [--latex analysis/latex] [--out docs]

Everything in docs/ is self-contained: data are embedded in the pages, d3 is loaded from
docs/vendor/ (no CDN), links are relative, and web fonts degrade to system fonts when offline.
"""
import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CDN_D3 = "https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"

sys.path.insert(0, str(HERE))
import build_animations  # noqa: E402
import build_report  # noqa: E402

INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>SCALE Capacity Analysis</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
/* Layout: one reading column; a key-numbers strip, then the four entry points, then reproduction notes. */
:root { --bg:#f6f7f8; --surface:#fdfdfc; --ink:#111418; --ink-2:#4b5058; --muted:#7d828a; --line:rgba(17,20,24,.10); --accent:#3b3592;
  --f-display:"IBM Plex Sans Condensed","Arial Narrow",system-ui,sans-serif; --f-body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif; --f-mono:"IBM Plex Mono",ui-monospace,Consolas,monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#111316; --surface:#181a1e; --ink:#f2f3f5; --ink-2:#c1c5cc; --muted:#8b9098; --line:rgba(255,255,255,.10); --accent:#a9a3f5; color-scheme:dark; } }
:root[data-theme="dark"] { --bg:#111316; --surface:#181a1e; --ink:#f2f3f5; --ink-2:#c1c5cc; --muted:#8b9098; --line:rgba(255,255,255,.10); --accent:#a9a3f5; color-scheme:dark; }
* { box-sizing:border-box; } html, body { margin:0; }
body { background:var(--bg); color:var(--ink); font:400 16px/1.6 var(--f-body); }
.wrap { max-width:880px; margin:0 auto; padding-inline:20px; padding-block:44px 72px; display:grid; gap:34px; }
h1, h2 { font-family:var(--f-display); margin:0; text-wrap:balance; } h1 { font-size:clamp(2rem,5vw,2.7rem); line-height:1.05; } h2 { font-size:1.35rem; }
p { margin:0; max-width:70ch; } .lede { color:var(--ink-2); font-size:1.08rem; }
.eyebrow { font:500 .74rem/1.2 var(--f-mono); letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }
header { display:grid; gap:12px; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line); border-radius:6px; overflow:hidden; }
.stats div { background:var(--surface); padding:14px 16px; display:grid; gap:2px; } .stats b { font:600 1.5rem/1.1 var(--f-display); } .stats span { font-size:.84rem; color:var(--ink-2); }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; }
.card { display:grid; gap:6px; padding:16px; border:1px solid var(--line); border-radius:6px; background:var(--surface); color:inherit; text-decoration:none; }
.card:hover, .card:focus-visible { border-color:var(--accent); outline:none; } .card b { font-size:1.02rem; } .card span { color:var(--ink-2); font-size:.9rem; }
code, pre { font-family:var(--f-mono); font-size:.88rem; } pre { background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:12px 14px; overflow-x:auto; margin:0; }
ul { margin:0; padding-left:1.2em; color:var(--ink-2); display:grid; gap:4px; } a { color:var(--accent); }
.note { color:var(--muted); font-size:.86rem; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">SCALE · replication artifact · additivity and burst factor</div>
  <h1>Can the capacity of LLM request mixes be predicted?</h1>
  <p class="lede">Analysis of __RUNS__ MoST mix runs (__DESIGNS__ designs) and __PURE__ pure-class runs on three 7–8 B models served on NVIDIA A40 GPUs. It tests whether SCALE's Capacity Units add up when request classes are mixed, and characterises the burst factor MIT / MST that governs burst allowances.</p>
</header>
<div class="stats">
  <div><b>q = __Q__</b><span>estimated combination exponent (harmonic = −1)</span></div>
  <div><b>__BIAS__</b><span>mean bias of mixes versus the harmonic law</span></div>
  <div><b>__BOUNDS__</b><span>runs within the capacity range of their classes</span></div>
  <div><b>B ≈ __BURST__</b><span>median burst factor, practically equal across models</span></div>
</div>
<section style="display:grid;gap:14px">
  <h2>Explore</h2>
  <div class="cards">
    <a class="card" href="report.html"><b>Statistical report</b><span>Frequentist and Bayesian analysis with interactive figures, inference tables and every mix run.</span></a>
    <a class="card" href="animations.html"><b>Animated explanations</b><span>Nine interactive scenes that build the intuition behind the results.</span></a>
    <a class="card" href="animaciones.html"><b>Animaciones (español)</b><span>The same nine scenes in Spanish.</span></a>
    <a class="card" href="latex/preview.pdf"><b>LaTeX assets</b><span>Draft section, tables, figures and macros for the paper, compiled as a preview PDF.</span></a>
  </div>
  <p>Download every LaTeX asset (macros, tables, figures, draft section): <a href="latex-assets.zip">latex-assets.zip</a>.</p>
</section>
<section style="display:grid;gap:12px">
  <h2>Data and reproduction</h2>
  <ul>
    <li>Raw MoST results: <code>MIT_MST_results/</code> in the repository (one <code>results.csv</code> per iteration).</li>
    <li>Analysis outputs: <a href="data/results.json">results.json</a>, <a href="data/mix_frequentist.csv">mix_frequentist.csv</a>, <a href="data/derived.json">derived.json</a>.</li>
    <li>Code and instructions: <code>analysis/README.md</code>.</li>
  </ul>
  <pre>python -m pip install -r analysis/requirements.txt
python analysis/run_all.py            # full pipeline (Bayesian part takes ~15-30 min)
python analysis/run_all.py --skip-bayes   # frequentist part only, a few minutes</pre>
  <p class="note">Built __BUILT__. All pages work offline: open <code>docs/index.html</code> from the archive.</p>
</section>
</div>
</body>
</html>
"""


def localise(html_path):
    p = Path(html_path)
    s = p.read_text(encoding="utf-8")
    s = s.replace(f'<script src="{CDN_D3}"></script>', '<script src="vendor/d3.min.js"></script>')
    # pages are published with the artifact skeleton; add a minimal one for standalone files
    if not s.lstrip().lower().startswith("<!doctype"):
        # templates start with <title>, <link>, <script> and <style>, then the page body
        cut = s.index('<div class="wrap">')
        head, body = s[:cut], s[cut:]
        s = ('<!doctype html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
             '<style>html,body{{margin:0}} img{{max-width:100%}} [hidden]{{display:none!important}}</style>\n'
             ).format(lang="es" if "animaciones" in p.name else "en") + head + "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    p.write_text(s, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(HERE / "output"))
    ap.add_argument("--latex", default=str(HERE / "latex"))
    ap.add_argument("--out", default=str(ROOT / "docs"))
    args = ap.parse_args()
    res, latex, out = Path(args.results), Path(args.latex), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / ".nojekyll").write_text("")
    (out / "vendor").mkdir(exist_ok=True)
    shutil.copy(HERE / "vendor" / "d3.min.js", out / "vendor" / "d3.min.js")

    R = json.loads((res / "results.json").read_text())
    if R.get("bayes"):
        build_report.main(str(res), str(out / "report.html"))
        localise(out / "report.html")
    else:
        print("results.json has no Bayesian part: report.html not rebuilt")
    build_animations.main(str(res), str(out / "animations.html"), "en")
    build_animations.main(str(res), str(out / "animaciones.html"), "es")
    localise(out / "animations.html")
    localise(out / "animaciones.html")

    data = out / "data"
    data.mkdir(exist_ok=True)
    for name in ["results.json", "mix_frequentist.csv"]:
        shutil.copy(res / name, data / name)
    if (latex / "derived.json").exists():
        shutil.copy(latex / "derived.json", data / "derived.json")

    # LaTeX assets: a browsable copy and a zip for the paper repository
    dst = out / "latex"
    if dst.exists():
        shutil.rmtree(dst)
    keep = [p for p in latex.rglob("*") if p.is_file() and p.suffix in {".tex", ".pdf"}]
    for p in keep:
        q = dst / p.relative_to(latex)
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p, q)
    with zipfile.ZipFile(out / "latex-assets.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in keep:
            z.write(p, Path("scale-latex") / p.relative_to(latex))

    f, b, bu = R["freq"], R.get("bayes"), R["burst"]
    import math
    q = b["free"]["q"]["median"] if b else f["q_profile"]["q_hat"]
    bias = b["harmonic"]["delta0"]["median"] if b else f["tests"]["H"]["all"]["mean"]
    burst_val = bu["overall"]["median"]  # same value as \scaleBurstMedian in the LaTeX macros
    from datetime import date
    html = (INDEX.replace("__RUNS__", f"{f['n_mix_runs']}").replace("__DESIGNS__", f"{f['n_design_units']}")
            .replace("__PURE__", f"{R['n_units'] - f['n_mix_runs']}").replace("__Q__", f"{q:.2f}".replace("-", "−"))
            .replace("__BIAS__", f"{100 * (math.exp(bias) - 1):+.1f} %".replace("-", "−"))
            .replace("__BOUNDS__", f"{f['bounds']['minmax'][0]}/{f['bounds']['minmax'][1]}")
            .replace("__BURST__", f"{burst_val:.1f}").replace("__BUILT__", date.today().isoformat()))
    (out / "index.html").write_text(html, encoding="utf-8")
    print("site written to", out)


if __name__ == "__main__":
    main()
