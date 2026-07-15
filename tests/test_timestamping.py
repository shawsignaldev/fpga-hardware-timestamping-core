from fpga_hardware_timestamping_core.timestamping import TimestampedEvent, max_skew_ns, monotonic_violations, normalize


def test_normalize_orders_events_after_channel_offset():
    ordered = normalize([
        TimestampedEvent("A", 1, 1_010),
        TimestampedEvent("B", 1, 1_000),
    ], {"A": 20})

    assert [event.channel for event in ordered] == ["A", "B"]
    assert ordered[0].normalized_ns == 990


def test_skew_and_monotonic_violation_detection():
    ordered = normalize([
        TimestampedEvent("A", 1, 100),
        TimestampedEvent("A", 2, 90),
        TimestampedEvent("B", 1, 140),
    ], {})

    assert max_skew_ns(ordered) == 50
    assert monotonic_violations(ordered) == []
