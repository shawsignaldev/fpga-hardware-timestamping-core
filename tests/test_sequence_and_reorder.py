from fpga_hardware_timestamping_core.reorder import ReorderBuffer
from fpga_hardware_timestamping_core.sequence import SequenceKind, SequenceMonitor
from fpga_hardware_timestamping_core.timestamping import OrderedEvent


def test_sequence_monitor_classifies_duplicate_gap_and_out_of_order():
    monitor = SequenceMonitor()

    diagnostics = [monitor.observe(sequence) for sequence in (10, 11, 11, 14, 13)]

    assert [diagnostic.kind for diagnostic in diagnostics] == [
        SequenceKind.FIRST,
        SequenceKind.OK,
        SequenceKind.DUPLICATE,
        SequenceKind.GAP,
        SequenceKind.OUT_OF_ORDER,
    ]
    assert diagnostics[3].missing_count == 2


def test_reorder_buffer_reorders_within_lateness_bound():
    buffer = ReorderBuffer(allowed_lateness_ns=10)

    emitted = []
    emitted.extend(buffer.push(OrderedEvent("A", 1, 100)))
    emitted.extend(buffer.push(OrderedEvent("A", 2, 120)))
    emitted.extend(buffer.push(OrderedEvent("B", 1, 110)))
    emitted.extend(buffer.flush())

    assert [event.normalized_ns for event in emitted] == [100, 110, 120]
    assert buffer.late_event_count == 0
    assert buffer.watermark_ns == 110


def test_reorder_buffer_records_events_beyond_lateness_bound():
    buffer = ReorderBuffer(allowed_lateness_ns=10)

    buffer.push(OrderedEvent("A", 1, 100))
    buffer.push(OrderedEvent("A", 2, 130))
    emitted = buffer.push(OrderedEvent("B", 1, 115))

    assert [event.normalized_ns for event in emitted] == [115]
    assert buffer.late_event_count == 1


def test_equal_timestamps_use_channel_then_sequence_tie_breaking():
    buffer = ReorderBuffer(allowed_lateness_ns=0)

    events = [
        OrderedEvent("B", 2, 100),
        OrderedEvent("A", 3, 100),
        OrderedEvent("A", 2, 100),
    ]
    emitted = []
    for event in events:
        emitted.extend(buffer.push(event))
    emitted.extend(buffer.flush())

    assert [(event.channel, event.sequence) for event in emitted] == [
        ("A", 2),
        ("A", 3),
        ("B", 2),
    ]
