# Architecture

## Purpose

This repository defines a deterministic timestamp-processing reference system for multi-channel FPGA market-data pipelines. It separates whole-stream analysis from small streaming RTL primitives so each boundary can be tested directly.

## Data Flow

```text
CSV rows / Python events
        |
        v
per-channel sequence monitor -----> sequence diagnostics
        |
        v
per-channel counter unwrapper
        |
        v
per-channel offset/drift calibration
        |
        v
bounded-lateness reorder buffer ---> late-event count
        |
        +---------------------------> JSON / Markdown reports
        |
        +---------------------------> skew / latency / jitter metrics
```

Arrival order is the order supplied to `analyze_events`. State is isolated per channel for sequence monitoring and counter unwrapping. The reorder buffer is shared because it establishes a deterministic order across channels.

## Python Components

| Component | Responsibility |
| --- | --- |
| `calibration.py` | Signed integer offset and drift correction |
| `counters.py` | Modular counter expansion around a per-channel high-water anchor |
| `sequence.py` | Arrival-order sequence classification and missing-count diagnostics |
| `reorder.py` | Heap-backed bounded-lateness ordering and watermark tracking |
| `analysis.py` | End-to-end orchestration and timing metrics |
| `csvio.py` | Strict CSV schema and integer parsing |
| `reporting.py` | Stable report schema and Markdown rendering |
| `cli.py` | Command-line configuration, fixture loading, and output |
| `timestamping.py` | Compatibility data types and original helper functions |

The Python model uses arbitrary-precision integers. It retains all seen sequence numbers per channel so any repeated value can be classified as a duplicate, including a non-adjacent repeat.

## RTL Components

`timestamp_unwrapper` tracks the highest unwrapped timestamp seen by one channel. It maps a new counter value into the current, previous, or next epoch using the half-counter-range rule. A late value does not move the high-water anchor backward.

`timestamp_normalizer` implements the documented signed offset and drift equation with integer division. Inputs and outputs are registered with one valid indication. A normalized value outside the signed `TIMESTAMP_WIDTH + 1` output range is saturated to the nearest boundary and raises `overflow` for the same valid cycle. The module does not unwrap counters.

`sequence_order_guard` is instantiated once per channel. It tracks the highest sequence and timestamp, then emits one-cycle status flags. Its duplicate flag identifies repetition of the current highest sequence. Older values are classified as out of order because retaining an unbounded history is not appropriate for this primitive.

The RTL does not implement the cross-channel reorder buffer, CSV, metrics, or reports. Those are reference-model and system-integration functions.

## Determinism

Buffered events are ordered by:

1. normalized timestamp
2. channel identifier
3. sequence number
4. arrival index

An internal insertion counter resolves records that are identical on all public keys. Channel identifiers use Python string ordering. Consumers that need numeric channel priority should map channel names before analysis.

## Validation And Failure Handling

The CSV reader accepts only the canonical three- or four-column header and rejects missing, extra, reordered, or duplicate columns, trailing fields, empty channels, and non-ASCII decimal integers. Source, event, diagnostic, and calibration identifiers must be valid UTF-8 text without terminal control or Unicode format characters; report rendering repeats these checks and neutralizes unsafe display text defensively. Sequence numbers, raw counter values, and arrival timestamps must be non-negative; unwrapped and normalized timestamps are signed. Counter values must fit the configured width. Counter width must be at least two bits, and allowed lateness must be non-negative. To admit arbitrary-precision fields past the standard-library default, the reader temporarily raises the process-wide CSV field limit to at most the decoded input length while holding a module lock, then restores the prior value on every success or failure path. The CLI rejects identical input and output paths as well as filesystem aliases before report publication, returns an argument error for invalid input or configuration, and atomically replaces a completed report without exposing partial output.

RTL parameter and input ranges are integration contracts. The normalizer exposes and saturates final-result overflow; internal operands remain fixed width. Integrators must still select widths that contain the expected timestamp, epoch, offset, and drift-product ranges.

## Evidence

The Python suite and rendered reports provide Python reference-model evidence only. They test the software algorithms, parsing, diagnostics, metrics, ordering, and CLI behavior.

The self-checking Icarus Verilog benches provide RTL simulation evidence only when they are compiled and run successfully. They cover selected vectors for rollover, half-range behavior, late samples, signed calibration, truncation, saturation, reset, back-to-back traffic, sequence classifications, and timestamp regression. CI also synthesizes representative configurations with Yosys and runs structural checks. The repository contains no place-and-route, static-timing, hardware-in-loop, device-utilization, or measured production-feed evidence.
