from __future__ import annotations

import csv
import json

import pytest

from app import cli
from app.demo_data import generate_demo_datasets


def test_synthetic_datasets_are_reproducible_and_scenario_labelled(tmp_path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    manifest_a = generate_demo_datasets(first)
    manifest_b = generate_demo_datasets(second)
    assert manifest_a == manifest_b
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
    assert manifest_a["seed"] == 26263
    valid = (first / "01_valid_kurukshetra.csv").read_bytes()
    assert valid == (first / "06_repeat_identical_upload.csv").read_bytes()
    review_rows = list(csv.DictReader((first / "02_review_kurukshetra.csv").open(encoding="utf-8")))
    assert review_rows[0]["apaar_id"] == "812345678901"
    assert review_rows[1]["apaar_id"] == ""
    invalid_rows = list(
        csv.DictReader((first / "03_invalid_kurukshetra.csv").open(encoding="utf-8"))
    )
    assert invalid_rows[0]["apaar_id"] == "123"
    assert invalid_rows[1]["dob"] == "not-a-date"
    assert invalid_rows[2]["program_code"] == "UNKNOWN"
    assert invalid_rows[3]["enrollment_year"] == "2099"
    cross_rows = list(
        csv.DictReader((first / "04_cross_institution_delhi.csv").open(encoding="utf-8"))
    )
    assert cross_rows[0]["apaar_id"] == "812345678901"
    overflow_rows = list(
        csv.DictReader((first / "05_capacity_overflow_kurukshetra.csv").open(encoding="utf-8"))
    )
    assert len(overflow_rows) == 2
    assert json.loads((first / "manifest.json").read_text(encoding="utf-8")) == manifest_a


def test_demo_reset_requires_explicit_confirmation_and_environment(monkeypatch) -> None:
    monkeypatch.setattr(cli, "require_local_demo_database", lambda: None)
    monkeypatch.delenv("WEAVE_ALLOW_DEMO_RESET", raising=False)
    with pytest.raises(SystemExit, match="Reset refused"):
        cli.reset_demo("RESET-WEAVE-DEMO")
