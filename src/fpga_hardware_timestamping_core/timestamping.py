from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimestampedEvent:
    channel: str
    sequence: int
    raw_ns: int


@dataclass(frozen=True)
class OrderedEvent:
    channel: str
    sequence: int
    normalized_ns: int


def normalize(events: list[TimestampedEvent], offsets_ns: dict[str, int]) -> list[OrderedEvent]:
    normalized = [
        OrderedEvent(event.channel, event.sequence, event.raw_ns - offsets_ns.get(event.channel, 0))
        for event in events
    ]
    return sorted(normalized, key=lambda event: (event.normalized_ns, event.channel, event.sequence))


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
    return max(event.normalized_ns for event in events) - min(event.normalized_ns for event in events)
