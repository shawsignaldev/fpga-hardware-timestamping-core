from __future__ import annotations


class CounterUnwrapper:
    """Map a fixed-width modular counter onto an integer timeline."""

    def __init__(self, counter_bits: int) -> None:
        if (
            not isinstance(counter_bits, int)
            or isinstance(counter_bits, bool)
            or counter_bits < 2
        ):
            raise ValueError("counter_bits must be an integer of at least 2")
        self.counter_bits = counter_bits
        self.modulus = 1 << counter_bits
        self.half_range = self.modulus >> 1
        self._anchor_raw: int | None = None
        self._anchor_unwrapped: int | None = None

    def unwrap(self, raw_value: int) -> int:
        if not isinstance(raw_value, int) or isinstance(raw_value, bool):
            raise TypeError("raw counter value must be an integer")
        if not 0 <= raw_value < self.modulus:
            raise ValueError(
                f"raw value is outside the {self.counter_bits}-bit counter range"
            )

        if self._anchor_raw is None or self._anchor_unwrapped is None:
            self._anchor_raw = raw_value
            self._anchor_unwrapped = raw_value
            return raw_value

        delta = (raw_value - self._anchor_raw) % self.modulus
        if delta >= self.half_range:
            delta -= self.modulus
        candidate = self._anchor_unwrapped + delta

        if candidate > self._anchor_unwrapped:
            self._anchor_raw = raw_value
            self._anchor_unwrapped = candidate
        return candidate
