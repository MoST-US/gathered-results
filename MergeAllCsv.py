"""Merge every results.csv of a gathered results scope into a single CSV.

``MergeExperimentCsv.py`` unifies the iterations of *one* experiment
(``<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>/``); this module walks the whole scope, so the
merged table holds every experiment, every interval-matrix cell (``IDENTIFIER``) and every
iteration (``DATE``) of the archive:

    <results scope>/<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>/
        <cell>/<iteration>/results.csv

One column is added on top of the ``MergeExperimentCsv.py`` contract: ``EXPERIMENT_NAME`` records
the experiment folder a row came from. That single provenance column is enough because the same
cell name (for example ``1-100_1-100``) appears in every experiment, while experiment folder names
are unique across the scope (checked against the current archive); ``--include-source-column``
additionally stores the ``<model>-<gputype>-<gpusused>`` folder (``RESULTS_SOURCE``) for archives in
which two models could reuse one experiment name.

Everything else is inherited from ``MergeExperimentCsv.py``, which is imported (never duplicated) as
a library: the same Base64-or-plain payload decoding, the same ``IDENTIFIER`` / ``DATE`` contract,
the same union-of-columns merge -- needed here even more than there, because this archive mixes four
``results.csv`` layouts (32/33/34/36 columns) -- and the same JSON summary style.

Additive (``mix_...``) cells are included by default, since the point of this module is the whole
archive: an ``Experiment_MIX_...`` experiment holds only ``mix_...`` cells and would otherwise be
dropped entirely (12 of the 29 experiments of the current archive, 1104 of its 5180 rows). Pass
``--exclude-additive`` to leave them out.

Run ``python MergeAllCsv.py --help`` for the options.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

# The sibling module sits next to this one; adding the script directory to ``sys.path`` keeps the
# import working when the script is started from another working directory.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import MergeExperimentCsv as experiment_merge

# Column holding the experiment folder (``Experiment_<TYPE>_<YYYY-MM-DD_HH-MM-SS>``) a row came
# from: the provenance column this module adds to the ``MergeExperimentCsv.py`` contract.
EXPERIMENT_NAME_COLUMN = "EXPERIMENT_NAME"
# Optional second provenance column holding the ``<model>-<gputype>-<gpusused>`` folder (the
# dashboard calls those folders "results sources").
SOURCE_COLUMN = "RESULTS_SOURCE"
# Results scope holding the `<model>-<gputype>-<gpusused>` folders, shared with the sibling module.
DEFAULT_RESULTS_ROOT = experiment_merge.DEFAULT_RESULTS_ROOT
IDENTIFIER_COLUMN = experiment_merge.IDENTIFIER_COLUMN
DATE_COLUMN = experiment_merge.DATE_COLUMN
SORT_MODES = experiment_merge.SORT_MODES
MergeResultsError = experiment_merge.MergeResultsError


def list_scope_experiments(root=DEFAULT_RESULTS_ROOT):
    """Every ``<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>`` path of a scope, sorted.

    Delegates to ``MergeExperimentCsv.list_experiment_paths`` so both modules agree on what an
    experiment is (and on the ``ROOT_NOT_FOUND`` error raised for a missing scope).
    """
    return experiment_merge.list_experiment_paths(root)


def default_output_path(root=DEFAULT_RESULTS_ROOT):
    """``<RESULTS_SCOPE>.csv`` in the working directory (never inside the results tree)."""
    name = Path(str(root or "").strip().rstrip("/\\")).name
    return "%s.csv" % (name or "results")


def merge_all_csv(
    root=DEFAULT_RESULTS_ROOT,
    include_additive=True,
    sort_mode="folder",
    identifier_column=IDENTIFIER_COLUMN,
    date_column=DATE_COLUMN,
    experiment_column=EXPERIMENT_NAME_COLUMN,
    source_column=None,
):
    """Merge every ``<experiment>/<cell>/<iteration>/results.csv`` of one results scope.

    Returns ``(columns, rows, summary)`` with the contract of
    ``MergeExperimentCsv.merge_experiment_csv``: the provenance columns first (``experiment_column``,
    ``identifier_column``, ``date_column`` and, when requested, ``source_column``), then the union of
    the source columns in first-seen order, so archives whose ``results.csv`` changed shape over time
    still merge cleanly. Every row keeps the experiment folder name of the file it came from, the
    cell it belongs to and its iteration timestamp.

    ``include_additive`` is ``True`` by default: an additive (``Experiment_MIX_...``) experiment
    holds only ``mix_...`` cells, so excluding them would drop whole experiments. ``sort_mode`` is
    ``"folder"`` (experiments, then cells, then iterations) or ``"date"`` (chronological across the
    whole scope).

    Experiments that cannot be read are collected in ``summary["skipped"]`` instead of aborting the
    merge; only a scope that yields no row at all raises ``NO_RESULTS_FOUND``.
    """
    if sort_mode not in SORT_MODES:
        raise MergeResultsError(
            'Unknown sort mode "%s" (expected %s).' % (sort_mode, " or ".join(SORT_MODES)),
            "INVALID_SORT",
        )
    if not str(root or "").strip():
        raise MergeResultsError("No results scope given.", "ROOT_NOT_FOUND")

    experiment_paths = list_scope_experiments(root)

    reserved = [experiment_column, identifier_column, date_column]
    if source_column:
        reserved.append(source_column)

    source_columns = []
    rows = []
    used_experiments = []
    skipped = []
    rows_by_experiment = {}
    iteration_count = 0

    for experiment_path in experiment_paths:
        try:
            columns, experiment_rows, experiment_summary = experiment_merge.merge_experiment_csv(
                experiment_path,
                root=root,
                include_additive=include_additive,
                sort_mode="folder",
                identifier_column=identifier_column,
                date_column=date_column,
            )
        except MergeResultsError as error:
            # Missing/empty experiments (and, with --exclude-additive, the additive-only ones) are
            # reported instead of failing the whole merge.
            skipped.append("%s: %s" % (experiment_path, error.message))
            continue
        except (OSError, ValueError, csv.Error) as error:
            skipped.append("%s: %s" % (experiment_path, error))
            continue

        for name in columns:
            if name and name not in reserved and name not in source_columns:
                source_columns.append(name)

        experiment_name = Path(experiment_path).name
        for row in experiment_rows:
            row[experiment_column] = experiment_name
            if source_column:
                row[source_column] = Path(experiment_path).parent.name
            rows.append(row)

        used_experiments.append(experiment_path)
        rows_by_experiment[experiment_path] = len(experiment_rows)
        iteration_count += experiment_summary.get("iterations", 0)

    if not rows:
        raise MergeResultsError(
            'No results.csv files found under "%s".' % root, "NO_RESULTS_FOUND"
        )

    # The folder walk of one experiment is already chronological; "date" interleaves them all (the
    # sort is stable, so rows sharing a timestamp keep their experiment order).
    if sort_mode == "date":
        rows.sort(key=lambda row: str(row.get(date_column, "")))

    columns = [experiment_column, identifier_column, date_column]
    if source_column:
        columns.append(source_column)
    for name in source_columns:
        if name not in columns:
            columns.append(name)

    # Rows written with an older/narrower header get '' instead of a missing key, so every merged
    # row exposes the full union of the source columns.
    for row in rows:
        for name in columns:
            row.setdefault(name, "")

    summary = {
        "root": str(root).replace("\\", "/"),
        "rows": len(rows),
        "experiments": used_experiments,
        "experiment_count": len(used_experiments),
        "iterations": iteration_count,
        "rows_by_experiment": rows_by_experiment,
        "columns": columns,
        "skipped": skipped,
    }
    return columns, rows, summary


def run_merge_all(
    root=DEFAULT_RESULTS_ROOT,
    include_additive=True,
    sort_mode="folder",
    output=None,
    identifier_column=IDENTIFIER_COLUMN,
    date_column=DATE_COLUMN,
    experiment_column=EXPERIMENT_NAME_COLUMN,
    source_column=None,
):
    """Build the merged CSV, write it and return the JSON serialisable summary.

    ``output`` of ``None``/``""`` writes ``<RESULTS_SCOPE>.csv`` in the working directory; ``-``
    streams the CSV to stdout, as ``MergeExperimentCsv.py`` does.
    """
    columns, rows, summary = merge_all_csv(
        root=root,
        include_additive=include_additive,
        sort_mode=sort_mode,
        identifier_column=identifier_column,
        date_column=date_column,
        experiment_column=experiment_column,
        source_column=source_column,
    )
    destination = output if output not in (None, "") else default_output_path(root)
    summary["output"] = experiment_merge.write_merged_csv(columns, rows, destination)
    return summary


def _main(argv=None):
    parser = argparse.ArgumentParser(
        prog="MergeAllCsv",
        description=(
            "Merge every results.csv of a gathered results scope "
            "(<model>-<gputype>-<gpusused>/<EXPERIMENT_NAME>/<cell>/<iteration>) into one CSV, "
            "tagging every row with its EXPERIMENT_NAME."
        ),
    )
    parser.add_argument(
        "--root",
        default=DEFAULT_RESULTS_ROOT,
        help="Results scope holding the <model>-<gputype>-<gpusused> folders (default: %s)."
        % DEFAULT_RESULTS_ROOT,
    )
    parser.add_argument(
        "--exclude-additive",
        action="store_true",
        help=(
            "Leave the additive (mix_...) cells out; an Experiment_MIX_... experiment holds only "
            "such cells, so it is skipped entirely."
        ),
    )
    parser.add_argument(
        "--sort",
        dest="sort_mode",
        choices=SORT_MODES,
        default="folder",
        help=(
            "Row order: 'folder' = experiments then cells then iterations, 'date' = chronological "
            "across the whole scope (default: folder)."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Destination CSV file (default: <RESULTS_SCOPE>.csv in the working directory), "
            "or '-' to stream the CSV to stdout."
        ),
    )
    parser.add_argument(
        "--experiment-column",
        default=EXPERIMENT_NAME_COLUMN,
        help="Column holding the experiment folder name (default: %s)." % EXPERIMENT_NAME_COLUMN,
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
        "--include-source-column",
        action="store_true",
        help="Also add the <model>-<gputype>-<gpusused> folder a row came from.",
    )
    parser.add_argument(
        "--source-column",
        default=None,
        help=(
            "Name of that optional results-source column (implies --include-source-column; "
            "default: %s)." % SOURCE_COLUMN
        ),
    )
    parser.add_argument(
        "--list",
        dest="list_experiments",
        action="store_true",
        help="Print the experiment paths of the results scope and exit.",
    )

    args = parser.parse_args(argv)

    source_column = None
    if args.include_source_column or args.source_column:
        source_column = args.source_column or SOURCE_COLUMN

    if args.list_experiments:
        try:
            experiment_paths = list_scope_experiments(args.root)
        except MergeResultsError as error:
            print(json.dumps({"error": error.message, "code": error.code}))
            return 1
        for path in experiment_paths:
            print(path)
        return 0

    try:
        summary = run_merge_all(
            root=args.root,
            include_additive=not args.exclude_additive,
            sort_mode=args.sort_mode,
            output=args.output,
            identifier_column=args.identifier_column,
            date_column=args.date_column,
            experiment_column=args.experiment_column,
            source_column=source_column,
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
