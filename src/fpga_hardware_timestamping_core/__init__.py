"""Reference model for multi-channel FPGA timestamp normalization."""

from .analysis import (
    AnalysisConfiguration,
    AnalysisResult,
    MetricSummary,
    SourceIdentity,
    TimingMetrics,
    analyze_events,
)
from .calibration import ChannelCalibration
from .counters import CounterUnwrapper
from .reorder import ReorderBuffer
from .sequence import SequenceDiagnostic, SequenceKind, SequenceMonitor
from .timestamping import (
    OrderedEvent,
    TimestampedEvent,
    max_skew_ns,
    monotonic_violations,
    normalize,
)

__all__ = [
    "AnalysisConfiguration",
    "AnalysisResult",
    "ChannelCalibration",
    "CounterUnwrapper",
    "MetricSummary",
    "OrderedEvent",
    "ReorderBuffer",
    "SequenceDiagnostic",
    "SequenceKind",
    "SequenceMonitor",
    "SourceIdentity",
    "TimestampedEvent",
    "TimingMetrics",
    "analyze_events",
    "max_skew_ns",
    "monotonic_violations",
    "normalize",
]
