from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

DEMO_SEED = 26263
HEADERS = [
    "student_ref",
    "apaar_id",
    "full_name",
    "dob",
    "program_code",
    "enrollment_year",
    "consent_granted",
    "seat_category_code",
]

VALID_ROW = [
    "DEMO-KKR-001",
    "812345678901",
    "Nila Demo",
    "2006-04-12",
    "BTECH-CSE",
    "2026",
    "true",
    "OPEN",
]
DATASETS: dict[str, dict] = {
    "01_valid_kurukshetra.csv": {
        "institution": "SYNTH-KKR-001",
        "rows": [VALID_ROW],
        "expected_scenarios": [
            "one eligible row",
            "upload persists a batch",
            "row can be committed within approved intake",
        ],
    },
    "02_review_kurukshetra.csv": {
        "institution": "SYNTH-KKR-001",
        "rows": [
            [
                "DEMO-KKR-DUP",
                "812345678901",
                "Nila Demo",
                "2006-04-12",
                "BTECH-CSE",
                "2026",
                "true",
                "OPEN",
            ],
            ["DEMO-KKR-MISSING", "", "Avi Demo", "2005-11-03", "BTECH-CSE", "2026", "true", "OPEN"],
        ],
        "expected_scenarios": [
            "existing keyed identity requires human review",
            "missing APAAR alone is not rejected",
        ],
    },
    "03_invalid_kurukshetra.csv": {
        "institution": "SYNTH-KKR-001",
        "rows": [
            [
                "DEMO-BAD-APAAR",
                "123",
                "Uma Demo",
                "2006-02-01",
                "BTECH-CSE",
                "2026",
                "true",
                "OPEN",
            ],
            [
                "DEMO-BAD-DATE",
                "823456789012",
                "Ira Demo",
                "not-a-date",
                "BTECH-CSE",
                "2026",
                "true",
                "OPEN",
            ],
            [
                "DEMO-BAD-PROGRAM",
                "834567890123",
                "Ravi Demo",
                "2005-09-09",
                "UNKNOWN",
                "2026",
                "true",
                "OPEN",
            ],
            [
                "DEMO-BAD-YEAR",
                "845678901234",
                "Mira Demo",
                "2005-05-05",
                "BTECH-CSE",
                "2099",
                "true",
                "OPEN",
            ],
        ],
        "expected_scenarios": [
            "APAAR format failure",
            "date validation failure",
            "unknown programme",
            "unconfigured academic year",
        ],
    },
    "04_cross_institution_delhi.csv": {
        "institution": "SYNTH-DEL-002",
        "rows": [
            [
                "DEMO-DEL-001",
                "812345678901",
                "Nila Demo",
                "2006-04-12",
                "BTECH-CSE",
                "2026",
                "true",
                "OPEN",
            ]
        ],
        "expected_scenarios": ["potential cross-institution candidate; review lead only"],
    },
    "05_capacity_overflow_kurukshetra.csv": {
        "institution": "SYNTH-KKR-001",
        "rows": [
            [
                "DEMO-OVER-001",
                "856789012345",
                "Tara Demo",
                "2005-08-10",
                "BTECH-CSE",
                "2026",
                "true",
                "OPEN",
            ],
            [
                "DEMO-OVER-002",
                "867890123456",
                "Neel Demo",
                "2005-10-22",
                "BTECH-CSE",
                "2026",
                "true",
                "OPEN",
            ],
        ],
        "expected_scenarios": ["capacity conflict is atomic; no partial batch commit"],
    },
    "06_repeat_identical_upload.csv": {
        "institution": "SYNTH-KKR-001",
        "rows": [VALID_ROW],
        "expected_scenarios": [
            "same canonical contents return the existing batch even with a different filename"
        ],
    },
}


def _csv_text(rows: list[list[str]]) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(HEADERS)
    writer.writerows(rows)
    return output.getvalue()


def generate_demo_datasets(output_dir: Path) -> dict:
    """Write repeatable fictional CSV scenarios and machine-readable expectations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict] = {}
    for filename, spec in DATASETS.items():
        contents = _csv_text(spec["rows"])
        (output_dir / filename).write_text(contents, encoding="utf-8", newline="")
        files[filename] = {
            "institution_code": spec["institution"],
            "row_count": len(spec["rows"]),
            "expected_scenarios": spec["expected_scenarios"],
        }
    manifest = {"seed": DEMO_SEED, "dataset_version": "weave-synthetic-v1", "files": files}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
