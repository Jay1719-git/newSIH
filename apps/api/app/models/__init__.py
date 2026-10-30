"""SQLAlchemy model registry; import every model here for Alembic metadata."""

from app.db.base import Base
from app.models.academics import (
    AcademicProgram,
    AcademicYear,
    ApprovedIntake,
    ProgramAcademicYear,
    SeatCategory,
)
from app.models.audit import AuditEvent
from app.models.auth_session import AuthSession
from app.models.consent import ConsentRecord
from app.models.duplicate import DuplicateCase
from app.models.enums import (
    AcademicYearStatus,
    AuditEntityType,
    ConsentStatus,
    EnrolmentStatus,
    FindingOutcome,
    ImportBatchStatus,
    ImportRowStatus,
    InstitutionStatus,
    ProgramStatus,
    ReviewCaseStatus,
    ReviewCaseType,
    UserRole,
    UserStatus,
)
from app.models.identity import Enrolment, StudentIdentityReference
from app.models.ingestion import DataImportBatch, ImportBatchRow, ValidationFinding
from app.models.institution import Institution
from app.models.review import ReviewCase
from app.models.user import User
from app.models.verifier_grant import ExternalVerifierGrant
from app.models.verification_credential import VerificationCredential

__all__ = [
    "AcademicProgram",
    "AcademicYear",
    "AcademicYearStatus",
    "ApprovedIntake",
    "AuditEntityType",
    "AuditEvent",
    "AuthSession",
    "Base",
    "ConsentRecord",
    "ConsentStatus",
    "DataImportBatch",
    "DuplicateCase",
    "Enrolment",
    "EnrolmentStatus",
    "ExternalVerifierGrant",
    "VerificationCredential",
    "FindingOutcome",
    "ImportBatchRow",
    "ImportBatchStatus",
    "ImportRowStatus",
    "Institution",
    "InstitutionStatus",
    "ProgramAcademicYear",
    "ProgramStatus",
    "ReviewCase",
    "ReviewCaseStatus",
    "ReviewCaseType",
    "SeatCategory",
    "StudentIdentityReference",
    "User",
    "UserRole",
    "UserStatus",
    "ValidationFinding",
]
