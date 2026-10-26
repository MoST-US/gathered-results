# SCALE capacity analysis: additivity and burst factor

Replication package for the evaluation of Capacity Units in the SCALE paper (*Making the most of
On-Premise LLMaaS with SCALE*, ICSOC 2026). It answers two questions with the MoST measurements of
this repository:

- **Additivity (RQ3).** Do the Capacity Units of different request classes add up when classes are
  mixed? SCALE's accounting, K_r = SK_max / MST_r with Σ K ≤ SK_max, predicts that a mix with class
  shares p_i has capacity C_mix = 1 / Σ (p_i / C_i), the weighted harmonic mean of the class
  capacities.
- **Burst factor (RQ4).** B_r = MIT_r / MST_r is how many times its sustainable (30-minute) rate a
  request class withstands during a 2-minute burst. SCALE prices requests with sustainable units and
  keeps instantaneous capacity as a safety threshold; both price classes the same way only if B_r is
  constant.

Browse the results at the published site (`docs/`, see *Publishing* below) or open
`docs/index.html` locally.

## Main findings

| | Result |
| --- | --- |
| Combination law | Harmonic: q = −0.96 (95 % CrI −1.02 to −0.88); geometric and arithmetic laws clearly worse |
| Bias of mixes | −5.5 % on average (90 % CrI −9.9 % to −1.0 %), practically equivalent to 0 within ±10 % |
| Boundedness | 294 of 301 runs lie between the capacities of their slowest and fastest class |
| MIT vs MST | Same law and mean bias; individual predictions twice as precise in MIT (90 % band ±15 % vs ±39 %) |
| Heaviest class | 600–1000 in / 1000–1500 out breaks additivity, in a model-dependent way |
| Stability | Repeated runs differ by < 2 %; departures are design-specific, not noise |
| Burst factor | ≈ 3.5 for every model (pairwise ratios within 3.5 % of 1); 77 % of classes within ±15 %; short answers +13 % |

The figures quoted in the paper come from `latex/macros.tex`, which is regenerated with the
results, so text and data cannot drift apart.

## Layout

```
analysis/
├── run_all.py                  # one command: analysis -> LaTeX assets -> site
├── additivity_analysis.py      # data loading, frequentist and Bayesian additivity analysis
├── burst_analysis.py           # burst factor B = MIT/MST (frequentist and Bayesian)
├── latex_export.py             # macros, tables, figures, draft section for the paper
├── build_report.py             # statistical report (HTML, interactive)
├── build_animations.py         # didactic animations (HTML, English and Spanish)
├── translate_animations.py     # derives the English animations template from the Spanish one
├── build_site.py               # assembles docs/ (GitHub Pages root, offline-capable)
├── report_template.html, animations_template.html, animations_template_en.html
├── vendor/d3.min.js            # d3 v7.9.0 (ISC licence), so that the pages work offline
├── requirements.txt            # pinned versions
├── output/                     # results.json, mix_frequentist.csv, run.log
├── latex/                      # macros.tex, tables/, figures/, section_additivity_burst.tex, preview.pdf
└── INTERPRETACION.md           # plain-language interpretation (Spanish, for the research group)
docs/                           # published site: index, report, animations, LaTeX assets, data
```

## Reproducing

Requirements: Python ≥ 3.12 (results were produced with 3.14) and, optionally, `pdflatex` for the
LaTeX preview.

```bash
python -m venv .venv && . .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r analysis/requirements.txt
python analysis/run_all.py                # full pipeline, ~15-30 min on 4 cores
python analysis/run_all.py --skip-bayes   # frequentist part only, a few minutes
python analysis/run_all.py --reuse        # rebuild LaTeX assets and site from analysis/output
```

On Windows, create the virtual environment in a short path (for example `C:\venvs\scale`): pip fails
on long paths unless Windows long-path support is enabled.

The Bayesian part uses NUTS with 4 chains × 600 draws and fixed seeds. Re-runs on other platforms
give the same conclusions; the last digit of some posterior summaries may change. Convergence
diagnostics are written to `output/run.log` and `output/results.json` (`bayes.diagnostics`).

### Data processing notes

- Each MoST search run (cell or mix, one experiment folder) is a unit; its capacity is latent and
  observed only through pass/fail verdicts at the probed rates.
- **Repeated runs** of a design are kept and modelled as runs nested in designs (design effect plus
  run effect); frequentist tests take the design as the unit.
- **Exact copies**: 114 mix folders are byte-identical copies of another run (same iteration
  timestamps and `results.csv`, stored under a second folder name or copied into a later
  experiment). They are counted once.
- The Bayesian additivity model is fitted in two stages: pure-class capacities from pure runs only,
  then the mixes with those capacities fixed and their uncertainty propagated (a "cut" that keeps a
  few extreme mixes from distorting the pure-class estimates).

## Using the LaTeX assets in the paper

Copy `analysis/latex/` (or unzip `docs/latex-assets.zip`) next to the paper and add to the
preamble:

```latex
\usepackage{booktabs,multirow,graphicx,xspace,amsmath}
\input{latex/macros}       % \scaleQHatBayes, \scaleBurstMedian, ... (115 constants)
```

Then `\input{latex/section_additivity_burst}` for the draft subsections, or use the tables
(`\input{latex/tables/tab_laws}` inside a `table` environment) and figures
(`\includegraphics{latex/figures/fig_burst}`) individually. Paths inside the draft section are
relative to `latex/`; adjust them, or set `\graphicspath`, when the files live elsewhere.
`preview.tex` compiles everything with the LNCS class. The draft cites `TODO-denning-buzen` as a
placeholder for the operational-analysis reference.

## Publishing

**GitHub Pages.** The site is the `docs/` folder, built locally with `python analysis/run_all.py`
and committed. `.github/workflows/artifact.yml` publishes it on every push to `main` that changes
`docs/` (or by hand: *Actions → artifact → Run workflow*). Its checkout is sparse, so only `docs/`
is downloaded and the ~20 GB of measurement data never are. Enable it once in *Settings → Pages →
Build and deployment → Source: GitHub Actions*. Do not use *Deploy from a branch*: that mode clones
the whole repository.

**Zenodo.** Every page works from `file://`, so an archive of the repository is a complete
artifact. Note that the repository tracks about 20 GB of request-level files
(`MIT_MST_results/**/results_from_json.csv`); the analysis only needs the 1 KB `results.csv`
summaries. Two options:

1. *GitHub integration*: enable the repository in Zenodo and publish a GitHub release; Zenodo
   archives the release and reads `.zenodo.json`. With ~20 GB of tracked data the release archive is
   large and may be slow or fail to transfer.
2. *Manual upload (recommended)*: upload two files to one Zenodo record, a small archive with the
   code, `docs/`, `analysis/` and the `results.csv` summaries (enough to reproduce everything), and
   a separate archive with the request-level `results_from_json.csv` files. For example:

   ```bash
   git ls-files | grep -v results_from_json.csv | zip -@ scale-artifact.zip
   git ls-files | grep results_from_json.csv | zip -@ scale-request-level-data.zip
   ```

Citation metadata is in `CITATION.cff`. Keep the deposit anonymous while the paper is under
double-blind review (Zenodo allows restricted or anonymous records; complete the authors and the
licence for the camera-ready version).
