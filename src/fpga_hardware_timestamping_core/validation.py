from __future__ import annotations

import unicodedata


_UNSAFE_IDENTIFIER_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})


def validate_identifier(
    value: str,
    *,
    field: str,
    allow_empty: bool = False,
) -> str:
    """Validate an identifier before it reaches a report or terminal."""

    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{field} must not be empty")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"{field} must contain valid UTF-8 text") from error
    if any(
        unicodedata.category(character) in _UNSAFE_IDENTIFIER_CATEGORIES
        for character in value
    ):
        raise ValueError(f"{field} must not contain control or format characters")
    return value


def neutralize_terminal_controls(value: str) -> str:
    """Return UTF-8-safe display text even for manually assembled report data."""

    return (
        "".join(
            "\N{REPLACEMENT CHARACTER}"
            if unicodedata.category(character) in _UNSAFE_IDENTIFIER_CATEGORIES
            else character
            for character in value
        )
        .encode("utf-8", errors="replace")
        .decode("utf-8")
    )
