"""Run the whole artifact pipeline: analysis -> LaTeX assets -> static site.

Usage (from the repository root):
  python analysis/run_all.py                 # full run (frequentist + Bayesian, ~15-30 min on 4 cores)
  python analysis/run_all.py --skip-bayes    # frequentist only (the report page then keeps its last build)
  python analysis/run_all.py --reuse         # skip the analysis, rebuild LaTeX and site from analysis/output

Outputs: analysis/output/ (results), analysis/latex/ (tables, figures, macros, draft section, preview.pdf
when pdflatex is available) and docs/ (site for GitHub Pages and offline browsing).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def step(title, args, cwd=None):
    print(f"\n== {title}", flush=True)
    r = subprocess.run([sys.executable, *args], cwd=cwd or HERE.parent)
    if r.returncode:
        sys.exit(f"step failed: {title}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-bayes", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="reuse analysis/output instead of recomputing it")
    ap.add_argument("--draws", type=int, default=600)
    args = ap.parse_args()
    out = HERE / "output"

    if not args.reuse:
        cmd = [str(HERE / "additivity_analysis.py"), "--out", str(out), "--draws", str(args.draws)]
        if args.skip_bayes:
            cmd.append("--skip-bayes")
        step("analysis", cmd)
    step("LaTeX assets", [str(HERE / "latex_export.py"), "--results", str(out), "--out", str(HERE / "latex")])
    if shutil.which("pdflatex"):
        print("\n== LaTeX preview")
        for _ in range(2):
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "preview.tex"],
                           cwd=HERE / "latex", stdout=subprocess.DEVNULL)
    else:
        print("\n(pdflatex not found: preview.pdf not rebuilt)")
    step("English animations template", [str(HERE / "translate_animations.py")])
    step("site", [str(HERE / "build_site.py"), "--results", str(out)])
    print("\nDone. Open docs/index.html")


if __name__ == "__main__":
    main()
