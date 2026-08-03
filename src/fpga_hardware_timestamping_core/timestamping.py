from __future__ import annotations

from dataclasses import dataclass

from .validation import validate_identifier


@dataclass(frozen=True)
class TimestampedEvent:
    channel: str
    sequence: int
    raw_ns: int
    arrival_ns: int | None = None

    def __post_init__(self) -> None:
        _validate_channel(self.channel)
        _validate_non_negative_integer("sequence", self.sequence)
        _validate_non_negative_integer("raw_ns", self.raw_ns)
        if self.arrival_ns is not None:
            _validate_non_negative_integer("arrival_ns", self.arrival_ns)


@dataclass(frozen=True)
class OrderedEvent:
    channel: str
    sequence: int
    normalized_ns: int
    raw_ns: int | None = None
    unwrapped_ns: int | None = None
    arrival_ns: int | None = None
    arrival_index: int = 0

    def __post_init__(self) -> None:
        _validate_channel(self.channel)
        _validate_non_negative_integer("sequence", self.sequence)
        _validate_integer("normalized_ns", self.normalized_ns)
        for name, value in (("raw_ns", self.raw_ns), ("arrival_ns", self.arrival_ns)):
            if value is not None:
                _validate_non_negative_integer(name, value)
        if self.unwrapped_ns is not None:
            _validate_integer("unwrapped_ns", self.unwrapped_ns)
        _validate_non_negative_integer("arrival_index", self.arrival_index)


def _validate_channel(channel: str) -> None:
    validate_identifier(channel, field="channel")


def _validate_integer(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")


def _validate_non_negative_integer(name: str, value: int) -> None:
    _validate_integer(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def normalize(
    events: list[TimestampedEvent], offsets_ns: dict[str, int]
) -> list[OrderedEvent]:
    for channel, offset_ns in offsets_ns.items():
        validate_identifier(channel, field="offset channel")
        _validate_integer(f"offset for channel {channel!r}", offset_ns)
    normalized = [
        OrderedEvent(
            event.channel,
            event.sequence,
            event.raw_ns - offsets_ns.get(event.channel, 0),
        )
        for event in events
    ]
    return sorted(
        normalized,
        key=lambda event: (event.normalized_ns, event.channel, event.sequence),
    )


def monotonic_violations(events: list[OrderedEvent]) -> list[str]:
    last_by_channel: dict[str, int] = {}
    violations: list[str] = []
    for event in events:
        previous = last_by_channel.get(event.channel)
        if previous is not None and event.normalized_ns < previous:
            violations.append(event.channel)
        last_by_channel[event.channel] = event.normalized_ns
    return violations


def max_skew_ns(events: list[OrderedEvent]) -> int:
    if not events:
        return 0
    return max(event.normalized_ns for event in events) - min(
        event.normalized_ns for event in events
    )
