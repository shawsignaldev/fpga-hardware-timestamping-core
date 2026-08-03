# Timing Model

## Units And Inputs

All timestamps, offsets, lateness bounds, and reported timing metrics are integer nanoseconds. Drift is a signed integer in parts per billion. Each channel has an independent calibration and fixed-width counter-unwrapping state.

The Python input event is:

```text
(channel, sequence, raw_ns, optional arrival_ns)
```

`raw_ns` is a counter reading, not an absolute time until it has been unwrapped and calibrated. Raw counter readings and arrival timestamps are non-negative. Unwrapped and normalized timestamps are signed because a late sample can map to the epoch immediately before the first observed anchor.

## Calibration Equation

For an unwrapped timestamp `u`, channel offset `o`, signed drift `d`, and calibration reference `r`:

```text
elapsed = u - r
drift_correction = trunc_toward_zero(elapsed * d / 1,000,000,000)
normalized = u - o - drift_correction
```

A positive offset means the channel clock reads ahead and is subtracted. A negative offset is therefore added. Positive drift means the channel gains time relative to the reference and receives an increasing subtraction after the reference epoch. Negative drift receives the corresponding addition.

Integer division truncates toward zero in both the Python model and SystemVerilog module. There is no floating-point arithmetic in normalization.

## Counter Rollover

For a `W`-bit counter, the modulus is `2^W` and the half range is `2^(W-1)`. The unwrapper compares each arrival with the channel's highest unwrapped anchor and chooses the nearby modular interpretation:

- A much smaller raw value is mapped into the next epoch.
- A much larger raw value can be mapped into the previous epoch as a late sample.
- A candidate newer than the anchor advances it; a late candidate does not.

This requires consecutive forward observations to be separated by less than half the counter range. A displacement of exactly half the range is interpreted as negative in the Python model. Streams that can be silent for half a counter period or longer need an external epoch indicator. Immediately after reset, a sample that belongs to a negative previous epoch cannot be represented by the unsigned RTL output.

For example, if the first observed value of an 8-bit counter is `2`, a later raw value of `250` maps to `-6` in the previous epoch. That signed value remains valid through calibration, ordering, metrics, and report generation. The software model preserves this previous-epoch domain even though the unsigned RTL output cannot represent it immediately after reset.

## Sequence Integrity

Sequence diagnostics are evaluated in arrival order, independently per channel:

| Classification | Condition |
| --- | --- |
| `first` | First observed sequence |
| `ok` | Exactly one above the prior high-water sequence |
| `duplicate` | A sequence value already observed by the Python monitor |
| `gap` | Above the prior high-water sequence by more than one |
| `out_of_order` | Below the prior high-water sequence and not previously observed |

The gap's `missing_count` is the size of the newly exposed interval. Later arrival of a missing sequence does not revise the earlier gap diagnostic.

The RTL guard has bounded state: it flags equality with the current high-water sequence as duplicate and any lower value as out of order.

## Watermark And Bounded Lateness

Let `M` be the greatest normalized timestamp observed and `L` the configured allowed lateness:

```text
watermark = M - L
```

The watermark never decreases. Events strictly below it are released in deterministic key order. Events exactly at the watermark remain buffered until the watermark advances or the stream is flushed; this permits deterministic tie-breaking among equal timestamps.

An arrival strictly below the watermark that existed before the arrival is counted as late. It is retained, not dropped, and is emitted when eligible. Because previously released events cannot be recalled, such an event can cause a timestamp regression in final emission order. The late-event count makes that condition explicit.

`flush()` releases all remaining events and does not alter the last data-derived watermark.

## Metrics

- **Timestamp span:** maximum normalized timestamp minus minimum across all events; zero for empty input.
- **Cross-channel skew:** for each sequence present on at least two distinct channels, maximum minus minimum normalized timestamp. Reports summarize those per-sequence values.
- **Latency:** `arrival_ns - normalized_ns` for every event with an arrival timestamp. Negative values are retained because they expose clock-domain or calibration inconsistency.
- **Jitter:** absolute change in latency between consecutive arrivals on the same channel. Reports pool those per-channel changes.

Each metric summary contains count, minimum, maximum, and an exact rational arithmetic mean. JSON renders a terminating mean as a decimal string and a repeating mean as `numerator/denominator`; Markdown uses the same exact text. Empty summaries use `null` in JSON and `n/a` in Markdown. Cross-channel skew spans every observation of a sequence once that sequence appears on at least two channels, so duplicates cannot be silently discarded.

## Numeric Ranges

Python arithmetic is not width-limited. RTL arithmetic is fixed-width and uses synthesis-oriented constructs. `timestamp_unwrapper` returns `COUNTER_WIDTH + EPOCH_WIDTH` unsigned bits. `timestamp_normalizer` returns `TIMESTAMP_WIDTH + 1` signed bits. A final result outside that signed range saturates and raises `overflow`; internal operand and drift-product sizing still belongs to the target integration.

No timing closure, resource use, clock frequency, transport latency, or end-to-end hardware latency is claimed by this model.
