from __future__ import annotations

import csv
from contextlib import contextmanager
import io
from pathlib import Path
from threading import RLock
from typing import TextIO

from .integers import parse_ascii_integer
from .timestamping import TimestampedEvent


REQUIRED_HEADER = ("channel", "sequence", "raw_ns")
FULL_HEADER = (*REQUIRED_HEADER, "arrival_ns")
_FIELD_SIZE_LOCK = RLock()


@contextmanager
def _csv_field_limit(required_limit: int):
    """Temporarily enlarge csv's process-wide limit for one serialized parse."""

    with _FIELD_SIZE_LOCK:
        previous_limit = csv.field_size_limit()
        changed = required_limit > previous_limit
        if changed:
            csv.field_size_limit(required_limit)
        try:
            yield
        finally:
            if changed:
                csv.field_size_limit(previous_limit)


def _parse_integer(value: str, *, row_number: int, field: str) -> int:
    try:
        return parse_ascii_integer(value)
    except ValueError as error:
        raise ValueError(
            f"row {row_number}: {field} must be an ASCII base-10 integer"
        ) from error


def _parse_csv_stream(csv_file: TextIO) -> list[TimestampedEvent]:
    reader = csv.reader(csv_file, strict=True)
    header = tuple(next(reader, ()))
    if header not in (REQUIRED_HEADER, FULL_HEADER):
        raise ValueError(
            "CSV header must be exactly channel,sequence,raw_ns "
            "with optional trailing arrival_ns"
        )

    events: list[TimestampedEvent] = []
    for row_number, row in enumerate(reader, start=2):
        if len(row) != len(header):
            raise ValueError(
                f"row {row_number}: expected {len(header)} fields, received {len(row)}"
            )
        channel = row[0].strip()
        if not channel:
            raise ValueError(f"row {row_number}: channel must not be empty")
        try:
            sequence = _parse_integer(row[1], row_number=row_number, field="sequence")
            raw_ns = _parse_integer(row[2], row_number=row_number, field="raw_ns")
            arrival_value = row[3] if len(header) == 4 else ""
            arrival_ns = (
                _parse_integer(arrival_value, row_number=row_number, field="arrival_ns")
                if arrival_value != ""
                else None
            )
        except (TypeError, ValueError) as error:
            if isinstance(error, ValueError) and str(error).startswith(
                f"row {row_number}:"
            ):
                raise
            raise ValueError(f"row {row_number}: invalid event data") from error
        events.append(
            TimestampedEvent(
                channel=channel,
                sequence=sequence,
                raw_ns=raw_ns,
                arrival_ns=arrival_ns,
            )
        )
    return events


def read_csv_event_bytes(data: bytes) -> list[TimestampedEvent]:
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must be valid UTF-8") from error
    with _csv_field_limit(len(text)):
        try:
            return _parse_csv_stream(io.StringIO(text, newline=""))
        except csv.Error as error:
            raise ValueError(f"invalid CSV: {error}") from error


def read_csv_events(path: str | Path) -> list[TimestampedEvent]:
    csv_path = Path(path)
    return read_csv_event_bytes(csv_path.read_bytes())
