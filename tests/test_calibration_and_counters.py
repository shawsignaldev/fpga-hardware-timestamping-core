import pytest

from fpga_hardware_timestamping_core.calibration import ChannelCalibration
from fpga_hardware_timestamping_core.counters import CounterUnwrapper


def test_negative_offset_is_added_during_normalization():
    calibration = ChannelCalibration(offset_ns=-25)

    assert calibration.normalize(1_000) == 1_025


@pytest.mark.parametrize(
    ("drift_ppb", "expected"),
    [
        (50, 1_999_999_850),
        (-50, 1_999_999_950),
    ],
)
def test_signed_drift_is_corrected_from_reference_epoch(drift_ppb, expected):
    calibration = ChannelCalibration(
        offset_ns=100,
        drift_ppb=drift_ppb,
        reference_ns=1_000_000_000,
    )

    assert calibration.normalize(2_000_000_000) == expected


@pytest.mark.parametrize("field", ["offset_ns", "drift_ppb", "reference_ns"])
@pytest.mark.parametrize("invalid", [True, 1.5, "1"])
def test_calibration_constructor_rejects_non_integer_fields(field, invalid):
    values = {"offset_ns": 0, "drift_ppb": 0, "reference_ns": 0}
    values[field] = invalid

    with pytest.raises(TypeError, match=f"{field} must be an integer"):
        ChannelCalibration(**values)


@pytest.mark.parametrize("invalid", [True, 1.5, "1"])
def test_calibration_normalize_rejects_non_integer_timestamp(invalid):
    with pytest.raises(TypeError, match="unwrapped_ns must be an integer"):
        ChannelCalibration().normalize(invalid)


def test_counter_unwrapper_advances_across_rollover():
    unwrapper = CounterUnwrapper(counter_bits=8)

    assert [unwrapper.unwrap(value) for value in (250, 255, 2, 5)] == [
        250,
        255,
        258,
        261,
    ]


def test_counter_unwrapper_maps_late_sample_to_previous_epoch():
    unwrapper = CounterUnwrapper(counter_bits=8)

    assert unwrapper.unwrap(250) == 250
    assert unwrapper.unwrap(2) == 258
    assert unwrapper.unwrap(254) == 254
    assert unwrapper.unwrap(3) == 259


def test_counter_unwrapper_rejects_values_outside_width():
    unwrapper = CounterUnwrapper(counter_bits=8)

    with pytest.raises(ValueError, match="8-bit counter"):
        unwrapper.unwrap(256)
