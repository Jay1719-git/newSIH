from __future__ import annotations

import logging
import re
from typing import Any

_SENSITIVE_KEY_PARTS = (
    "apaar",
    "aadhaar",
    "csv",
    "password",
    "secret",
    "authorization",
    "token",
    "full_name",
    "date_of_birth",
    "dob",
    "email",
    "student_ref",
)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(apaar(?:_id)?|aadhaar(?:_no|_id)?|csv_content|password|secret|authorization|token|"
    r"full_name|date_of_birth|dob|email|student_ref)"
    r"(\s*[:=]\s*)([^,;\s]+)"
)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS)
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_redact(item) for item in value)
    if isinstance(value, str):
        return _SENSITIVE_ASSIGNMENT.sub(r"\1\2[REDACTED]", value)
    return value


class SensitiveDataRedactionFilter(logging.Filter):
    """Redact common sensitive values from structured and interpolated log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, (dict, list, tuple)):
            record.msg = _redact(record.msg)
        elif isinstance(record.msg, str):
            record.msg = _redact(record.msg)

        if record.args:
            record.args = _redact(record.args)

        for key, value in list(record.__dict__.items()):
            if any(part in key.lower() for part in _SENSITIVE_KEY_PARTS):
                record.__dict__[key] = "[REDACTED]"
            elif isinstance(value, (dict, list, tuple, str)):
                record.__dict__[key] = _redact(value)
        return True


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    for handler in root.handlers:
        if not any(isinstance(item, SensitiveDataRedactionFilter) for item in handler.filters):
            handler.addFilter(SensitiveDataRedactionFilter())
