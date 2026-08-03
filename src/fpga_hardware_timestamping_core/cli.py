from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from .analysis import analyze_events
from .calibration import ChannelCalibration
from .csvio import read_csv_event_bytes
from .integers import parse_ascii_integer
from .reporting import render_json_report, render_markdown_report


def _calibration(value: str) -> tuple[str, ChannelCalibration]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4 or not parts[0]:
        raise argparse.ArgumentTypeError(
            "calibration must be CHANNEL,OFFSET_NS,DRIFT_PPB,REFERENCE_NS"
        )
    try:
        calibration = ChannelCalibration(
            offset_ns=parse_ascii_integer(parts[1]),
            drift_ppb=parse_ascii_integer(parts[2]),
            reference_ns=parse_ascii_integer(parts[3]),
        )
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "calibration values must be integers"
        ) from error
    return parts[0], calibration


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fpga-timestamp-report",
        description="Normalize and order multi-channel fixed-width timestamps.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="input CSV; defaults to the packaged fixture",
    )
    parser.add_argument("--counter-bits", type=int, default=16)
    parser.add_argument("--lateness-ns", type=int, default=100)
    parser.add_argument(
        "--calibration",
        action="append",
        default=[],
        type=_calibration,
        metavar="CHANNEL,OFFSET_NS,DRIFT_PPB,REFERENCE_NS",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    return parser


def _run(args: argparse.Namespace) -> str:
    if args.input is None:
        fixture = resources.files("fpga_hardware_timestamping_core").joinpath(
            "data/sample_timestamps.csv"
        )
        with resources.as_file(fixture) as fixture_path:
            source_bytes = fixture_path.read_bytes()
            events = read_csv_event_bytes(source_bytes)
            source_name = fixture_path.name
            source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    else:
        source_bytes = args.input.read_bytes()
        events = read_csv_event_bytes(source_bytes)
        source_name = args.input.name
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    calibrations = dict(args.calibration)
    result = analyze_events(
        events,
        calibrations,
        counter_bits=args.counter_bits,
        allowed_lateness_ns=args.lateness_ns,
        source_name=source_name,
        source_sha256=source_sha256,
    )
    if args.format == "markdown":
        return render_markdown_report(result)
    return render_json_report(result)


def _write_report(path: Path, report: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(report)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _reject_input_output_alias(
    input_path: Path | None, output_path: Path | None
) -> None:
    if input_path is None or output_path is None:
        return
    if input_path.resolve(strict=False) == output_path.resolve(strict=False):
        raise ValueError("output must not refer to the input CSV")
    try:
        aliases = os.path.samefile(input_path, output_path)
    except FileNotFoundError:
        aliases = False
    if aliases:
        raise ValueError("output must not refer to the input CSV")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        _reject_input_output_alias(args.input, args.output)
        report = _run(args)
        _reject_input_output_alias(args.input, args.output)
        if args.output is None:
            print(report, end="" if report.endswith("\n") else "\n")
        else:
            _write_report(args.output, report)
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))
    return 0
