from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from fractions import Fraction
from typing import Any

from .analysis import AnalysisResult, MetricSummary
from .integers import integer_to_decimal, json_safe_integers
from .sequence import SequenceKind
from .validation import neutralize_terminal_controls, validate_identifier


def _format_fraction(value: Fraction) -> str:
    numerator = value.numerator
    denominator = value.denominator
    sign = "-" if numerator < 0 else ""
    numerator = abs(numerator)
    whole, remainder = divmod(numerator, denominator)
    if remainder == 0:
        return f"{sign}{integer_to_decimal(whole)}"

    reduced_denominator = denominator
    while reduced_denominator % 2 == 0:
        reduced_denominator //= 2
    while reduced_denominator % 5 == 0:
        reduced_denominator //= 5
    if reduced_denominator != 1:
        return f"{integer_to_decimal(value.numerator)}/{integer_to_decimal(value.denominator)}"

    digits: list[str] = []
    while remainder:
        remainder *= 10
        digit, remainder = divmod(remainder, denominator)
        digits.append(str(digit))
    return f"{sign}{integer_to_decimal(whole)}.{''.join(digits)}"


def _metric_to_dict(metric: MetricSummary) -> dict[str, int | str | None]:
    return {
        "count": metric.count,
        "minimum": metric.minimum,
        "maximum": metric.maximum,
        "mean": _format_fraction(metric.mean) if metric.mean is not None else None,
    }


def report_to_dict(result: AnalysisResult) -> dict[str, Any]:
    if result.source.name is not None:
        validate_identifier(result.source.name, field="source_name")
    for channel, _ in result.configuration.calibrations:
        validate_identifier(channel, field="calibration channel")
    for event in result.ordered_events:
        validate_identifier(event.channel, field="event channel")
    for diagnostic in result.diagnostics:
        validate_identifier(
            diagnostic.channel,
            field="diagnostic channel",
            allow_empty=True,
        )
    sequence_counts = Counter(diagnostic.kind for diagnostic in result.diagnostics)
    channels = {event.channel for event in result.ordered_events}
    return {
        "configuration": {
            "allowed_lateness_ns": result.configuration.allowed_lateness_ns,
            "calibrations": {
                channel: asdict(calibration)
                for channel, calibration in result.configuration.calibrations
            },
            "counter_bits": result.configuration.counter_bits,
        },
        "source": asdict(result.source),
        "summary": {
            "channel_count": len(channels),
            "event_count": len(result.ordered_events),
            "late_event_count": result.late_event_count,
        },
        "sequence": {kind.value: sequence_counts[kind] for kind in SequenceKind}
        | {
            "gap_positions_exposed": sum(
                diagnostic.missing_count for diagnostic in result.diagnostics
            ),
        },
        "metrics": {
            "timestamp_span_ns": result.metrics.timestamp_span_ns,
            "cross_channel_skew_ns": _metric_to_dict(
                result.metrics.cross_channel_skew_ns
            ),
            "latency_ns": _metric_to_dict(result.metrics.latency_ns),
            "jitter_ns": _metric_to_dict(result.metrics.jitter_ns),
        },
        "events": [asdict(event) for event in result.ordered_events],
        "diagnostics": [
            {
                **asdict(diagnostic),
                "kind": diagnostic.kind.value,
            }
            for diagnostic in result.diagnostics
        ],
    }


def render_json_report(result: AnalysisResult) -> str:
    payload = json_safe_integers(report_to_dict(result))
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _format_number(value: int | str | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return integer_to_decimal(value)
    return str(value)


def _markdown_code(value: str) -> str:
    """Render untrusted text as a GFM code span without active inline syntax."""

    collapsed = (
        neutralize_terminal_controls(value).replace("\r", " ").replace("\n", " ")
    )
    maximum_run = 0
    current_run = 0
    for character in collapsed:
        if character == "`":
            current_run += 1
            maximum_run = max(maximum_run, current_run)
        else:
            current_run = 0
    delimiter = "`" * (maximum_run + 1)
    if maximum_run or collapsed[:1].isspace() or collapsed[-1:].isspace():
        return f"{delimiter} {collapsed} {delimiter}"
    return f"{delimiter}{collapsed}{delimiter}"


def render_markdown_report(result: AnalysisResult) -> str:
    report = report_to_dict(result)
    summary = report["summary"]
    sequence = report["sequence"]
    metrics = report["metrics"]
    configuration = report["configuration"]
    source = report["source"]
    lines = [
        "# Timestamp Analysis Report",
        "",
        "This report is Python reference-model evidence from the supplied input. It is not RTL simulation evidence.",
        "",
        "## Run Identity",
        "",
        f"- Source: {_markdown_code(source['name'] or 'unspecified')}",
        f"- SHA-256: `{source['sha256'] or 'unspecified'}`",
        f"- Counter width: {configuration['counter_bits']} bits",
        f"- Allowed lateness: {configuration['allowed_lateness_ns']} ns",
        f"- Calibrated channels: {len(configuration['calibrations'])}",
        "",
        "## Calibration Configuration",
        "",
    ]
    for channel, calibration in configuration["calibrations"].items():
        lines.extend(
            [
                f"### Channel {_markdown_code(channel)}",
                "",
                f"- Offset: {_format_number(calibration['offset_ns'])} ns",
                f"- Drift: {_format_number(calibration['drift_ppb'])} ppb",
                (
                    "- Reference timestamp: "
                    f"{_format_number(calibration['reference_ns'])} ns"
                ),
                "",
            ]
        )
    if not configuration["calibrations"]:
        lines.extend(["No per-channel calibrations were supplied.", ""])
    lines.extend(
        [
            "## Summary",
            "",
            "| Measure | Value |",
            "| --- | ---: |",
            f"| Events | {summary['event_count']} |",
            f"| Channels | {summary['channel_count']} |",
            f"| Events beyond lateness bound | {summary['late_event_count']} |",
            "",
            "## Sequence Integrity",
            "",
            "| Classification | Count |",
            "| --- | ---: |",
            f"| First | {sequence['first']} |",
            f"| In order | {sequence['ok']} |",
            f"| Duplicate | {sequence['duplicate']} |",
            f"| Gap | {sequence['gap']} |",
            f"| Out of order | {sequence['out_of_order']} |",
            f"| Gap positions exposed | {_format_number(sequence['gap_positions_exposed'])} |",
            "",
            "## Timing Metrics",
            "",
            "| Metric | Count | Minimum (ns) | Maximum (ns) | Mean (ns) |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for label, key in (
        ("Cross-channel skew", "cross_channel_skew_ns"),
        ("Latency", "latency_ns"),
        ("Jitter", "jitter_ns"),
    ):
        metric = metrics[key]
        lines.append(
            f"| {label} | {metric['count']} | {_format_number(metric['minimum'])} | "
            f"{_format_number(metric['maximum'])} | {_format_number(metric['mean'])} |"
        )
    if summary["event_count"]:
        span_row = (
            f"| Timestamp span | 1 | {_format_number(metrics['timestamp_span_ns'])} | "
            f"{_format_number(metrics['timestamp_span_ns'])} | "
            f"{_format_number(metrics['timestamp_span_ns'])} |"
        )
    else:
        span_row = "| Timestamp span | 0 | n/a | n/a | n/a |"
    lines.extend([span_row, ""])
    return "\n".join(lines)
