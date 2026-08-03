from __future__ import annotations

import heapq
from itertools import count

from .timestamping import OrderedEvent


class ReorderBuffer:
    """Timestamp-order events behind a monotonic bounded-lateness watermark."""

    def __init__(self, allowed_lateness_ns: int) -> None:
        if (
            not isinstance(allowed_lateness_ns, int)
            or isinstance(allowed_lateness_ns, bool)
            or allowed_lateness_ns < 0
        ):
            raise ValueError("allowed_lateness_ns must be a non-negative integer")
        self.allowed_lateness_ns = allowed_lateness_ns
        self.watermark_ns: int | None = None
        self.late_event_count = 0
        self._maximum_seen_ns: int | None = None
        self._heap: list[tuple[int, str, int, int, int, OrderedEvent]] = []
        self._insertion_order = count()

    def push(self, event: OrderedEvent) -> list[OrderedEvent]:
        if self.watermark_ns is not None and event.normalized_ns < self.watermark_ns:
            self.late_event_count += 1

        if self._maximum_seen_ns is None or event.normalized_ns > self._maximum_seen_ns:
            self._maximum_seen_ns = event.normalized_ns
            next_watermark = self._maximum_seen_ns - self.allowed_lateness_ns
            if self.watermark_ns is None or next_watermark > self.watermark_ns:
                self.watermark_ns = next_watermark

        heapq.heappush(
            self._heap,
            (
                event.normalized_ns,
                event.channel,
                event.sequence,
                event.arrival_index,
                next(self._insertion_order),
                event,
            ),
        )
        return self._drain_before_watermark()

    def flush(self) -> list[OrderedEvent]:
        emitted: list[OrderedEvent] = []
        while self._heap:
            emitted.append(heapq.heappop(self._heap)[-1])
        return emitted

    def _drain_before_watermark(self) -> list[OrderedEvent]:
        emitted: list[OrderedEvent] = []
        if self.watermark_ns is None:
            return emitted
        while self._heap and self._heap[0][0] < self.watermark_ns:
            emitted.append(heapq.heappop(self._heap)[-1])
        return emitted
