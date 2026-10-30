from enum import StrEnum


class InstitutionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    INACTIVE = "INACTIVE"


class UserRole(StrEnum):
    REGULATOR_ADMIN = "regulator_admin"
    REGULATOR_OFFICER = "regulator_officer"
    INSTITUTION_ADMIN = "institution_admin"
    INSTITUTION_OPERATOR = "institution_operator"
    AUDITOR = "auditor"
    STUDENT = "student"
    EXTERNAL_VERIFIER = "external_verifier"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class ProgramStatus(StrEnum):
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    INACTIVE = "INACTIVE"


class AcademicYearStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class EnrolmentStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    FLAGGED_CONFLICT = "FLAGGED_CONFLICT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    ACCEPTED = "ACCEPTED"
    WITHDRAWN = "WITHDRAWN"


class ImportBatchStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_FLAGS = "COMPLETED_WITH_FLAGS"
    FAILED = "FAILED"


class FindingOutcome(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


class ImportRowStatus(StrEnum):
    READY = "READY"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"
    COMMITTED = "COMMITTED"


class ReviewCaseType(StrEnum):
    CROSS_INSTITUTION_DUPLICATE = "CROSS_INSTITUTION_DUPLICATE"
    INTRA_BATCH_DUPLICATE = "INTRA_BATCH_DUPLICATE"
    INTAKE_OVERFLOW = "INTAKE_OVERFLOW"


class ReviewCaseStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    INFO_REQUESTED = "INFO_REQUESTED"


class ConsentStatus(StrEnum):
    GRANTED = "GRANTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class AuditEntityType(StrEnum):
    INSTITUTION = "INSTITUTION"
    USER = "USER"
    ENROLMENT = "ENROLMENT"
    IMPORT_BATCH = "IMPORT_BATCH"
    REVIEW_CASE = "REVIEW_CASE"
    CONSENT = "CONSENT"
    SYSTEM = "SYSTEM"
