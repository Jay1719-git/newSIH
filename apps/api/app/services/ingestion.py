from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth.policies import Action, Principal, authorize_record
from app.core.config import get_settings
from app.models.academics import (
    AcademicProgram,
    AcademicYear,
    ApprovedIntake,
    ProgramAcademicYear,
    SeatCategory,
)
from app.models.audit import AuditEvent
from app.models.enums import (
    AuditEntityType,
    EnrolmentStatus,
    FindingOutcome,
    ImportBatchStatus,
    ImportRowStatus,
    ReviewCaseStatus,
    ReviewCaseType,
    UserRole,
)
from app.models.identity import Enrolment, StudentIdentityReference
from app.models.ingestion import DataImportBatch, ImportBatchRow, ValidationFinding
from app.models.institution import Institution
from app.models.review import ReviewCase
from app.services.csv_ingestion import ParsedCsv, parse_csv_content, spreadsheet_safe
from app.services.duplicate_detection import apaar_fingerprints

logger = logging.getLogger(__name__)
RULESET_VERSION = "2026.10.v1"
APAAR_PATTERN = re.compile(r"^[2-9][0-9]{11}$")
STUDENT_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,79}$")
BOOL_TRUE = frozenset({"true", "1", "yes", "y"})
BOOL_FALSE = frozenset({"false", "0", "no", "n"})
ADMISSION_STATUSES = frozenset({"ADMITTED", "WITHDRAWN", "PENDING_REVIEW"})
ACTIVE_ENROLMENT_STATUSES = (EnrolmentStatus.ACCEPTED, EnrolmentStatus.VERIFIED)


def _normalize_apaar(value: str | None) -> str:
    return "" if not value else re.sub(r"[\s-]", "", value)


def _parse_bool(value: str | None, *, default: bool | None = None) -> bool | None:
    if value is None or not value.strip():
        return default
    normalized = value.strip().casefold()
    if normalized in BOOL_TRUE:
        return True
    if normalized in BOOL_FALSE:
        return False
    return None


