from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .validation import validate_identifier


class SequenceKind(str, Enum):
    FIRST = "first"
    OK = "ok"
    DUPLICATE = "duplicate"
    GAP = "gap"
    OUT_OF_ORDER = "out_of_order"


@dataclass(frozen=True)
class SequenceDiagnostic:
    channel: str
    sequence: int
    kind: SequenceKind
    previous_highest: int | None
    missing_count: int = 0

    def __post_init__(self) -> None:
        validate_identifier(self.channel, field="diagnostic channel", allow_empty=True)


class SequenceMonitor:
    """Classify sequence integrity in arrival order for one channel."""

    def __init__(self, channel: str = "") -> None:
        self.channel = validate_identifier(
            channel,
            field="sequence monitor channel",
            allow_empty=True,
        )
        self._highest: int | None = None
        self._seen: set[int] = set()

    def observe(self, sequence: int) -> SequenceDiagnostic:
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise ValueError("sequence must be a non-negative integer")

        previous = self._highest
        if previous is None:
            kind = SequenceKind.FIRST
            missing_count = 0
            self._highest = sequence
        elif sequence in self._seen:
            kind = SequenceKind.DUPLICATE
            missing_count = 0
        elif sequence == previous + 1:
            kind = SequenceKind.OK
            missing_count = 0
            self._highest = sequence
        elif sequence > previous + 1:
            kind = SequenceKind.GAP
            missing_count = sequence - previous - 1
            self._highest = sequence
        else:
            kind = SequenceKind.OUT_OF_ORDER
            missing_count = 0

        self._seen.add(sequence)
        return SequenceDiagnostic(
            channel=self.channel,
            sequence=sequence,
            kind=kind,
            previous_highest=previous,
            missing_count=missing_count,
        )
