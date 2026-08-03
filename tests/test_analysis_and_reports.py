import json
from fractions import Fraction

import pytest

from fpga_hardware_timestamping_core.analysis import analyze_events
from fpga_hardware_timestamping_core.calibration import ChannelCalibration
from fpga_hardware_timestamping_core.reporting import (
    render_json_report,
    render_markdown_report,
    report_to_dict,
)
from fpga_hardware_timestamping_core.timestamping import TimestampedEvent


def test_analysis_computes_skew_jitter_and_latency_metrics():
    events = [
        TimestampedEvent("A", 1, 100, arrival_ns=130),
        TimestampedEvent("B", 1, 105, arrival_ns=140),
        TimestampedEvent("A", 2, 200, arrival_ns=245),
        TimestampedEvent("B", 2, 205, arrival_ns=250),
    ]

    result = analyze_events(
        events,
        calibrations={"B": ChannelCalibration(offset_ns=5)},
        counter_bits=16,
        allowed_lateness_ns=100,
    )

    assert [
        (event.channel, event.normalized_ns) for event in result.ordered_events
    ] == [
        ("A", 100),
        ("B", 100),
        ("A", 200),
        ("B", 200),
    ]
    assert result.metrics.timestamp_span_ns == 100
    assert result.metrics.cross_channel_skew_ns.count == 2
    assert result.metrics.cross_channel_skew_ns.maximum == 0
    assert result.metrics.latency_ns.count == 4
    assert result.metrics.latency_ns.minimum == 30
    assert result.metrics.latency_ns.maximum == 50
    assert result.metrics.latency_ns.mean == 41.25
    assert result.metrics.jitter_ns.count == 2
    assert result.metrics.jitter_ns.maximum == 15
    assert result.metrics.jitter_ns.mean == Fraction(25, 2)


def test_metric_means_remain_exact_for_large_integer_timestamps():
    base = 10**400
    events = [
        TimestampedEvent("A", 1, 0, arrival_ns=base),
        TimestampedEvent("B", 1, 0, arrival_ns=base + 1),
    ]

    result = analyze_events(events, counter_bits=8)

    assert result.metrics.latency_ns.mean == Fraction(2 * base + 1, 2)
    report = report_to_dict(result)
    assert report["metrics"]["latency_ns"]["mean"] == f"{base}.5"
    assert json.loads(render_json_report(result)) == report


def test_cross_channel_skew_includes_duplicate_observations():
    result = analyze_events(
        [
            TimestampedEvent("A", 7, 100),
            TimestampedEvent("B", 7, 105),
            TimestampedEvent("A", 7, 1_000),
        ],
        counter_bits=16,
        allowed_lateness_ns=2_000,
    )

    assert result.metrics.cross_channel_skew_ns.count == 1
    assert result.metrics.cross_channel_skew_ns.maximum == 900


def test_analysis_handles_empty_input():
    result = analyze_events([], counter_bits=8, allowed_lateness_ns=10)

    assert result.ordered_events == ()
    assert result.diagnostics == ()
    assert result.metrics.timestamp_span_ns == 0
    assert result.metrics.latency_ns.count == 0
    assert result.late_event_count == 0


def test_analysis_accepts_a_late_sample_from_the_previous_counter_epoch():
    result = analyze_events(
        [
            TimestampedEvent("A", 0, 2),
            TimestampedEvent("A", 1, 250),
        ],
        counter_bits=8,
        allowed_lateness_ns=256,
    )

    assert [event.unwrapped_ns for event in result.ordered_events] == [-6, 2]
    assert [event.normalized_ns for event in result.ordered_events] == [-6, 2]


def test_report_captures_reproducibility_configuration_and_input_identity():
    calibration = ChannelCalibration(offset_ns=-10, drift_ppb=25, reference_ns=50)
    result = analyze_events(
        [TimestampedEvent("A", 1, 100)],
        calibrations={"A": calibration},
        counter_bits=12,
        allowed_lateness_ns=7,
        source_name="events.csv",
        source_sha256="a" * 64,
    )

    report = report_to_dict(result)

    assert report["configuration"] == {
        "allowed_lateness_ns": 7,
        "calibrations": {"A": {"drift_ppb": 25, "offset_ns": -10, "reference_ns": 50}},
        "counter_bits": 12,
    }
    assert report["source"] == {"name": "events.csv", "sha256": "a" * 64}