def _fingerprint(parsed: ParsedCsv, key: bytes) -> str:
    canonical: list[dict[str, str | None]] = []
    for _, source in parsed.rows:
        row = {key_name: source.get(key_name) for key_name in sorted(parsed.columns)}
        apaar_value = row.get("apaar_id")
        if apaar_value is not None:
            row["apaar_id"] = hmac.new(
                key,
                b"weave-upload-apaar\x00" + _normalize_apaar(apaar_value).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        canonical.append(row)
    material = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hmac.new(key, material.encode("utf-8"), hashlib.sha256).hexdigest()


def _add_finding(
    row: ImportBatchRow,
    code: str,
    outcome: FindingOutcome,
    reason: str,
    field: str | None = None,
    remediation: str | None = None,
) -> None:
    if any(item.rule_code == code for item in row.findings):
        return
    row.findings.append(
        ValidationFinding(
            rule_code=code,
            outcome=outcome,
            reason=reason,
            affected_field=field,
            remediation=remediation,
        )
    )


def _row_status(row: ImportBatchRow) -> ImportRowStatus:
    outcomes = {finding.outcome for finding in row.findings}
    if FindingOutcome.FAIL in outcomes:
        return ImportRowStatus.REJECTED
    if FindingOutcome.REVIEW in outcomes:
        return ImportRowStatus.REVIEW_REQUIRED
    if FindingOutcome.WARN in outcomes:
        return ImportRowStatus.WARNING
    return ImportRowStatus.READY


def _append_audit(
    db: Session,
    *,
    principal: Principal,
    institution_id: uuid.UUID,
    action: str,
    entity_id: uuid.UUID,
    request_id: str,
    summary: str,
    outcome: str = "SUCCESS",
    safe_payload: dict[str, Any] | None = None,
) -> AuditEvent:
    previous = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.institution_id == institution_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
        .with_for_update()
    )
    previous_hash = previous.event_hash if previous else None
    now = datetime.now(UTC)
    payload = {"outcome": outcome, **(safe_payload or {})}
    event_material = json.dumps(
        {
            "action": action,
            "actor_user_id": str(principal.user_id),
            "created_at": now.isoformat(),
            "entity_id": str(entity_id),
            "institution_id": str(institution_id),
            "payload": payload,
            "previous_hash": previous_hash,
            "request_id": request_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    event = AuditEvent(
        institution_id=institution_id,
        actor_user_id=principal.user_id,
        action=action,
        entity_type=AuditEntityType.IMPORT_BATCH,
        entity_id=entity_id,
        request_id=request_id,
        summary=summary,
        payload=payload,
        previous_hash=previous_hash,
        event_hash=hashlib.sha256(event_material).hexdigest(),
        created_at=now,
    )
    db.add(event)
    return event


def _program_maps(db: Session, institution_id: uuid.UUID):
    entries = db.execute(
        select(ProgramAcademicYear, AcademicProgram, AcademicYear)
        .join(AcademicProgram, ProgramAcademicYear.program_id == AcademicProgram.id)
        .join(AcademicYear, ProgramAcademicYear.academic_year_id == AcademicYear.id)
        .where(ProgramAcademicYear.institution_id == institution_id)
    ).all()
    by_program: dict[str, list[tuple[ProgramAcademicYear, AcademicProgram, AcademicYear]]] = (
        defaultdict(list)
    )
    by_year_alias: dict[str, list[AcademicYear]] = defaultdict(list)
    for program_year, program, year in entries:
        if program.status.value == "ACTIVE":
            by_program[program.code.strip().upper()].append((program_year, program, year))
        by_year_alias[year.code.strip().casefold()].append(year)
        by_year_alias[str(year.starts_on.year)].append(year)
    return entries, by_program, by_year_alias


def _validate_rows(
    db: Session,
    *,
    rows: list[ImportBatchRow],
    source_rows: tuple[tuple[int, dict[str, str | None]], ...],
    institution_id: uuid.UUID,
    apaar_key: bytes,
    apaar_key_version: str,
    apaar_keyring: dict[str, bytes],
) -> tuple[list[ReviewCase], dict[uuid.UUID, str]]:
    entries, by_program, year_aliases = _program_maps(db, institution_id)
    program_year_by_id = {pya.id: (pya, program, year) for pya, program, year in entries}
    intake_rows = db.execute(
        select(ApprovedIntake, SeatCategory)
        .outerjoin(SeatCategory, ApprovedIntake.seat_category_id == SeatCategory.id)
        .where(
            ApprovedIntake.program_academic_year_id.in_(program_year_by_id or [uuid.UUID(int=0)])
        )
    ).all()
    intakes: dict[uuid.UUID, dict[str | None, int]] = defaultdict(dict)
    category_by_code: dict[str, uuid.UUID] = {}
    for intake, category in intake_rows:
        code = category.code.upper() if category else None
        intakes[intake.program_academic_year_id][code] = intake.approved_seats
        if category:
            category_by_code[category.code.strip().upper()] = category.id

    enrolled = db.execute(
        select(
            Enrolment.program_academic_year_id,
            Enrolment.seat_category_id,
            Enrolment.student_ref,
        ).where(
            Enrolment.institution_id == institution_id,
            Enrolment.status.in_(ACTIVE_ENROLMENT_STATUSES),
        )
    ).all()
    existing_keys = {(year_id, student_ref.casefold()) for year_id, _, student_ref in enrolled}
    category_counts: Counter[tuple[uuid.UUID, uuid.UUID | None]] = Counter(
        (year_id, category_id) for year_id, category_id, _ in enrolled
    )
    total_counts: Counter[uuid.UUID] = Counter(year_id for year_id, _, _ in enrolled)

    identity_by_digest = {
        (identity.key_version, identity.hmac_digest): identity
        for identity in db.scalars(
            select(StudentIdentityReference).where(
                StudentIdentityReference.key_version.in_(tuple(apaar_keyring))
            )
        )
    }
    seen_keys: dict[tuple[uuid.UUID, str], ImportBatchRow] = {}
    seen_apaar: dict[str, ImportBatchRow] = {}
    review_cases: list[ReviewCase] = []
    category_code_by_row: dict[uuid.UUID, str] = {}
    counter_pool: Counter[tuple[uuid.UUID, str | None]] = Counter()
    total_request_counts: Counter[uuid.UUID] = Counter()

    for row, (_line_number, values) in zip(rows, source_rows, strict=True):
        student_ref = (values.get("student_ref") or "").strip()
        name = (values.get("full_name") or "").strip()
        dob_text = (values.get("dob") or "").strip()
        program_code = (values.get("program_code") or "").strip().upper()
        year_text = (values.get("enrollment_year") or "").strip()
        apaar_text = (values.get("apaar_id") or "").strip()
        row.student_ref = student_ref or None
        row.full_name = name[:200] or None
        row.date_of_birth = None
        row.consent_granted = _parse_bool(values.get("consent_granted"))

        if not student_ref:
            _add_finding(
                row,
                "STUDENT_REF_REQUIRED",
                FindingOutcome.FAIL,
                "Student ID or roll number is required.",
                "student_ref",
            )
        elif not STUDENT_REF_PATTERN.fullmatch(student_ref):
            _add_finding(
                row,
                "STUDENT_REF_FORMAT",
                FindingOutcome.FAIL,
                "Student ID contains unsupported characters or is too long.",
                "student_ref",
            )
        if not name or len(name) > 200 or any(ord(c) < 32 for c in name):
            _add_finding(
                row,
                "FULL_NAME_INVALID",
                FindingOutcome.FAIL,
                "Full name is required and must be at most 200 characters.",
                "full_name",
            )
        if dob_text:
            try:
                parsed_dob = date.fromisoformat(dob_text)
                if parsed_dob > date.today():
                    raise ValueError
                row.date_of_birth = parsed_dob.isoformat()
            except ValueError:
                _add_finding(
                    row,
                    "DOB_FORMAT_INVALID",
                    FindingOutcome.FAIL,
                    "Date of birth must be a valid ISO date.",
                    "dob",
                )
        else:
            _add_finding(
                row, "DOB_REQUIRED", FindingOutcome.FAIL, "Date of birth is required.", "dob"
            )

        raw_apaar = _normalize_apaar(apaar_text)
        if not raw_apaar:
            row.masked_apaar = "NOT PROVIDED"
            _add_finding(
                row,
                "APAAR_NOT_PROVIDED",
                FindingOutcome.WARN,
                "APAAR was not provided; this synthetic record remains a provisional identifier.",
                "apaar_id",
                "Provide synthetic APAAR when available; absence alone does not reject admission.",
            )
        elif not APAAR_PATTERN.fullmatch(raw_apaar):
            row.masked_apaar = "INVALID FORMAT"
            _add_finding(
                row,
                "APAAR_FORMAT_INVALID",
                FindingOutcome.FAIL,
                "APAAR reference format is invalid; this check does not verify identity.",
                "apaar_id",
            )
        else:
            row.masked_apaar = f"****-****-{raw_apaar[-4:]}"
            _add_finding(
                row,
                "APAAR_FORMAT_VALID",
                FindingOutcome.PASS,
                "APAAR has the expected synthetic format; no identity verification was performed.",
                "apaar_id",
            )
            apaar_fingerprint_set = sorted(apaar_fingerprints(raw_apaar, apaar_keyring))
            identity = next(
                (
                    identity_by_digest[fingerprint]
                    for fingerprint in apaar_fingerprint_set
                    if fingerprint in identity_by_digest
                ),
                None,
            )
            digest = next(
                digest_value
                for version, digest_value in apaar_fingerprint_set
                if version == apaar_key_version
            )
            if identity:
                row.identity_reference_id = identity.id
                _add_finding(
                    row,
                    "APAAR_DUPLICATE_REVIEW",
                    FindingOutcome.REVIEW,
                    "This synthetic APAAR reference already exists; human review is required.",
                    "apaar_id",
                )
            else:
                identity_id = db.scalar(
                    pg_insert(StudentIdentityReference)
                    .values(
                        key_version=apaar_key_version,
                        normalization_version="identity-norm-v1",
                        hmac_digest=digest,
                        masked_apaar=row.masked_apaar,
                    )
                    .on_conflict_do_nothing(index_elements=["key_version", "hmac_digest"])
                    .returning(StudentIdentityReference.id)
                )
                identity = (
                    db.get(StudentIdentityReference, identity_id)
                    if identity_id
                    else db.scalar(
                        select(StudentIdentityReference).where(
                            StudentIdentityReference.key_version == apaar_key_version,
                            StudentIdentityReference.hmac_digest == digest,
                        )
                    )
                )
                if identity is None:
                    raise RuntimeError("APAAR reference could not be safely matched")
                identity_by_digest[(apaar_key_version, digest)] = identity
                row.identity_reference_id = identity.id
            identity_key = str(identity.id)
            if identity_key in seen_apaar:
                _add_finding(
                    row,
                    "APAAR_DUPLICATE_IN_BATCH",
                    FindingOutcome.REVIEW,
                    "APAAR repeats within this batch; human review is required.",
                    "apaar_id",
                )
                _add_finding(
                    seen_apaar[identity_key],
                    "APAAR_DUPLICATE_IN_BATCH",
                    FindingOutcome.REVIEW,
                    "APAAR repeats within this batch; human review is required.",
                    "apaar_id",
                )
            else:
                seen_apaar[identity_key] = row

        consent = row.consent_granted
        consent_text = values.get("consent_granted")
        if consent_text and consent is None:
            _add_finding(
                row,
                "CONSENT_FORMAT_INVALID",
                FindingOutcome.FAIL,
                "Consent value must be true or false.",
                "consent_granted",
            )
        elif consent is None or not consent:
            _add_finding(
                row,
                "CONSENT_NOT_CONFIRMED",
                FindingOutcome.WARN,
                "Consent is unconfirmed; consent-gated verification and disclosure stay disabled.",
                "consent_granted",
            )

        program_options = by_program.get(program_code, [])
        if not program_code:
            _add_finding(
                row,
                "PROGRAM_REQUIRED",
                FindingOutcome.FAIL,
                "Programme code is required.",
                "program_code",
            )
        elif not program_options:
            _add_finding(
                row,
                "PROGRAM_UNKNOWN",
                FindingOutcome.FAIL,
                "Programme is not configured for the authenticated institution.",
                "program_code",
            )

        matched_year: AcademicYear | None = None
        alias_options = year_aliases.get(year_text.casefold(), []) if year_text else []
        distinct_years = {item.id: item for item in alias_options}
        if not year_text:
            _add_finding(
                row,
                "ACADEMIC_YEAR_REQUIRED",
                FindingOutcome.FAIL,
                "Academic year is required.",
                "enrollment_year",
            )
        elif len(distinct_years) == 1:
            matched_year = next(iter(distinct_years.values()))
        else:
            _add_finding(
                row,
                "ACADEMIC_YEAR_UNMAPPED",
                FindingOutcome.FAIL,
                "Academic year does not match a configured year or its explicit start-year alias.",
                "enrollment_year",
            )

        selected = None
        if matched_year and program_options:
            selected = next(
                (item for item in program_options if item[2].id == matched_year.id), None
            )
            if selected is None:
                _add_finding(
                    row,
                    "PROGRAM_YEAR_MISMATCH",
                    FindingOutcome.FAIL,
                    "Programme is not configured for this academic year.",
                    "enrollment_year",
                )
        if selected:
            program_year, _, academic_year = selected
            row.program_academic_year_id = program_year.id
            _add_finding(
                row,
                "PROGRAM_YEAR_MATCH",
                FindingOutcome.PASS,
                "Programme and academic year match the authenticated institution configuration.",
                "program_code",
            )
            try:
                admission_date = date.fromisoformat((values.get("admission_date") or "").strip())
                row.admission_date = admission_date
            except ValueError:
                if values.get("admission_date"):
                    _add_finding(
                        row,
                        "ADMISSION_DATE_FORMAT_INVALID",
                        FindingOutcome.FAIL,
                        "Admission date must be a valid ISO date.",
                        "admission_date",
                    )
                else:
                    _add_finding(
                        row,
                        "ADMISSION_DATE_MISSING",
                        FindingOutcome.WARN,
                        "Admission date is absent; date-window validation was not performed.",
                        "admission_date",
                    )
            if (
                row.admission_date
                and not academic_year.starts_on <= row.admission_date <= academic_year.ends_on
            ):
                _add_finding(
                    row,
                    "ADMISSION_OUTSIDE_YEAR_WINDOW",
                    FindingOutcome.FAIL,
                    "Admission date is outside the configured academic-year window.",
                    "admission_date",
                )

            category_code = (values.get("seat_category_code") or "").strip().upper() or None
            if category_code:
                # Category lookup is limited to configured categories and never creates a pool.
                category_id = category_by_code.get(category_code)
                if category_id is None:
                    category_id = db.scalar(
                        select(SeatCategory.id).where(
                            func.upper(SeatCategory.code) == category_code,
                            SeatCategory.is_active.is_(True),
                        )
                    )
                    if category_id:
                        category_by_code[category_code] = category_id
                if category_id is None:
                    _add_finding(
                        row,
                        "SEAT_CATEGORY_UNKNOWN",
                        FindingOutcome.REVIEW,
                        "Seat category is not configured; no intake pool was inferred.",
                        "seat_category_code",
                    )
                else:
                    row.seat_category_id = category_id
                    category_code_by_row[row.id] = category_code
                    if category_code not in intakes.get(program_year.id, {}):
                        _add_finding(
                            row,
                            "SEAT_POOL_UNCONFIGURED",
                            FindingOutcome.REVIEW,
                            "No approved intake exists for this programme, year, category.",
                            "seat_category_code",
                        )
            elif None not in intakes.get(program_year.id, {}):
                _add_finding(
                    row,
                    "SEAT_CATEGORY_REQUIRED",
                    FindingOutcome.REVIEW,
                    "No total intake exists; provide a configured seat category.",
                    "seat_category_code",
                )
            else:
                category_code_by_row[row.id] = ""

            flag_values: dict[str, bool] = {}
            for field in (
                "supernumerary_seat",
                "nri_status",
                "oci_status",
                "foreign_national_status",
            ):
                parsed_bool = _parse_bool(values.get(field), default=False)
                if parsed_bool is None:
                    _add_finding(
                        row,
                        f"{field.upper()}_INVALID",
                        FindingOutcome.FAIL,
                        "Field must be true or false.",
                        field,
                    )
                    parsed_bool = False
                flag_values[field] = parsed_bool
                setattr(row, field, parsed_bool)
            nationality_flags = sum(
                flag_values[field]
                for field in ("nri_status", "oci_status", "foreign_national_status")
            )
            if nationality_flags > 1:
                _add_finding(
                    row,
                    "NATIONALITY_FLAGS_CONFLICT",
                    FindingOutcome.FAIL,
                    "NRI, OCI, and foreign-national flags cannot be combined.",
                    "nri_status",
                )

            admission_status = (
                values.get("admission_status") or "ADMITTED"
            ).strip().upper() or "ADMITTED"
            if not values.get("admission_status"):
                _add_finding(
                    row,
                    "ADMISSION_STATUS_ASSUMED",
                    FindingOutcome.WARN,
                    "Admission status defaulted to ADMITTED for the legacy CSV format.",
                    "admission_status",
                )
            if admission_status not in ADMISSION_STATUSES:
                _add_finding(
                    row,
                    "ADMISSION_STATUS_INVALID",
                    FindingOutcome.FAIL,
                    "Admission status is not supported.",
                    "admission_status",
                )
                admission_status = "PENDING_REVIEW"
            row.admission_status = admission_status
            if admission_status == "PENDING_REVIEW":
                _add_finding(
                    row,
                    "ADMISSION_REQUIRES_REVIEW",
                    FindingOutcome.REVIEW,
                    "Admission is marked pending review.",
                    "admission_status",
                )

            key = (program_year.id, student_ref.casefold())
            if student_ref and (key in seen_keys or key in existing_keys):
                _add_finding(
                    row,
                    "DUPLICATE_ENROLMENT_KEY_IN_BATCH"
                    if key in seen_keys
                    else "DUPLICATE_ENROLMENT_KEY",
                    FindingOutcome.FAIL,
                    "Student ID already has an enrolment for this programme and academic year.",
                    "student_ref",
                )
                if key in seen_keys:
                    _add_finding(
                        seen_keys[key],
                        "DUPLICATE_ENROLMENT_KEY_IN_BATCH",
                        FindingOutcome.FAIL,
                        "Student ID repeats within this batch for this programme and "
                        "academic year.",
                        "student_ref",
                    )
            if student_ref:
                seen_keys.setdefault(key, row)
        else:
            row.program_academic_year_id = None

    # Preview capacity in row order. Only rows otherwise eligible for admission consume the
    # preview; final commit repeats this under program-year locks to close races.
    for row, (_, _values) in zip(rows, source_rows, strict=True):
        row.row_status = _row_status(row)
        if row.row_status not in {ImportRowStatus.READY, ImportRowStatus.WARNING}:
            continue
        if row.admission_status != "ADMITTED" or row.program_academic_year_id is None:
            continue
        pya = row.program_academic_year_id
        pool_code = category_code_by_row.get(row.id)
        pools = intakes.get(pya, {})
        if pool_code is None:
            continue
        category_id = row.seat_category_id
        if pool_code:
            approved = pools.get(pool_code)
            if approved is None:
                continue
            count_key = (pya, category_id)
            if category_counts[count_key] + counter_pool[(pya, pool_code)] + 1 > approved:
                _add_finding(
                    row,
                    "INTAKE_CAPACITY_REVIEW",
                    FindingOutcome.REVIEW,
                    "This admission exceeds configured category intake; review is required.",
                    "seat_category_code",
                )
                row.row_status = ImportRowStatus.REVIEW_REQUIRED
                continue
        total_approved = pools.get(None)
        if total_approved is not None:
            if total_counts[pya] + total_request_counts[pya] + 1 > total_approved:
                _add_finding(
                    row,
                    "INTAKE_TOTAL_CAPACITY_REVIEW",
                    FindingOutcome.REVIEW,
                    "This admission exceeds total approved intake; operator review is required.",
                    "seat_category_code",
                )
                row.row_status = ImportRowStatus.REVIEW_REQUIRED
                continue
        counter_pool[(pya, pool_code)] += 1
        total_request_counts[pya] += 1

    # Review cases are generated for duplicate APAAR matches without exposing the identifier.
    for row in rows:
        if any(
            item.rule_code in {"APAAR_DUPLICATE_REVIEW", "APAAR_DUPLICATE_IN_BATCH"}
            for item in row.findings
        ):
            if row.identity_reference_id:
                intra_batch = any(
                    finding.rule_code == "APAAR_DUPLICATE_IN_BATCH" for finding in row.findings
                )
                case = ReviewCase(
                    institution_id=institution_id,
                    import_row=row,
                    identity_reference_id=row.identity_reference_id,
                    case_type=(
                        ReviewCaseType.INTRA_BATCH_DUPLICATE
                        if intra_batch
                        else ReviewCaseType.CROSS_INSTITUTION_DUPLICATE
                    ),
                    status=ReviewCaseStatus.OPEN,
                )
                db.add(case)
                review_cases.append(case)
    return review_cases, category_code_by_row


def _audit_payload(event: AuditEvent | None, role: UserRole) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "id": str(event.id),
        "institution_id": str(event.institution_id) if event.institution_id else "",
        "actor_role": role.value,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else "",
        "action": event.action,
        "entity_type": "BATCH",
        "entity_id": str(event.entity_id) if event.entity_id else "",
        "outcome": "SUCCESS",
        "summary": event.summary,
        "previous_hash": event.previous_hash or "",
        "event_hash": event.event_hash,
        "created_at": event.created_at.isoformat(),
    }


def _serialize(db: Session, batch: DataImportBatch, principal: Principal) -> dict[str, Any]:
    institution = db.get(Institution, batch.institution_id)
    program_info = {
        item[0]: (item[1], item[2])
        for item in db.execute(
            select(ProgramAcademicYear.id, AcademicProgram.code, AcademicYear.starts_on)
            .join(AcademicProgram, ProgramAcademicYear.program_id == AcademicProgram.id)
            .join(AcademicYear, ProgramAcademicYear.academic_year_id == AcademicYear.id)
            .where(ProgramAcademicYear.institution_id == batch.institution_id)
        ).all()
    }
    rows = list(batch.rows)
    counts = Counter(row.row_status for row in rows)
    batch_status = batch.status.value
    if (
        counts[ImportRowStatus.REJECTED]
        or counts[ImportRowStatus.REVIEW_REQUIRED]
        or counts[ImportRowStatus.WARNING]
    ):
        batch_status = ImportBatchStatus.COMPLETED_WITH_FLAGS.value
    batch_payload = {
        "id": str(batch.id),
        "institution_id": str(batch.institution_id),
        "institution_name": institution.name if institution else "",
        "filename": batch.filename,
        "uploaded_by": "synthetic account",
        "total_rows": len(rows),
        "passed_rows": (
            counts[ImportRowStatus.READY]
            + counts[ImportRowStatus.WARNING]
            + counts[ImportRowStatus.COMMITTED]
        ),
        "flagged_rows": counts[ImportRowStatus.REVIEW_REQUIRED],
        "failed_rows": counts[ImportRowStatus.REJECTED],
        "committed_rows": counts[ImportRowStatus.COMMITTED],
        "ruleset_version": RULESET_VERSION,
        "commit_eligible": any(
            row.row_status in {ImportRowStatus.READY, ImportRowStatus.WARNING} for row in rows
        ),
        "committed": batch.committed_at is not None,
        "status": batch_status,
        "created_at": batch.created_at.isoformat(),
    }
    students: list[dict[str, Any]] = []
    for row in rows:
        program_code, start_date = program_info.get(row.program_academic_year_id, ("", None))
        findings = [
            {
                "rule_code": item.rule_code,
                "stu_code": item.rule_code,
                "rule_name": item.rule_code.replace("_", " ").title(),
                "outcome": item.outcome.value,
                "reason": item.reason,
                "affected_field": item.affected_field,
                "actual_masked": row.masked_apaar,
                "remediation": item.remediation,
                "ruleset_version": RULESET_VERSION,
            }
            for item in row.findings
        ]
        duplicate = any("DUPLICATE" in item.rule_code for item in row.findings)
        if row.row_status == ImportRowStatus.REJECTED:
            status = "VALIDATION_FAILED"
        elif duplicate:
            status = "FLAGGED_CONFLICT"
        else:
            # Format checks and local review do not constitute official identity verification.
            status = "PENDING_REVIEW"
        students.append(
            {
                "id": str(row.id),
                "institution_id": str(batch.institution_id),
                "institution_name": institution.name if institution else "",
                "student_ref": row.student_ref or "",
                "apaar_masked": row.masked_apaar or "NOT PROVIDED",
                "apaar_status": (
                    "NOT_PROVIDED"
                    if not row.masked_apaar
                    else "FORMAT_INVALID"
                    if row.masked_apaar == "INVALID FORMAT"
                    else "FORMAT_VALID"
                ),
                "full_name": row.full_name or "",
                "dob": row.date_of_birth or "",
                "program_code": program_code,
                "enrollment_year": start_date.year if start_date else 0,
                "consent_granted": bool(row.consent_granted),
                "status": status,
                "committed": row.row_status == ImportRowStatus.COMMITTED,
                "validation_results": findings,
                "batch_id": str(batch.id),
                "created_at": row.created_at.isoformat(),
                "row_status": row.row_status.value,
                "admission_date": row.admission_date.isoformat() if row.admission_date else None,
                "admission_status": row.admission_status,
                "seat_category_code": (
                    db.scalar(
                        select(SeatCategory.code).where(SeatCategory.id == row.seat_category_id)
                    )
                    if row.seat_category_id
                    else None
                ),
                "supernumerary_seat": row.supernumerary_seat,
                "nri_status": row.nri_status,
                "oci_status": row.oci_status,
                "foreign_national_status": row.foreign_national_status,
            }
        )
    return {
        "environment": get_settings().app_env.upper(),
        "ruleset_version": RULESET_VERSION,
        "batch": batch_payload,
        "records": students,
    }


def upload_batch(
    db: Session,
    *,
    principal: Principal,
    filename: str,
    csv_content: str,
    request_id: str,
) -> dict[str, Any]:
    if not principal.institution_id:
        raise HTTPException(status_code=403, detail="Institution membership is required.")
    authorize_record(
        principal,
        institution_id=principal.institution_id,
        action=Action.WRITE,
        resource="batch",
    )
    # All CSV content is held only in request memory; it is never logged or persisted.
    parsed = parse_csv_content(csv_content)
    settings = get_settings()
    key = settings.require_apaar_hmac_key()
    key_version = settings.apaar_hmac_key_version
    keyring = settings.require_apaar_hmac_keyring()
    fingerprint = _fingerprint(parsed, key)
    institution = db.scalar(
        select(Institution).where(Institution.id == principal.institution_id).with_for_update()
    )
    if institution is None:
        raise HTTPException(status_code=404, detail="Institution was not found.")
    if not institution.is_synthetic:
        raise HTTPException(
            status_code=403, detail="This local API accepts synthetic institutions only."
        )
    existing = db.scalar(
        select(DataImportBatch)
        .where(
            DataImportBatch.institution_id == institution.id,
            DataImportBatch.fingerprint_key_version == key_version,
            DataImportBatch.content_fingerprint == fingerprint,
        )
        .with_for_update()
    )
    if existing:
        result = _serialize(db, existing, principal)
        event = db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_id == existing.id, AuditEvent.action == "STUDENT_BATCH_UPLOADED"
            )
            .order_by(AuditEvent.created_at.asc())
        )
        result.update(
            {
                "records": result.pop("records"),
                "conflicts_created": [],
                "review_cases_created": [
                    str(case_id)
                    for case_id in db.scalars(
                        select(ReviewCase.id)
                        .join(ImportBatchRow, ReviewCase.import_row_id == ImportBatchRow.id)
                        .where(ImportBatchRow.batch_id == existing.id)
                    )
                ],
                "audit_event": _audit_payload(event, principal.role),
                "idempotent_replay": True,
            }
        )
        db.commit()
        return result

    safe_filename = filename.replace("\\", "/").split("/")[-1][:255] or "upload.csv"
    batch = DataImportBatch(
        institution_id=institution.id,
        uploaded_by_user_id=principal.user_id,
        filename=safe_filename,
        fingerprint_key_version=key_version,
        content_fingerprint=fingerprint,
        status=ImportBatchStatus.PROCESSING,
        total_rows=len(parsed.rows),
    )
    db.add(batch)
    db.flush()
    rows = [
        ImportBatchRow(
            batch_id=batch.id,
            institution_id=institution.id,
            row_number=line_number,
            student_ref=None,
            masked_apaar=None,
            full_name=None,
            date_of_birth=None,
            consent_granted=None,
            supernumerary_seat=False,
            nri_status=False,
            oci_status=False,
            foreign_national_status=False,
            admission_status="ADMITTED",
            row_status=ImportRowStatus.READY,
        )
        for line_number, _ in parsed.rows
    ]
    db.add_all(rows)
    db.flush()
    review_cases, _ = _validate_rows(
        db,
        rows=rows,
        source_rows=parsed.rows,
        institution_id=institution.id,
        apaar_key=key,
        apaar_key_version=key_version,
        apaar_keyring=keyring,
    )
    for row in rows:
        row.row_status = _row_status(row)
    batch.status = (
        ImportBatchStatus.COMPLETED_WITH_FLAGS
        if any(row.row_status != ImportRowStatus.READY for row in rows)
        else ImportBatchStatus.COMPLETED
    )
    event = _append_audit(
        db,
        principal=principal,
        institution_id=institution.id,
        action="STUDENT_BATCH_UPLOADED",
        entity_id=batch.id,
        request_id=request_id,
        summary=f"Synthetic student batch validated with {len(rows)} rows.",
        safe_payload={
            "total_rows": len(rows),
            "ready_rows": sum(row.row_status == ImportRowStatus.READY for row in rows),
            "warning_rows": sum(row.row_status == ImportRowStatus.WARNING for row in rows),
            "review_rows": sum(row.row_status == ImportRowStatus.REVIEW_REQUIRED for row in rows),
            "rejected_rows": sum(row.row_status == ImportRowStatus.REJECTED for row in rows),
        },
    )
    db.commit()
    db.refresh(batch)
    logger.info("synthetic_batch_validated batch_id=%s row_count=%s", batch.id, len(rows))
    result = _serialize(db, batch, principal)
    result.update(
        {
            # The legacy client expects ConflictCase objects. This first slice
            # has no conflict-case response DTO, so keep that field empty and
            # expose newly created review case identifiers separately.
            "conflicts_created": [],
            "review_cases_created": [str(case.id) for case in review_cases],
            "audit_event": _audit_payload(event, principal.role),
            "idempotent_replay": False,
        }
    )
    return result


