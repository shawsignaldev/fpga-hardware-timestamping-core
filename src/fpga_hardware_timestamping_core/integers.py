from __future__ import annotations

import re
from typing import Any


_ASCII_INTEGER = re.compile(r"[+-]?[0-9]+\Z")
_CHUNK_DIGITS = 9
_CHUNK_BASE = 10**_CHUNK_DIGITS
_NATIVE_JSON_LIMIT = 10**4_000


def parse_ascii_integer(value: str) -> int:
    """Parse an ASCII decimal integer without Python's decimal digit guard."""

    if not isinstance(value, str) or not _ASCII_INTEGER.fullmatch(value):
        raise ValueError("value must be an ASCII base-10 integer")
    negative = value.startswith("-")
    digits = value[1:] if value[:1] in "+-" else value
    parsed = 0
    for start in range(0, len(digits), _CHUNK_DIGITS):
        chunk = digits[start : start + _CHUNK_DIGITS]
        parsed = parsed * (10 ** len(chunk)) + int(chunk)
    return -parsed if negative else parsed


def integer_to_decimal(value: int) -> str:
    """Format an integer without Python's decimal digit guard."""

    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("value must be an integer")
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    remaining = abs(value)
    chunks: list[int] = []
    while remaining:
        remaining, chunk = divmod(remaining, _CHUNK_BASE)
        chunks.append(chunk)
    return (
        sign
        + str(chunks[-1])
        + "".join(f"{chunk:0{_CHUNK_DIGITS}d}" for chunk in reversed(chunks[:-1]))
    )


def json_safe_integers(value: Any) -> Any:
    """Convert only integers too large for portable JSON conversion to strings."""

    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        if value <= -_NATIVE_JSON_LIMIT or value >= _NATIVE_JSON_LIMIT:
            return integer_to_decimal(value)
        return value
    if isinstance(value, list):
        return [json_safe_integers(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe_integers(item) for item in value]
    if isinstance(value, dict):
        return {key: json_safe_integers(item) for key, item in value.items()}
    return value
