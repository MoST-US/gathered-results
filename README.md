# gathered-results

An archive of MoST experiment results gathered through the dashboard, plus two small Python 3
helpers that flatten the nested archive into a single analysis-ready CSV.

Each run is stored as its own `results.csv` (the dashboard uploads them as Base64 payloads through
the GitHub blob API), so comparing runs by hand means opening thousands of files. The scripts walk
the tree and merge those files into one table, tagging every row with the experiment it came from,
the interval-matrix cell it belongs to and its iteration timestamp.

## Repository layout

```
gathered-results/
├── MergeExperimentCsv.py           # merge ONE experiment (all cells × iterations) into one CSV
├── MergeAllCsv.py                  # merge EVERY experiment of the archive into one CSV
└── MIT_MST_results/                # the gathered archive: 3 results sources, 29 experiments, 5180 results.csv
    └── <model>-<gpuType>-<N>gpus/          # results source, e.g. deepseek-ai_DeepSeek-R1-Distill-Qwen-7B-A40-1gpus
        └── <EXPERIMENT_NAME>/              # Experiment_MIT_... / Experiment_MST_... / Experiment_MIX_...
            └── <cell>/                     # interval-matrix cell, e.g. 1-100_1-100 (additive cells: mix_...)
                └── <iteration>/            # YYYY-MM-DD_HH-MM-SS
                    └── results.csv         # one stored run
```

Current sources: `deepseek-ai_DeepSeek-R1-Distill-Qwen-7B-A40-1gpus`,
`google_gemma-7b-A40-1gpus`, `meta-llama_Llama-3.1-8B-Instruct-A40-1gpus`.
`Experiment_MIT_*` / `Experiment_MST_*` experiments hold interval-matrix cells such as
`1-100_1-100`; `Experiment_MIX_*` experiments hold only additive (`mix_...`) cells.

## The scripts

**`MergeExperimentCsv.py`** — merges the iterations of *one* experiment
(`<source>/<EXPERIMENT_NAME>/`) into one CSV: every row keeps its cell name in an `IDENTIFIER`
column and its iteration timestamp in a `DATE` column (taken from the iteration folder name, or
from a `Date`/`Timestamp`/`created_at` column when present). Payloads that are still Base64 are
decoded first, so plain results trees work too. Because the archive mixes `results.csv` files
written with 32/33/34/36 columns, column sets are unioned, not intersected. Additive `mix_...`
cells are skipped unless `--include-additive` is given.

**`MergeAllCsv.py`** — walks the whole archive and calls the module above for every experiment,
adding an `EXPERIMENT_NAME` column (and an optional `RESULTS_SOURCE` column with
`--include-source-column`). Additive cells are included by default, because an `Experiment_MIX_*`
experiment holds nothing else. Experiments that cannot be read are reported in `skipped` instead of
failing the whole merge. The two modules share the same decoding, merge and JSON-summary code —
`MergeAllCsv.py` imports `MergeExperimentCsv.py` and never duplicates it.

Both scripts print a JSON summary and never write inside the results tree: the merged CSV is
written to the working directory (`<EXPERIMENT_NAME>.csv` / `<RESULTS_SCOPE>.csv`) unless
`--output` says otherwise, and `--output -` streams it to stdout.

## Requirements

Python 3 with the standard library only — no dependencies to install.

## Quick start

```powershell
# List the experiments of the archive
python MergeExperimentCsv.py --list

# Merge one experiment -> Experiment_MIT_2026-09-19_17-22-57.csv in the current directory
python MergeExperimentCsv.py "deepseek-ai_DeepSeek-R1-Distill-Qwen-7B-A40-1gpus/Experiment_MIT_2026-09-19_17-22-57"

# Merge every experiment -> MIT_MST_results.csv, oldest rows first, source folder included
python MergeAllCsv.py --sort date --include-source-column

# Pipe the merged CSV somewhere else (the JSON summary then goes to stderr)
python MergeAllCsv.py --output - | Out-File all.csv
```

Run `python MergeExperimentCsv.py --help` / `python MergeAllCsv.py --help` for all options
(`--root`, `--include-additive` / `--exclude-additive`, `--sort folder|date`, `--output`,
`--identifier-column`, `--date-column`, `--include-source-column`, `--list`).
