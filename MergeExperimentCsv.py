"""Merge the per-iteration results.csv files of one gathered experiment into a single CSV.

A gathered results archive keeps every run under
``<results scope>/<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>/`` and, inside it, one folder per
interval-matrix cell (the sub-experiment, for example ``1-100_1-100``) holding one folder per
iteration (``YYYY-MM-DD_HH-MM-SS``) with its own ``results.csv``:

    MIT_MST_results/deepseek-ai_...-A40-1gpus/Experiment_MIT_2026-09-19_17-22-57/
        1-100_1-100/2026-09-17_15-36-12/results.csv

Given that experiment path this module returns one unified CSV in which every row keeps the
sub-experiment identity in an ``IDENTIFIER`` column and the iteration timestamp in a ``DATE``
column, exactly like ``MergeResultsCsv.py`` does for the live ``results/`` tree. The path contract
is the one produced by the dashboard uploader (``github-results-uploader.mjs``):

    <results path>/<model>-<gpuType>-<N>gpus/<experimentFolder>/
        <sub-experiment>/<iteration>/results.csv

Two format details separate this archive from a live ``results/`` tree:

* the stored ``results.csv`` payloads are Base64 text (the dashboard uploads them through the
  GitHub blob API), so they are decoded before they are parsed as CSV. Payloads that are already
  plain CSV are read unchanged, so the same script also works on a plain results tree;
* the experiment folder sits one level below the results scope, so ``MergeExperimentCsv.py``'s
  positional argument plays the role of ``MergeResultsCsv.py --root`` and the cells play the role
  of its experiments.

Everything else mirrors ``MergeResultsCsv.py``: the same ``IDENTIFIER`` / ``DATE`` contract, the
same union-of-columns merge (so archives whose ``results.csv`` gained columns over time still merge
cleanly) and the same JSON summary.

Run ``python MergeExperimentCsv.py --help`` for the options.
"""
import argparse
import base64
import binascii
import csv
import io
import json
import re
import sys
from pathlib import Path

IDENTIFIER_COLUMN = "IDENTIFIER"
DATE_COLUMN = "DATE"
RESULTS_FILENAME = "results.csv"
# Results scope that holds the `<model>-<gputype>-<gpusused>` folders in this archive.
DEFAULT_RESULTS_ROOT = "MIT_MST_results"
# Additive (`WORKLOAD_MIXES`) folders are named `mix_...` and are not interval-matrix cells.
ADDITIVE_SUB_EXPERIMENT_PREFIX = "mix_"
# Mirrors DATE_KEYS in the dashboard (src/App.jsx): the first date-like column holding a value
# wins, otherwise the iteration folder name (`YYYY-MM-DD_HH-MM-SS`) is used.
DATE_COLUMN_CANDIDATES = ("Date", "date", "Timestamp", "timestamp", "created_at")
# Stored payloads are the Base64 blob the dashboard commits through the GitHub blob API. A plain
# CSV always carries commas, which are outside this alphabet, so the two forms never collide.
BASE64_PAYLOAD_PATTERN = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
SORT_MODES = ("folder", "date")


