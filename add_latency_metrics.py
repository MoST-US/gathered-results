"""Add request-latency summary metrics to every results.csv below a directory.

Usage:
    python add_latency_metrics.py
    python add_latency_metrics.py path\to\results
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import statistics
import tempfile
from pathlib import Path
from typing import Iterable


LATENCY_COLUMN = "request_duration_ms"
METRIC_COLUMNS = (
    "latency_count",
    "latency_mean_ms",
    "latency_min_ms",
    "latency_max_ms",
    "latency_q1_mean_ms",
    "latency_q2_mean_ms",
    "latency_q3_mean_ms",
    "latency_q4_mean_ms",
    "latency_median_ms",
    "latency_p95_ms",
    "latency_p99_ms",
    "latency_stdev_ms",
)


def _percentile(values: list[float], percentile: float) -> float:
    """Return a linearly interpolated percentile."""
    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def _quartile_means(values: list[float]) -> tuple[float | None, ...]:
    """Return the means of four consecutive, sorted quartile groups."""
    result: list[float | None] = []
    base_size, remainder = divmod(len(values), 4)
    start = 0
    for quartile_index in range(4):
        group_size = base_size + (1 if quartile_index < remainder else 0)
        group = values[start : start + group_size]
        result.append(statistics.mean(group) if group else None)
        start += group_size
    return tuple(result)


def calculate_metrics(raw_values: Iterable[str]) -> dict[str, float | int | None]:
    """Calculate latency metrics from CSV field values."""
    values: list[float] = []
    for raw_value in raw_values:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            values.append(value)

    if not values:
        raise ValueError("no valid non-negative latency values found")

    values.sort()
    q1, q2, q3, q4 = _quartile_means(values)
    return {
        "latency_count": len(values),
        "latency_mean_ms": statistics.mean(values),
        "latency_min_ms": values[0],
        "latency_max_ms": values[-1],
        "latency_q1_mean_ms": q1,
        "latency_q2_mean_ms": q2,
        "latency_q3_mean_ms": q3,
        "latency_q4_mean_ms": q4,
        "latency_median_ms": statistics.median(values),
        "latency_p95_ms": _percentile(values, 95),
        "latency_p99_ms": _percentile(values, 99),
        "latency_stdev_ms": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def _format_metric(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.6f}"


def _read_latency_values(source_path: Path) -> list[str]:
    with source_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file)
        if not reader.fieldnames or LATENCY_COLUMN not in reader.fieldnames:
            raise ValueError(f"missing {LATENCY_COLUMN!r} column")
        return [
            row.get(LATENCY_COLUMN, "")
            for row in reader
        ]


def update_results_file(results_path: Path) -> str:
    """Update one results.csv and return its outcome."""
    with results_path.open("r", encoding="utf-8-sig", newline="") as results_file:
        reader = csv.DictReader(results_file)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames:
        return "skipped (empty or missing header)"
    if "latency_mean_ms" in fieldnames:
        return "skipped (metrics already present)"

    source_path = results_path.with_name("results_from_json.csv")
    if not source_path.is_file():
        return "skipped (results_from_json.csv unavailable)"

    try:
        metrics = calculate_metrics(_read_latency_values(source_path))
    except (OSError, csv.Error, ValueError) as error:
        return f"skipped ({error})"

    output_fieldnames = [*fieldnames, *METRIC_COLUMNS]
    for row in rows:
        row.update({
            column: _format_metric(metrics[column])
            for column in METRIC_COLUMNS
        })

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=results_path.parent,
            prefix=f".{results_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(temporary_file, fieldnames=output_fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_path, results_path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    return f"updated ({metrics['latency_count']} requests)"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add latency metrics to results.csv files recursively."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="directory to scan recursively (default: current directory)",
    )
    args = parser.parse_args()

    results_files = sorted(args.root.rglob("results.csv"))
    total = len(results_files)
    counts = {"updated": 0, "skipped": 0, "failed": 0}

    for index, results_path in enumerate(results_files, start=1):
        try:
            outcome = update_results_file(results_path)
        except OSError as error:
            outcome = f"failed ({error})"

        category = "updated" if outcome.startswith("updated") else (
            "failed" if outcome.startswith("failed") else "skipped"
        )
        counts[category] += 1
        print(
            f"\r[{index}/{total}] {index / total:.1%} "
            f"{category}: {results_path}",
            end="",
            flush=True,
        )
        print(f" - {outcome}")

    print(
        f"Completed: {total} files scanned; "
        f"{counts['updated']} updated, {counts['skipped']} skipped, "
        f"{counts['failed']} failed."
    )


if __name__ == "__main__":
    main()
