import csv
import hashlib
import json
import os
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 CI job
    import tomli as tomllib

from fpga_hardware_timestamping_core.analysis import analyze_events
from fpga_hardware_timestamping_core.cli import main
from fpga_hardware_timestamping_core.csvio import read_csv_events
from fpga_hardware_timestamping_core.reporting import render_json_report


def test_csv_reader_accepts_optional_arrival_timestamp(tmp_path):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "channel,sequence,raw_ns,arrival_ns\nA,1,250,270\nB,1,4,281\n",
        encoding="utf-8",
    )

    events = read_csv_events(csv_path)

    assert [
        (event.channel, event.sequence, event.raw_ns, event.arrival_ns)
        for event in events
    ] == [
        ("A", 1, 250, 270),
        ("B", 1, 4, 281),
    ]


def test_csv_reader_returns_empty_list_for_header_only_file(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("channel,sequence,raw_ns,arrival_ns\n", encoding="utf-8")

    assert read_csv_events(csv_path) == []


def test_csv_reader_rejects_missing_required_column(tmp_path):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text("channel,sequence\nA,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="raw_ns"):
        read_csv_events(csv_path)


@pytest.mark.parametrize(
    "header",
    [
        "sequence,channel,raw_ns,arrival_ns",
        "channel,sequence,raw_ns,arrival_ns,extra",
        "channel,sequence,raw_ns,raw_ns",
    ],
)
def test_csv_reader_rejects_noncanonical_headers(tmp_path, header):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(f"{header}\nA,1,2,3\n", encoding="utf-8")

    with pytest.raises(ValueError, match="header"):
        read_csv_events(csv_path)


def test_csv_reader_rejects_trailing_fields(tmp_path):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "channel,sequence,raw_ns,arrival_ns\nA,1,2,3,unexpected\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="row 2"):
        read_csv_events(csv_path)


def test_csv_and_json_support_integers_beyond_python_decimal_digit_guard(tmp_path):
    raw_text = "1" + "0" * 5_000
    csv_path = tmp_path / "large.csv"
    csv_path.write_text(
        f"channel,sequence,raw_ns\nA,1,{raw_text}\n",
        encoding="utf-8",
    )

    events = read_csv_events(csv_path)
    result = analyze_events(events, counter_bits=20_000)
    report = json.loads(render_json_report(result))

    assert report["events"][0]["raw_ns"] == raw_text
    assert report["events"][0]["normalized_ns"] == raw_text


def test_csv_reader_supports_a_131073_digit_field_and_restores_the_parser_limit(
    tmp_path,
):
    original_limit = csv.field_size_limit()
    raw_text = "1" + "0" * 131_072
    csv_path = tmp_path / "large-field.csv"
    csv_path.write_text(
        f"channel,sequence,raw_ns\nA,1,{raw_text}\n",
        encoding="utf-8",
    )

    events = read_csv_events(csv_path)

    assert len(events) == 1
    assert events[0].raw_ns.bit_length() > 400_000
    assert events[0].raw_ns % (10**32) == 0
    assert csv.field_size_limit() == original_limit


def test_csv_reader_restores_the_parser_limit_after_a_large_invalid_field(tmp_path):
    original_limit = csv.field_size_limit()
    invalid_raw = "1" * 131_072 + "x"
    csv_path = tmp_path / "invalid-large-field.csv"
    csv_path.write_text(
        f"channel,sequence,raw_ns\nA,1,{invalid_raw}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="raw_ns must be an ASCII base-10 integer"):
        read_csv_events(csv_path)

    assert csv.field_size_limit() == original_limit


def test_cli_writes_json_report_for_explicit_input(tmp_path):
    csv_path = tmp_path / "events.csv"
    output_path = tmp_path / "report.json"
    csv_path.write_text(
        "channel,sequence,raw_ns,arrival_ns\nA,1,250,270\nA,2,2,280\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(csv_path),
            "--counter-bits",
            "8",
            "--lateness-ns",
            "10",
            "--calibration",
            "A,-10,0,0",
            "--format",
            "json",
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["summary"]["event_count"] == 2
    assert [event["normalized_ns"] for event in report["events"]] == [260, 268]
    assert report["source"]["name"] == "events.csv"
    assert len(report["source"]["sha256"]) == 64
    assert report["configuration"]["counter_bits"] == 8


def test_cli_hashes_the_exact_bytes_it_analyzes(tmp_path, monkeypatch):
    csv_path = tmp_path / "events.csv"
    output_path = tmp_path / "report.json"
    csv_path.write_bytes(b"channel,sequence,raw_ns\nA,1,1\n")
    replacement = b"channel,sequence,raw_ns\nA,1,2\n"
    original_read_bytes = Path.read_bytes

    def controlled_read_bytes(path):
        if path == csv_path:
            return replacement
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", controlled_read_bytes)

    assert (
        main([str(csv_path), "--counter-bits", "8", "--output", str(output_path)]) == 0
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["events"][0]["raw_ns"] == 2
    assert report["source"]["sha256"] == hashlib.sha256(replacement).hexdigest()


def test_cli_uses_packaged_fixture_when_input_is_omitted(tmp_path):
    output_path = tmp_path / "fixture-report.json"

    exit_code = main(["--format", "json", "--output", str(output_path)])

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["summary"]["channel_count"] >= 2
    assert report["summary"]["event_count"] >= 6


def test_cli_creates_output_parent_directory(tmp_path):
    output_path = tmp_path / "nested" / "reports" / "timestamps.json"

    exit_code = main(["--format", "json", "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()


def test_cli_report_uses_lf_bytes(tmp_path):
    output_path = tmp_path / "report.md"

    assert main(["--format", "markdown", "--output", str(output_path)]) == 0

    assert b"\r\n" not in output_path.read_bytes()
    assert output_path.read_bytes().endswith(b"\n")


@pytest.mark.parametrize("alias_kind", ["same-path", "hard-link"])
def test_cli_rejects_input_output_aliases_without_mutating_source(tmp_path, alias_kind):
    csv_path = tmp_path / "events.csv"
    original = b"channel,sequence,raw_ns\nA,1,7\n"
    csv_path.write_bytes(original)
    output_path = csv_path
    if alias_kind == "hard-link":
        output_path = tmp_path / "report.json"
        os.link(csv_path, output_path)

    with pytest.raises(SystemExit) as error:
        main([str(csv_path), "--output", str(output_path)])

    assert error.value.code == 2
    assert csv_path.read_bytes() == original
    assert output_path.read_bytes() == original


def test_cli_publishes_output_atomically(tmp_path, monkeypatch):
    output_path = tmp_path / "report.json"
    output_path.write_text("previous\n", encoding="utf-8", newline="\n")

    def fail_replace(source, destination):
        raise OSError("injected publication failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(SystemExit) as error:
        main(["--format", "json", "--output", str(output_path)])

    assert error.value.code == 2
    assert output_path.read_bytes() == b"previous\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_packaging_defines_console_script():
    with open("pyproject.toml", "rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    assert (
        project["scripts"]["fpga-timestamp-report"]
        == "fpga_hardware_timestamping_core.cli:main"
    )


def test_package_and_ci_enforce_supported_python_and_ruff_quality_gates():
    with open("pyproject.toml", "rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert pyproject["project"]["requires-python"] == ">=3.10,<3.15"
    assert any(
        requirement.startswith("ruff")
        for requirement in pyproject["project"]["optional-dependencies"]["dev"]
    )
    for version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
        assert f'"{version}"' in workflow
    assert "ruff check ." in workflow
    assert "ruff format --check ." in workflow