def get_batch(db: Session, *, principal: Principal, batch_id: uuid.UUID) -> dict[str, Any]:
    batch = db.scalar(
        select(DataImportBatch).where(
            DataImportBatch.id == batch_id,
            DataImportBatch.institution_id == principal.institution_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch was not found.")
    result = _serialize(db, batch, principal)
    return {key: result[key] for key in ("environment", "ruleset_version", "batch", "records")}


def list_validation_results(db: Session, *, principal: Principal) -> dict[str, Any]:
    if not principal.institution_id:
        raise HTTPException(status_code=403, detail="Institution membership is required.")
    batches = db.scalars(
        select(DataImportBatch)
        .where(DataImportBatch.institution_id == principal.institution_id)
        .order_by(DataImportBatch.created_at.desc())
    ).all()
    payloads = [_serialize(db, batch, principal) for batch in batches]
    return {
        "environment": get_settings().app_env.upper(),
        "ruleset_version": RULESET_VERSION,
        "batches": [item["batch"] for item in payloads],
        "students": [record for item in payloads for record in item["records"]],
    }


def error_report(db: Session, *, principal: Principal, batch_id: uuid.UUID) -> str:
    batch = db.scalar(
        select(DataImportBatch).where(
            DataImportBatch.id == batch_id,
            DataImportBatch.institution_id == principal.institution_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch was not found.")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    headers = [
        "row_number",
        "student_ref",
        "apaar_masked",
        "row_status",
        "reason_code",
        "outcome",
        "field",
        "reason",
    ]
    writer.writerow([spreadsheet_safe(value) for value in headers])
    for row in batch.rows:
        for finding in row.findings:
            if finding.outcome == FindingOutcome.PASS:
                continue
            values = [
                row.row_number,
                row.student_ref or "",
                row.masked_apaar or "NOT PROVIDED",
                row.row_status.value,
                finding.rule_code,
                finding.outcome.value,
                finding.affected_field or "",
                finding.reason,
            ]
            writer.writerow([spreadsheet_safe(value) for value in values])
    return output.getvalue()


def commit_batch(
    db: Session,
    *,
    principal: Principal,
    batch_id: uuid.UUID,
    request_id: str,
) -> dict[str, Any]:
    if not principal.institution_id:
        raise HTTPException(status_code=403, detail="Institution membership is required.")
    authorize_record(
        principal,
        institution_id=principal.institution_id,
        action=Action.WRITE,
        resource="batch",
    )
    institution = db.scalar(
        select(Institution).where(Institution.id == principal.institution_id).with_for_update()
    )
    batch = db.scalar(
        select(DataImportBatch)
        .where(
            DataImportBatch.id == batch_id,
            DataImportBatch.institution_id == principal.institution_id,
        )
        .with_for_update()
    )
    if institution is None or batch is None:
        raise HTTPException(status_code=404, detail="Batch was not found.")
    if batch.committed_at is not None:
        return {
            "environment": get_settings().app_env.upper(),
            "batch": _serialize(db, batch, principal)["batch"],
            "newly_committed": 0,
            "audit_event": None,
        }

    eligible = [
        row
        for row in batch.rows
        if row.row_status in {ImportRowStatus.READY, ImportRowStatus.WARNING}
        and row.program_academic_year_id is not None
    ]
    year_ids = sorted({row.program_academic_year_id for row in eligible}, key=str)
    if year_ids:
        # PostgreSQL row locks serialize allocation for each configured program/year.
        db.scalars(
            select(ProgramAcademicYear)
            .where(ProgramAcademicYear.id.in_(year_ids))
            .order_by(ProgramAcademicYear.id)
            .with_for_update()
        ).all()
    intake_rows = db.execute(
        select(ApprovedIntake, SeatCategory)
        .outerjoin(SeatCategory, ApprovedIntake.seat_category_id == SeatCategory.id)
        .where(ApprovedIntake.program_academic_year_id.in_(year_ids or [uuid.UUID(int=0)]))
    ).all()
    intakes: dict[uuid.UUID, dict[uuid.UUID | None, int]] = defaultdict(dict)
    for intake, category in intake_rows:
        intakes[intake.program_academic_year_id][category.id if category else None] = (
            intake.approved_seats
        )
    enrolments = db.execute(
        select(Enrolment.program_academic_year_id, Enrolment.seat_category_id).where(
            Enrolment.institution_id == institution.id,
            Enrolment.status.in_(ACTIVE_ENROLMENT_STATUSES),
        )
    ).all()
    category_counts: Counter[tuple[uuid.UUID, uuid.UUID | None]] = Counter(enrolments)
    total_counts: Counter[uuid.UUID] = Counter(year_id for year_id, _ in enrolments)
    request_counts: Counter[tuple[uuid.UUID, uuid.UUID | None]] = Counter()
    request_totals: Counter[uuid.UUID] = Counter()

    capacity_conflicts: list[ImportBatchRow] = []
    for row in eligible:
        if row.admission_status != "ADMITTED":
            continue
        pya = row.program_academic_year_id
        pools = intakes.get(pya, {})
        category_id = row.seat_category_id
        if category_id not in pools:
            capacity_conflicts.append(row)
            continue
        category_cap = pools[category_id]
        if (
            category_counts[(pya, category_id)] + request_counts[(pya, category_id)] + 1
            > category_cap
        ):
            capacity_conflicts.append(row)
            continue
        total_cap = pools.get(None)
        if total_cap is not None and total_counts[pya] + request_totals[pya] + 1 > total_cap:
            capacity_conflicts.append(row)
            continue
        request_counts[(pya, category_id)] += 1
        request_totals[pya] += 1

    if capacity_conflicts:
        # A changed pool means the preview for the entire batch is stale.
        # Require review for every would-be commit row so a retry cannot commit
        # only the subset that happened to fit.
        for row in eligible:
            _add_finding(
                row,
                "COMMIT_CAPACITY_CHANGED",
                FindingOutcome.REVIEW,
                "Available approved capacity changed before commit; manual review is required.",
                "seat_category_code",
            )
            row.row_status = ImportRowStatus.REVIEW_REQUIRED
        event = _append_audit(
            db,
            principal=principal,
            institution_id=institution.id,
            action="STUDENT_BATCH_COMMIT_BLOCKED",
            entity_id=batch.id,
            request_id=request_id,
            summary="Student batch commit was blocked by current approved intake capacity.",
            outcome="DENIED",
            safe_payload={"capacity_conflict_rows": len(capacity_conflicts)},
        )
        db.commit()
        raise HTTPException(
            status_code=409, detail="Approved intake capacity changed; no rows were committed."
        )

    now = datetime.now(UTC)
    for row in eligible:
        if row.admission_status == "PENDING_REVIEW":
            continue
        enrolment_status = (
            EnrolmentStatus.WITHDRAWN
            if row.admission_status == "WITHDRAWN"
            else EnrolmentStatus.ACCEPTED
        )
        enrolment = Enrolment(
            institution_id=institution.id,
            identity_reference_id=row.identity_reference_id,
            program_academic_year_id=row.program_academic_year_id,
            seat_category_id=row.seat_category_id,
            student_ref=row.student_ref or "",
            status=enrolment_status,
        )
        db.add(enrolment)
        db.flush()
        row.enrolment_id = enrolment.id
        row.row_status = ImportRowStatus.COMMITTED
    batch.committed_at = now
    event = _append_audit(
        db,
        principal=principal,
        institution_id=institution.id,
        action="STUDENT_BATCH_COMMITTED",
        entity_id=batch.id,
        request_id=request_id,
        summary=f"Student batch committed {len(eligible)} eligible admission rows.",
        safe_payload={"newly_committed": len(eligible)},
    )
    db.commit()
    db.refresh(batch)
    return {
        "environment": get_settings().app_env.upper(),
        "batch": _serialize(db, batch, principal)["batch"],
        "newly_committed": len(eligible),
        "audit_event": _audit_payload(event, principal.role),
    }
