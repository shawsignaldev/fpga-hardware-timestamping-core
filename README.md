# FPGA Hardware Timestamping Core

A reference system for normalizing and ordering timestamps from multi-channel FPGA market-data pipelines. The repository combines a dependency-light Python model for data analysis with synthesis-oriented SystemVerilog streaming primitives.

## Capabilities

- Per-channel signed offset and frequency-drift calibration in parts per billion
- Fixed-width counter rollover unwrapping with bounded out-of-order tolerance
- Duplicate, gap, and out-of-order sequence diagnostics
- Deterministic ordering by normalized timestamp, channel, sequence, and arrival index
- Bounded-lateness buffering with a monotonic watermark and late-event accounting
- Cross-channel skew, latency, and latency-jitter summaries
- Strict canonical CSV input with deterministic, atomic JSON and Markdown reports
- Exact rational metric means without floating-point overflow or precision loss
- Input hashes and complete analysis configuration in every report
- Self-checking SystemVerilog benches for unwrapping, normalization, and sequence/order guarding

## Quick Start

Python 3.10 through 3.14 is supported and exercised in CI. The runtime package uses only the Python standard library.

```console
python -m pip install -e ".[dev]"
python -m pytest -q
fpga-timestamp-report --format markdown --output report.md
```

With no input path, the CLI analyzes the packaged copy of [`examples/sample_timestamps.csv`](examples/sample_timestamps.csv). An explicit input and per-channel calibration can be supplied as follows:

```console
fpga-timestamp-report examples/sample_timestamps.csv \
  --counter-bits 16 \
  --lateness-ns 100 \
  --calibration A,-10,25,65520 \
  --calibration B,4,-15,65524 \
  --format json \
  --output report.json
```

Calibration fields are `CHANNEL,OFFSET_NS,DRIFT_PPB,REFERENCE_NS`. Repeating a channel uses the last value.

## CSV Format

The header must be exactly the first three fields below, in order, with the optional fourth field last. Extra, reordered, or duplicate columns and trailing row fields are rejected.

| Field | Required | Meaning |
| --- | --- | --- |
| `channel` | Yes | Non-empty UTF-8 channel identifier without control or format characters |
| `sequence` | Yes | Non-negative per-channel sequence number |
| `raw_ns` | Yes | Unsigned fixed-width timestamp counter value |
| `arrival_ns` | No | Observation time used for latency and jitter metrics |

Rows are processed in file order, which is treated as arrival order. Integer fields use base-10 notation. Values outside the selected counter width are rejected during analysis.

Source and channel identifiers must encode as UTF-8 and cannot contain terminal control or Unicode format characters. The CLI rejects an output path that resolves to the input CSV, including hard-link aliases, before publication so a report cannot overwrite its evidence source.

## Python API

The original `TimestampedEvent`, `OrderedEvent`, `normalize`, `monotonic_violations`, and `max_skew_ns` interfaces remain available.

```python
from fpga_hardware_timestamping_core import (
    ChannelCalibration,
    TimestampedEvent,
    analyze_events,
)

events = [
    TimestampedEvent("A", 1, 65_530, arrival_ns=65_560),
    TimestampedEvent("A", 2, 4, arrival_ns=65_575),
]
result = analyze_events(
    events,
    calibrations={"A": ChannelCalibration(offset_ns=-10, drift_ppb=25)},
    counter_bits=16,
    allowed_lateness_ns=100,
)
```

See [`docs/timing-model.md`](docs/timing-model.md) for arithmetic, rollover, ordering, and metric definitions.

## Reports

JSON reports provide machine-readable source identity, configuration, summary, sequence, metric, event, and diagnostic records. Exact means are decimal strings when the rational result terminates and `numerator/denominator` strings otherwise. Integers beyond the portable native JSON conversion range are emitted as exact decimal strings; ordinary integers remain JSON numbers. Markdown reports contain the same aggregate evidence for review, including every calibration channel's signed offset, drift, and reference timestamp. Untrusted source and channel identifiers are rendered as literal code spans so Markdown, HTML, links, images, and GFM autolinks remain inactive. File reports are staged and atomically replaced with UTF-8, LF-only bytes. Reported latency is `arrival_ns - normalized_ns`; it is omitted when `arrival_ns` is absent. No transport or hardware latency is inferred.

## RTL

The [`rtl`](rtl) directory contains:

- `timestamp_unwrapper.sv`: expands a modular counter into epoch plus counter bits
- `timestamp_normalizer.sv`: applies signed offset and drift correction, saturating and flagging results outside the signed output range
- `sequence_order_guard.sv`: emits one-cycle duplicate, gap, out-of-order, and timestamp-regression flags

Each `sequence_order_guard` instance tracks one channel. Channel routing, buffering, and report rendering remain integration responsibilities.

On a system with Icarus Verilog:

```console
make -C rtl test
```

The benches are self-checking and terminate with `$fatal` on a mismatch. GitHub Actions runs Python tests, the three RTL simulations, and representative Yosys synthesis and structural checks.

## Evidence Boundaries

Python test and report output is reference-model evidence. It validates software behavior over supplied event streams but does not establish RTL behavior, synthesis results, timing closure, throughput, or device latency.

Successful Icarus Verilog bench output is RTL simulation evidence for the tested module vectors. Successful Yosys checks establish synthesizability only for the representative parameter sets in CI. Neither establishes place-and-route, static timing, hardware-in-loop behavior, device utilization, nor production-feed behavior. See [`docs/architecture.md`](docs/architecture.md) for the component boundary.

## Repository Layout

```text
src/fpga_hardware_timestamping_core/  Python package and packaged fixture
tests/                                Python behavioral tests
rtl/                                  SystemVerilog modules and benches
examples/                             Multi-channel CSV fixture
docs/                                 Architecture and timing contracts
.github/workflows/ci.yml              Python and RTL CI
```

## Security

Review [`SECURITY.md`](SECURITY.md) before using untrusted input or integrating calibration controls. Calibration values and counter widths affect every output timestamp and should be treated as controlled configuration.

## License

MIT. See [`LICENSE`](LICENSE).
