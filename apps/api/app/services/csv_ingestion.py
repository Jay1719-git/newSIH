from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 10_000
MAX_CSV_FIELD_CHARS = 16_384
REQUIRED_COLUMNS = frozenset(
    {
        "student_ref",
        "apaar_id",
        "full_name",
        "dob",
        "program_code",
        "enrollment_year",
        "consent_granted",
    }
)
OPTIONAL_COLUMNS = frozenset(
    {
        "admission_date",
        "seat_category_code",
        "supernumerary_seat",
        "nri_status",
        "oci_status",
        "foreign_national_status",
        "admission_status",
    }
)
ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
_AADHAAR_HEADER = re.compile(r"aadhaar|aadhar", re.IGNORECASE)


class CsvStructureError(ValueError):
    """A file-level CSV error; distinct from findings about an individual row."""


@dataclass(frozen=True)
class ParsedCsv:
    columns: tuple[str, ...]
    rows: tuple[tuple[int, dict[str, str | None]], ...]


def parse_csv_content(content: str) -> ParsedCsv:
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise CsvStructureError("CSV exceeds the maximum upload size.")
    stream = io.StringIO(content.lstrip("\ufeff"), newline="")
    try:
        reader = csv.reader(stream, strict=True)
        raw_header = next(reader, None)
        if raw_header is None:
            raise CsvStructureError("CSV must contain a header row.")
        header = tuple(cell.strip().lower() for cell in raw_header)
        if not header or any(not cell for cell in header):
            raise CsvStructureError("CSV header contains an empty column name.")
        if len(set(header)) != len(header):
            raise CsvStructureError("CSV header contains duplicate column names.")
        if any(_AADHAAR_HEADER.search(column) for column in header):
            raise CsvStructureError("Aadhaar columns are not accepted.")
        missing = REQUIRED_COLUMNS - set(header)
        unknown = set(header) - ALLOWED_COLUMNS
        if missing:
            raise CsvStructureError("CSV is missing one or more required columns.")
        if unknown:
            raise CsvStructureError("CSV contains unsupported columns.")

        data: list[tuple[int, dict[str, str | None]]] = []
        while True:
            try:
                cells = next(reader)
            except StopIteration:
                break
            if not cells or (len(cells) == 1 and not cells[0].strip()):
                continue
            if len(cells) != len(header):
                raise CsvStructureError("CSV contains a row with an inconsistent number of fields.")
            if any(len(cell) > MAX_CSV_FIELD_CHARS for cell in cells):
                raise CsvStructureError("CSV contains a field exceeding the parser limit.")
            data.append(
                (
                    reader.line_num,
                    {column: value.strip() for column, value in zip(header, cells, strict=True)},
                )
            )
            if len(data) > MAX_CSV_ROWS:
                raise CsvStructureError("CSV exceeds the maximum row count.")
    except (csv.Error, UnicodeError) as exc:
        raise CsvStructureError("CSV is malformed.") from exc
    if not data:
        raise CsvStructureError("CSV must contain at least one data row.")
    return ParsedCsv(columns=header, rows=tuple(data))


def spreadsheet_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip("\t\r\n ").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
