from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Mapping

from .calibration import ChannelCalibration
from .counters import CounterUnwrapper
from .reorder import ReorderBuffer
from .sequence import SequenceDiagnostic, SequenceMonitor
from .timestamping import OrderedEvent, TimestampedEvent
from .validation import validate_identifier


@dataclass(frozen=True)
class MetricSummary:
    count: int
    minimum: int | None
    maximum: int | None
    mean: Fraction | None


@dataclass(frozen=True)
class AnalysisConfiguration:
    counter_bits: int = 48
    allowed_lateness_ns: int = 0
    calibrations: tuple[tuple[str, ChannelCalibration], ...] = ()

    def __post_init__(self) -> None:
        for channel, calibration in self.calibrations:
            validate_identifier(channel, field="calibration channel")
            if not isinstance(calibration, ChannelCalibration):
                raise TypeError(
                    "calibration values must be ChannelCalibration instances"
                )


@dataclass(frozen=True)
class SourceIdentity:
    name: str | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        if self.name is not None:
            validate_identifier(self.name, field="source_name")
        if self.sha256 is not None and (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError(
                "source_sha256 must be 64 lowercase hexadecimal characters or None"
            )


@dataclass(frozen=True)
class TimingMetrics:
    timestamp_span_ns: int
    cross_channel_skew_ns: MetricSummary
    latency_ns: MetricSummary
    jitter_ns: MetricSummary


@dataclass(frozen=True)
class AnalysisResult:
    ordered_events: tuple[OrderedEvent, ...]
    diagnostics: tuple[SequenceDiagnostic, ...]
    metrics: TimingMetrics
    late_event_count: int
    configuration: AnalysisConfiguration = field(default_factory=AnalysisConfiguration)
    source: SourceIdentity = field(default_factory=SourceIdentity)


def _summarize(values: Iterable[int]) -> MetricSummary:
    materialized = list(values)
    if not materialized:
        return MetricSummary(count=0, minimum=None, maximum=None, mean=None)
    return MetricSummary(
        count=len(materialized),
        minimum=min(materialized),
        maximum=max(materialized),
        mean=Fraction(sum(materialized), len(materialized)),
    )


def _compute_metrics(events: tuple[OrderedEvent, ...]) -> TimingMetrics:
    timestamp_span_ns = 0
    if events:
        timestamps = [event.normalized_ns for event in events]
        timestamp_span_ns = max(timestamps) - min(timestamps)

    by_sequence: dict[int, list[OrderedEvent]] = {}
    for event in events:
        by_sequence.setdefault(event.sequence, []).append(event)
    skew_values = [
        max(event.normalized_ns for event in sequence_events)
        - min(event.normalized_ns for event in sequence_events)
        for sequence_events in by_sequence.values()
        if len({event.channel for event in sequence_events}) > 1
    ]

    latency_by_channel: dict[str, list[tuple[int, int]]] = {}
    all_latencies: list[int] = []
    for event in events:
        if event.arrival_ns is None:
            continue
        latency = event.arrival_ns - event.normalized_ns
        all_latencies.append(latency)
        latency_by_channel.setdefault(event.channel, []).append(
            (event.arrival_index, latency)
        )

    jitter_values: list[int] = []
    for channel_latencies in latency_by_channel.values():
        ordered_latencies = [value for _, value in sorted(channel_latencies)]
        jitter_values.extend(
            abs(current - previous)
            for previous, current in zip(ordered_latencies, ordered_latencies[1:])
        )

    return TimingMetrics(
        timestamp_span_ns=timestamp_span_ns,
        cross_channel_skew_ns=_summarize(skew_values),
        latency_ns=_summarize(all_latencies),
        jitter_ns=_summarize(jitter_values),
    )


def analyze_events(
    events: Iterable[TimestampedEvent],
    calibrations: Mapping[str, ChannelCalibration] | None = None,
    *,
    counter_bits: int = 48,
    allowed_lateness_ns: int = 0,
    source_name: str | None = None,
    source_sha256: str | None = None,
) -> AnalysisResult:
    calibrations = calibrations or {}
    normalized_calibrations: list[tuple[str, ChannelCalibration]] = []
    for channel, calibration in calibrations.items():
        validate_identifier(channel, field="calibration channel")
        if not isinstance(calibration, ChannelCalibration):
            raise TypeError("calibration values must be ChannelCalibration instances")
        normalized_calibrations.append((channel, calibration))
    normalized_calibrations.sort(key=lambda item: item[0])
    if source_name is not None:
        validate_identifier(source_name, field="source_name")
    SourceIdentity(name=source_name, sha256=source_sha256)

    calibration_map = dict(normalized_calibrations)
    unwrappers: dict[str, CounterUnwrapper] = {}
    monitors: dict[str, SequenceMonitor] = {}
    reorder_buffer = ReorderBuffer(allowed_lateness_ns)
    diagnostics: list[SequenceDiagnostic] = []
    ordered_events: list[OrderedEvent] = []

    for arrival_index, event in enumerate(events):
        monitor = monitors.setdefault(event.channel, SequenceMonitor(event.channel))
        diagnostics.append(monitor.observe(event.sequence))

        unwrapper = unwrappers.setdefault(event.channel, CounterUnwrapper(counter_bits))
        unwrapped_ns = unwrapper.unwrap(event.raw_ns)
        calibration = calibration_map.get(event.channel, ChannelCalibration())
        normalized_ns = calibration.normalize(unwrapped_ns)
        normalized_event = OrderedEvent(
            channel=event.channel,
            sequence=event.sequence,
            normalized_ns=normalized_ns,
            raw_ns=event.raw_ns,
            unwrapped_ns=unwrapped_ns,
            arrival_ns=event.arrival_ns,
            arrival_index=arrival_index,
        )
        ordered_events.extend(reorder_buffer.push(normalized_event))

    ordered_events.extend(reorder_buffer.flush())
    ordered_tuple = tuple(ordered_events)
    return AnalysisResult(
        ordered_events=ordered_tuple,
        diagnostics=tuple(diagnostics),
        metrics=_compute_metrics(ordered_tuple),
        late_event_count=reorder_buffer.late_event_count,
        configuration=AnalysisConfiguration(
            counter_bits=counter_bits,
            allowed_lateness_ns=allowed_lateness_ns,
            calibrations=tuple(normalized_calibrations),
        ),
        source=SourceIdentity(name=source_name, sha256=source_sha256),
    )
