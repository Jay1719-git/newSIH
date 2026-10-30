import logging

from app.core.logging import SensitiveDataRedactionFilter


def test_sensitive_identifiers_are_redacted_from_log_message_and_fields() -> None:
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "APAAR_ID=123456789012; email=person@example.test",
        (),
        None,
    )
    record.student_ref = "SYNTH-123456"
    SensitiveDataRedactionFilter().filter(record)
    rendered = record.getMessage() + str(record.__dict__)
    assert "123456789012" not in rendered
    assert "person@example.test" not in rendered
    assert "SYNTH-123456" not in rendered
