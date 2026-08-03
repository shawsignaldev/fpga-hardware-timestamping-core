from __future__ import annotations

from dataclasses import dataclass

PPB_SCALE = 1_000_000_000


def _truncate_division(numerator: int, denominator: int) -> int:
    quotient = abs(numerator) // denominator
    return -quotient if numerator < 0 else quotient


@dataclass(frozen=True)
class ChannelCalibration:
    """Signed offset and frequency-drift calibration for one channel."""

    offset_ns: int = 0
    drift_ppb: int = 0
    reference_ns: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("offset_ns", self.offset_ns),
            ("drift_ppb", self.drift_ppb),
            ("reference_ns", self.reference_ns),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer")

    def normalize(self, unwrapped_ns: int) -> int:
        """Remove offset and signed drift from an unwrapped timestamp."""

        if not isinstance(unwrapped_ns, int) or isinstance(unwrapped_ns, bool):
            raise TypeError("unwrapped_ns must be an integer")
        elapsed_ns = unwrapped_ns - self.reference_ns
        drift_correction_ns = _truncate_division(elapsed_ns * self.drift_ppb, PPB_SCALE)
        return unwrapped_ns - self.offset_ns - drift_correction_ns