class MergeResultsError(Exception):
    """Raised when the merged CSV cannot be built."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def decode_results_payload(raw_bytes):
    """Return the CSV text of one stored ``results.csv`` payload.

    Base64 payloads (gathered archives) are decoded; anything else is returned as text, so plain
    ``results.csv`` files of a live results tree read identically.
    """
    text = raw_bytes.decode("utf-8-sig")
    compact = "".join(text.split())
    if (
        compact
        and "," not in compact
        and len(compact) % 4 == 0
        and BASE64_PAYLOAD_PATTERN.match(compact)
    ):
        try:
            return base64.b64decode(compact, validate=True).decode("utf-8-sig")
        except (binascii.Error, UnicodeDecodeError):
            pass
    return text


def read_results_rows(csv_path):
    """Read the header and the non-empty data rows of one stored results.csv."""
    raw_bytes = Path(csv_path).read_bytes()
    reader = csv.reader(io.StringIO(decode_results_payload(raw_bytes)))
    try:
        fieldnames = [str(name).strip() for name in next(reader)]
    except StopIteration:
        return [], []
    rows = [row for row in reader if any(str(value).strip() != "" for value in row)]
    return fieldnames, rows


def list_sub_experiment_names(experiment_dir, include_additive=False):
    """Sub-experiment (interval-matrix cell) folders of one experiment, sorted by name.

    Additive (``mix_...``) folders are skipped unless ``include_additive`` is set.
    """
    try:
        names = sorted(entry.name for entry in experiment_dir.iterdir() if entry.is_dir())
    except OSError as error:
        raise MergeResultsError(
            'Unable to read experiment "%s": %s' % (experiment_dir, error), "EXPERIMENT_NOT_FOUND"
        )

    if include_additive:
        return names
    return [
        name for name in names if not name.lower().startswith(ADDITIVE_SUB_EXPERIMENT_PREFIX)
    ]


def list_iteration_csvs(sub_experiment_dir):
    """``(iteration folder name, results.csv path)`` pairs of one cell, ordered by name."""
    try:
        iteration_names = sorted(
            entry.name for entry in sub_experiment_dir.iterdir() if entry.is_dir()
        )
    except OSError:
        return []

    iteration_csvs = []
    for name in iteration_names:
        candidate = sub_experiment_dir / name / RESULTS_FILENAME
        if candidate.is_file():
            iteration_csvs.append((name, candidate))
    return iteration_csvs


def resolve_iteration_date(record, iteration_name):
    """Timestamp of an iteration: first date-like source column, else the iteration folder name."""
    for candidate in DATE_COLUMN_CANDIDATES:
        value = record.get(candidate)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return iteration_name


def resolve_experiment_path(experiment, root=DEFAULT_RESULTS_ROOT):
    """Directory holding one ``<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>`` path.

    An existing absolute or relative path is used as-is, otherwise it is resolved against ``root``.
    """
    raw = str(experiment or "").strip().strip("/\\")
    if not raw:
        raise MergeResultsError("No experiment path given.", "EXPERIMENT_NOT_FOUND")

    candidates = []
    direct = Path(raw)
    if direct.is_dir():
        candidates.append(direct)
    if root not in (None, ""):
        candidates.append(Path(root) / raw)

    for candidate in candidates:
        if candidate.is_dir():
            return candidate

    tried = ", ".join('"%s"' % candidate for candidate in candidates)
    raise MergeResultsError(
        'Experiment folder "%s" not found (tried %s).' % (raw, tried or '"%s"' % raw),
        "EXPERIMENT_NOT_FOUND",
    )


def list_experiment_paths(root=DEFAULT_RESULTS_ROOT):
    """Every ``<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>`` path of a results scope, sorted."""
    root_path = Path(root)
    if not root_path.is_dir():
        raise MergeResultsError('Results root "%s" does not exist.' % root, "ROOT_NOT_FOUND")

    paths = []
    for model_dir in sorted(entry for entry in root_path.iterdir() if entry.is_dir()):
        for experiment_dir in sorted(entry for entry in model_dir.iterdir() if entry.is_dir()):
            paths.append("%s/%s" % (model_dir.name, experiment_dir.name))
    return paths


def default_output_path(experiment):
    """``<EXPERIMENT_NAME>.csv`` in the working directory (never inside the results tree)."""
    name = Path(str(experiment or "").strip().rstrip("/\\")).name
    return "%s.csv" % (name or "experiment")


def merge_experiment_csv(
    experiment,
    root=DEFAULT_RESULTS_ROOT,
    include_additive=False,
    sort_mode="folder",
    identifier_column=IDENTIFIER_COLUMN,
    date_column=DATE_COLUMN,
):
    """Merge every ``<cell>/<iteration>/results.csv`` of one experiment.

    Returns ``(columns, rows, summary)``: ``columns`` is the merged header (the identifier and the
    date column first, then the union of the source columns in first-seen order, so archives whose
    results.csv gained columns over time still merge cleanly) and ``rows`` are dicts ready to be
    written. The identifier/date columns are always (re)built by this module, which keeps the
    sub-experiment folder name (the interval-matrix cell, for example ``1-100_1-100``) and the
    iteration timestamp next to every merged row.

    ``sort_mode`` is ``"folder"`` (cells, then iterations -- the order of ``MergeResultsCsv.py``) or
    ``"date"`` (chronological across cells).
    """
    if sort_mode not in SORT_MODES:
        raise MergeResultsError(
            'Unknown sort mode "%s" (expected %s).' % (sort_mode, " or ".join(SORT_MODES)),
            "INVALID_SORT",
        )

    experiment_dir = resolve_experiment_path(experiment, root)
    selected = list_sub_experiment_names(experiment_dir, include_additive=include_additive)

    source_columns = []
    rows = []
    used_sub_experiments = []
    skipped = []
    iteration_count = 0

    for sub_experiment in selected:
        sub_experiment_dir = experiment_dir / sub_experiment
        if not sub_experiment_dir.is_dir():
            skipped.append("%s: sub-experiment folder not found" % sub_experiment)
            continue

        iteration_csvs = list_iteration_csvs(sub_experiment_dir)
        if not iteration_csvs:
            skipped.append("%s: no iteration results.csv found" % sub_experiment)
            continue

        rows_before = len(rows)
        for iteration_name, csv_path in iteration_csvs:
            try:
                fieldnames, csv_rows = read_results_rows(csv_path)
            except (OSError, ValueError, csv.Error) as error:
                skipped.append("%s/%s: %s" % (sub_experiment, iteration_name, error))
                continue

            for name in fieldnames:
                if name and name not in source_columns:
                    source_columns.append(name)

            for csv_row in csv_rows:
                record = {}
                for index, name in enumerate(fieldnames):
                    record[name] = csv_row[index] if index < len(csv_row) else ""
                record[identifier_column] = sub_experiment
                record[date_column] = resolve_iteration_date(record, iteration_name)
                rows.append(record)

            iteration_count += 1

        if len(rows) > rows_before:
            used_sub_experiments.append(sub_experiment)

    if not rows:
        raise MergeResultsError(
            'No results.csv files found under "%s".' % experiment_dir, "NO_RESULTS_FOUND"
        )

    # The folder walk is already chronological inside one cell; "date" interleaves the cells.
    if sort_mode == "date":
        rows.sort(key=lambda row: str(row.get(date_column, "")))

    columns = [identifier_column, date_column]
    for name in source_columns:
        if name not in columns:
            columns.append(name)

    # Rows written with an older/narrower header get '' instead of a missing key, so every merged
    # row exposes the full union of the source columns.
    for row in rows:
        for name in columns:
            row.setdefault(name, "")

    summary = {
        "experiment": str(experiment_dir).replace("\\", "/"),
        "rows": len(rows),
        "iterations": iteration_count,
        "sub_experiments": used_sub_experiments,
        "columns": columns,
        "skipped": skipped,
    }
    return columns, rows, summary


def _write_rows(handle, columns, rows):
    """Write the merged header and rows, keeping the multiline/quoted fields of results.csv."""
    writer = csv.DictWriter(
        handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)


def write_merged_csv(columns, rows, output=None):
    """Write the merged table to ``output``; ``-``/``None`` streams it to stdout.

    Returns the destination as a string (``<stdout>`` when the CSV went to stdout).
    """
    if output in (None, "", "-"):
        _write_rows(sys.stdout, columns, rows)
        return "<stdout>"

    destination = Path(output)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8", newline="") as handle:
            _write_rows(handle, columns, rows)
    except OSError as error:
        raise MergeResultsError(
            'Unable to write "%s": %s' % (destination, error), "WRITE_FAILED"
        )
    return str(destination)


def run_merge_experiment(
    experiment,
    root=DEFAULT_RESULTS_ROOT,
    include_additive=False,
    sort_mode="folder",
    output=None,
    identifier_column=IDENTIFIER_COLUMN,
    date_column=DATE_COLUMN,
):
    """Build the merged CSV, write it and return the JSON serialisable summary.

    ``output`` of ``None``/``""`` writes ``<EXPERIMENT_NAME>.csv`` in the working directory; ``-``
    streams the CSV to stdout, as ``MergeResultsCsv.py`` does.
    """
    columns, rows, summary = merge_experiment_csv(
        experiment,
        root=root,
        include_additive=include_additive,
        sort_mode=sort_mode,
        identifier_column=identifier_column,
        date_column=date_column,
    )
    destination = output if output not in (None, "") else default_output_path(experiment)
    summary["output"] = write_merged_csv(columns, rows, destination)
    return summary


def _main(argv=None):
    parser = argparse.ArgumentParser(
        prog="MergeExperimentCsv",
        description=(
            "Merge the per-iteration results.csv files of one gathered experiment "
            "(<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>) into one CSV."
        ),
    )
    parser.add_argument(
        "experiment",
        nargs="?",
        default="",
        help=(
            "Experiment path, for example "
            "deepseek-ai_DeepSeek-R1-Distill-Qwen-7B-A40-1gpus/Experiment_MIT_2026-09-19_17-22-57 "
            "(an existing absolute path is used as-is)."
        ),
    )
    parser.add_argument(
        "--root",
        default=DEFAULT_RESULTS_ROOT,
        help="Results scope holding the <model>-<gputype>-<gpusused> folders (default: %s)."
        % DEFAULT_RESULTS_ROOT,
    )
    parser.add_argument(
        "--include-additive",
        action="store_true",
        help="Also merge the additive (mix_...) sub-experiment folders.",
    )
    parser.add_argument(
        "--sort",
        dest="sort_mode",
        choices=SORT_MODES,
        default="folder",
        help=(
            "Row order: 'folder' = cells then iterations, 'date' = chronological "
            "(default: folder)."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Destination CSV file (default: <EXPERIMENT_NAME>.csv in the working directory), "
            "or '-' to stream the CSV to stdout."
        ),
    )
    parser.add_argument(
        "--identifier-column",
        default=IDENTIFIER_COLUMN,
        help="Column holding the sub-experiment name (default: %s)." % IDENTIFIER_COLUMN,
    )
    parser.add_argument(
        "--date-column",
        default=DATE_COLUMN,
        help="Column holding the iteration timestamp (default: %s)." % DATE_COLUMN,
    )
    parser.add_argument(
        "--list",
        dest="list_experiments",
        action="store_true",
        help="Print the experiment paths of the results scope and exit.",
    )

    args = parser.parse_args(argv)

    if args.list_experiments:
        try:
            experiment_paths = list_experiment_paths(args.root)
        except MergeResultsError as error:
            print(json.dumps({"error": error.message, "code": error.code}))
            return 1
        for path in experiment_paths:
            print(path)
        return 0

    if not args.experiment:
        parser.error("the experiment path is required (or use --list)")

    try:
        summary = run_merge_experiment(
            experiment=args.experiment,
            root=args.root,
            include_additive=args.include_additive,
            sort_mode=args.sort_mode,
            output=args.output,
            identifier_column=args.identifier_column,
            date_column=args.date_column,
        )
    except MergeResultsError as error:
        print(json.dumps({"error": error.message, "code": error.code}))
        return 1
    except Exception as error:
        print(json.dumps({"error": str(error), "code": "UNKNOWN_ERROR"}))
        return 1

    # Streamed CSVs own stdout, so the JSON summary moves to stderr in that case.
    summary_stream = sys.stderr if args.output == "-" else sys.stdout
    print(json.dumps(summary), file=summary_stream)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