def test_markdown_report_includes_complete_calibration_configuration():
    result = analyze_events(
        [],
        calibrations={
            "A": ChannelCalibration(offset_ns=-10, drift_ppb=25, reference_ns=50),
            "B": ChannelCalibration(offset_ns=4, drift_ppb=-15, reference_ns=65_524),
        },
    )

    markdown_report = render_markdown_report(result)

    assert "## Calibration Configuration" in markdown_report
    assert "### Channel `A`" in markdown_report
    assert "- Offset: -10 ns" in markdown_report
    assert "- Drift: 25 ppb" in markdown_report
    assert "- Reference timestamp: 50 ns" in markdown_report
    assert "### Channel `B`" in markdown_report
    assert "- Offset: 4 ns" in markdown_report
    assert "- Drift: -15 ppb" in markdown_report
    assert "- Reference timestamp: 65524 ns" in markdown_report


def test_json_and_markdown_reports_include_evidence_and_diagnostics():
    events = [
        TimestampedEvent("A", 1, 250, arrival_ns=270),
        TimestampedEvent("A", 1, 251, arrival_ns=272),
        TimestampedEvent("A", 3, 2, arrival_ns=280),
        TimestampedEvent("A", 2, 3, arrival_ns=282),
    ]
    result = analyze_events(events, counter_bits=8, allowed_lateness_ns=20)

    report = report_to_dict(result)
    json_report = json.loads(render_json_report(result))
    markdown_report = render_markdown_report(result)

    assert report["summary"] == {
        "channel_count": 1,
        "event_count": 4,
        "late_event_count": 0,
    }
    assert report["sequence"]["duplicate"] == 1
    assert report["sequence"]["gap"] == 1
    assert report["sequence"]["out_of_order"] == 1
    assert report["sequence"]["gap_positions_exposed"] == 1
    assert json_report == report
    assert "# Timestamp Analysis Report" in markdown_report
    assert "Python reference-model evidence" in markdown_report
    assert "| Duplicate | 1 |" in markdown_report
    assert "| Gap positions exposed | 1 |" in markdown_report
    assert "| Timestamp span | 1 | 9 | 9 | 9 |" in markdown_report


def test_empty_markdown_report_does_not_claim_a_timestamp_span_observation():
    markdown_report = render_markdown_report(analyze_events([]))

    assert "| Timestamp span | 0 | n/a | n/a | n/a |" in markdown_report


def test_markdown_report_renders_untrusted_identifiers_as_literal_code():
    hostile_source = (
        "[review](https://attacker.invalid) ![pixel](https://attacker.invalid/pixel) "
        "**forged** user@example.com <script>alert(1)</script> `tick`"
    )
    hostile_channel = "[channel](https://attacker.invalid) | ops@example.com **admin**"
    result = analyze_events(
        [],
        calibrations={hostile_channel: ChannelCalibration()},
        source_name=hostile_source,
        source_sha256="b" * 64,
    )

    markdown_report = render_markdown_report(result)

    assert (
        "`` [review](https://attacker.invalid) ![pixel](https://attacker.invalid/pixel) "
        "**forged** user@example.com <script>alert(1)</script> `tick` ``"
        in markdown_report
    )
    assert f"### Channel `{hostile_channel}`" in markdown_report


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("source_name", "capture\x1b]52;c;payload\x07.csv"),
        ("source_name", "capture\ud800.csv"),
    ],
)
def test_analysis_rejects_invalid_report_source_identifiers(keyword, value):
    with pytest.raises(ValueError, match="source_name"):
        analyze_events([], **{keyword: value})


@pytest.mark.parametrize(
    "channel", ["A\x07B", "A\x1b]52;c;payload\x07", "A\u202eB", "\ud800"]
)
def test_analysis_rejects_invalid_calibration_identifiers(channel):
    with pytest.raises(ValueError, match="calibration channel"):
        analyze_events([], calibrations={channel: ChannelCalibration()})
