from pathlib import Path

from fpga_hardware_timestamping_core.timestamping import (
    TimestampedEvent,
    max_skew_ns,
    monotonic_violations,
    normalize,
)
import pytest


def test_normalize_orders_events_after_channel_offset():
    ordered = normalize(
        [
            TimestampedEvent("A", 1, 1_010),
            TimestampedEvent("B", 1, 1_000),
        ],
        {"A": 20},
    )

    assert [event.channel for event in ordered] == ["A", "B"]
    assert ordered[0].normalized_ns == 990


def test_skew_and_monotonic_violation_detection():
    ordered = normalize(
        [
            TimestampedEvent("A", 1, 100),
            TimestampedEvent("A", 2, 90),
            TimestampedEvent("B", 1, 140),
        ],
        {},
    )

    assert max_skew_ns(ordered) == 50
    assert monotonic_violations(ordered) == []


def test_timestamped_event_remains_compatible_with_three_arguments():
    event = TimestampedEvent("A", 7, 123)

    assert event.channel == "A"
    assert event.sequence == 7
    assert event.raw_ns == 123
    assert event.arrival_ns is None


@pytest.mark.parametrize(
    "event",
    [
        lambda: TimestampedEvent("", 1, 1),
        lambda: TimestampedEvent("A", -1, 1),
        lambda: TimestampedEvent("A", 1, -1),
        lambda: TimestampedEvent("A", 1, 1, arrival_ns=True),
    ],
)
def test_timestamped_event_rejects_invalid_public_values(event):
    with pytest.raises((TypeError, ValueError)):
        event()


@pytest.mark.parametrize(
    "invalid_channel", ["A\x07B", "A\x1b]52;c;payload\x07", "A\u202eB", "\ud800"]
)
def test_event_identifiers_reject_terminal_controls_and_invalid_unicode(
    invalid_channel,
):
    with pytest.raises(ValueError, match="channel"):
        TimestampedEvent(invalid_channel, 1, 1)


@pytest.mark.parametrize("invalid_offset", [True, 1.5, "1"])
def test_compatibility_normalize_rejects_non_integer_offsets(invalid_offset):
    with pytest.raises(TypeError, match="offset"):
        normalize([TimestampedEvent("A", 1, 1)], {"A": invalid_offset})


def test_rtl_sources_expose_safe_names_and_normalization_overflow_status():
    guard = Path("rtl/sequence_order_guard.sv").read_text(encoding="utf-8")
    normalizer = Path("rtl/timestamp_normalizer.sv").read_text(encoding="utf-8")

    assert "sequence_in" in guard
    assert " input  logic [SEQUENCE_WIDTH-1:0]    sequence," not in guard
    assert "output logic                                  overflow" in normalizer
