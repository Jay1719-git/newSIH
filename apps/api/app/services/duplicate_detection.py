from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth.policies import Action, Principal, authorize_record
from app.core.config import get_settings
from app.models.duplicate import DuplicateCase
from app.models.enums import ImportBatchStatus, ImportRowStatus, UserRole
from app.models.identity import StudentIdentityReference
from app.models.ingestion import DataImportBatch, ImportBatchRow
from app.models.institution import Institution

NORMALIZATION_VERSION = "identity-norm-v1"
_NAME_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")
_OUTCOMES = frozenset(
    {"CONFIRMED_DUPLICATE", "DISTINCT_STUDENTS", "INSUFFICIENT_EVIDENCE", "ESCALATED"}
)


@dataclass(frozen=True)
class MatchRecord:
    record_id: uuid.UUID
    institution_id: uuid.UUID
    student_ref: str | None
    full_name: str | None
    date_of_birth: str | None
    identity_reference_id: uuid.UUID | None
    program_academic_year_id: uuid.UUID | None = None
    committed: bool = False


@dataclass(frozen=True)
class MatchCandidate:
    record_a_id: uuid.UUID
    record_b_id: uuid.UUID
    institution_a_id: uuid.UUID
    institution_b_id: uuid.UUID
    match_type: Literal[
        "EXACT_WITHIN_INSTITUTION", "POTENTIAL_WITHIN_INSTITUTION", "POTENTIAL_CROSS_INSTITUTION"
    ]
    confidence_band: Literal["HIGH", "MEDIUM"]
    reason_codes: tuple[str, ...]
    explanation: str


def normalize_name(value: str | None) -> str:
    """Versioned, deterministic name normalization; source strings stay server-side."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    return _SPACE.sub(" ", _NAME_PUNCTUATION.sub(" ", value)).strip()


def normalize_reference(value: str | None) -> str:
    return "" if not value else re.sub(r"[\s-]", "", unicodedata.normalize("NFKC", value)).upper()


def hmac_fingerprint(value: str, key: bytes, *, namespace: str) -> str:
    """Use a keyed, domain-separated digest; never fall back to an ordinary hash."""
    material = f"{NORMALIZATION_VERSION}\0{namespace}\0{value}".encode()
    return hmac.new(key, material, hashlib.sha256).hexdigest()


def apaar_fingerprints(value: str, keys: dict[str, bytes]) -> set[tuple[str, str]]:
    """Build version-tagged HMACs for current plus retained keys during rotation overlap."""
    normalized = re.sub(r"[\s-]", "", unicodedata.normalize("NFKC", value))
    return {
        (version, hmac.new(key, normalized.encode("ascii"), hashlib.sha256).hexdigest())
        for version, key in keys.items()
    }


def _confidence(score: float) -> str:
    return "HIGH" if score >= 0.95 else "MEDIUM"


def generate_candidates(
    records: list[MatchRecord],
    identity_by_id: dict[uuid.UUID, StudentIdentityReference],
    *,
    key: bytes,
    name_threshold: float = 0.88,
) -> list[MatchCandidate]:
    """Generate explainable candidate pairs using exact keys and DOB HMAC blocking."""
    if not 0.5 <= name_threshold <= 1.0:
        raise ValueError("name_threshold must be between 0.5 and 1.0")
    result: dict[tuple[uuid.UUID, uuid.UUID], MatchCandidate] = {}
    active = [r for r in records if r.full_name and r.full_name.strip()]
    names = {r.record_id: normalize_name(r.full_name) for r in active}
    dob_blocks = {
        r.record_id: hmac_fingerprint(r.date_of_birth or "", key, namespace="dob-block")
        for r in active
        if r.date_of_birth
    }

    def add(
        a: MatchRecord,
        b: MatchRecord,
        match_type: str,
        band: str,
        reasons: tuple[str, ...],
        explanation: str,
    ) -> None:
        left, right = sorted((a, b), key=lambda item: item.record_id.hex)
        candidate = MatchCandidate(
            left.record_id,
            right.record_id,
            left.institution_id,
            right.institution_id,
            match_type,  # type: ignore[arg-type]
            band,  # type: ignore[arg-type]
            reasons,
            explanation,
        )
        pair = (left.record_id, right.record_id)
        current = result.get(pair)
        if current is None or (
            "APAAR_FINGERPRINT_MATCH" in candidate.reason_codes
            and "APAAR_FINGERPRINT_MATCH" not in current.reason_codes
        ):
            result[pair] = candidate

    # Exact APAAR references are compared by opaque identity-reference IDs. The digest itself
    # is never serialized. Ingestion maps rotation-key fingerprints to the same reference.
    by_identity: dict[uuid.UUID, list[MatchRecord]] = {}
    for record in active:
        if record.identity_reference_id and record.identity_reference_id in identity_by_id:
            by_identity.setdefault(record.identity_reference_id, []).append(record)
    for group in by_identity.values():
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                same_tenant = a.institution_id == b.institution_id
                add(
                    a,
                    b,
                    "EXACT_WITHIN_INSTITUTION" if same_tenant else "POTENTIAL_CROSS_INSTITUTION",
                    "HIGH",
                    ("APAAR_FINGERPRINT_MATCH",),
                    "The same keyed identity-reference fingerprint is present; "
                    "this is a review lead, not a fraud finding.",
                )

    # Student references are an exact within-institution signal only, and only within the same
    # configured academic programme/year. The service does not compare them across institutions.
    ref_groups: dict[tuple[uuid.UUID, str], list[MatchRecord]] = {}
    for record in active:
        ref = normalize_reference(record.student_ref)
        if ref and record.program_academic_year_id:
            ref_groups.setdefault((record.institution_id, ref), []).append(record)
    for group in ref_groups.values():
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if (
                    a.record_id == b.record_id
                    or a.program_academic_year_id != b.program_academic_year_id
                ):
                    continue
                add(
                    a,
                    b,
                    "EXACT_WITHIN_INSTITUTION",
                    "HIGH",
                    ("INSTITUTION_REFERENCE_MATCH",),
                    "The institution-local student reference matches; confirm whether "
                    "the records refer to one student.",
                )

    # DOB is used only as a keyed blocking value. Names are compared in memory and never
    # persisted in case details. No gender, nationality, or other protected traits are used.
    by_block: dict[str, list[MatchRecord]] = {}
    for record in active:
        block = dob_blocks.get(record.record_id)
        if block:
            by_block.setdefault(block, []).append(record)
    for group in by_block.values():
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                a_ref = normalize_reference(a.student_ref)
                b_ref = normalize_reference(b.student_ref)
                if a.institution_id == b.institution_id and a_ref and a_ref == b_ref:
                    continue
                ratio = SequenceMatcher(
                    None, names[a.record_id], names[b.record_id], autojunk=False
                ).ratio()
                if ratio < name_threshold:
                    continue
                same_tenant = a.institution_id == b.institution_id
                exact_name = names[a.record_id] == names[b.record_id]
                reasons = (
                    "DOB_BLOCK_MATCH",
                    "NORMALIZED_NAME_MATCH" if exact_name else "NAME_VARIANT_SIMILARITY",
                )
                add(
                    a,
                    b,
                    "POTENTIAL_WITHIN_INSTITUTION"
                    if same_tenant
                    else "POTENTIAL_CROSS_INSTITUTION",
                    _confidence(ratio),
                    reasons,
                    "The keyed date-of-birth block matches and normalized names are similar; "
                    "manual review is required.",
                )
    return sorted(result.values(), key=lambda item: (item.record_a_id.hex, item.record_b_id.hex))


def _safe_mask(value: str | None) -> str | None:
    if not value:
        return None
    return f"{value[0].upper()}•••"


def _row_to_record(row: ImportBatchRow, committed_ids: set[uuid.UUID]) -> MatchRecord:
    return MatchRecord(
        row.id,
        row.institution_id,
        row.student_ref,
        row.full_name,
        row.date_of_birth,
        row.identity_reference_id,
        row.program_academic_year_id,
        row.id in committed_ids,
    )


def scan_duplicates(db: Session, *, principal: Principal) -> dict:
    if principal.role not in {
        UserRole.INSTITUTION_ADMIN,
        UserRole.INSTITUTION_OPERATOR,
        UserRole.REGULATOR_ADMIN,
    }:
        raise HTTPException(status_code=403, detail="This role cannot run duplicate detection.")
    if (
        principal.role in {UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR}
        and not principal.institution_id
    ):
        raise HTTPException(status_code=403, detail="Institution membership is required.")
    settings = get_settings()
    key = settings.require_apaar_hmac_key()
    threshold = settings.duplicate_name_similarity_threshold

    query = (
        select(ImportBatchRow)
        .join(DataImportBatch, ImportBatchRow.batch_id == DataImportBatch.id)
        .where(
            DataImportBatch.status.in_(
                (ImportBatchStatus.COMPLETED, ImportBatchStatus.COMPLETED_WITH_FLAGS)
            ),
            ImportBatchRow.row_status != ImportRowStatus.REJECTED,
            ImportBatchRow.admission_status != "WITHDRAWN",
        )
    )
    if principal.role in {UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR}:
        # Include the caller's rows plus committed counterparts. Counterpart raw fields are
        # loaded only inside the matching service and never leave the server unmasked.
        query = query.where(
            or_(
                ImportBatchRow.institution_id == principal.institution_id,
                ImportBatchRow.row_status == ImportRowStatus.COMMITTED,
            )
        )
    rows = list(db.scalars(query))
    committed_ids = set(
        db.scalars(
            select(ImportBatchRow.id).where(ImportBatchRow.row_status == ImportRowStatus.COMMITTED)
        )
    )
    records = [_row_to_record(row, committed_ids) for row in rows]
    reference_ids = {
        record.identity_reference_id for record in records if record.identity_reference_id
    }
    identities = {
        item.id: item
        for item in db.scalars(
            select(StudentIdentityReference).where(
                StudentIdentityReference.id.in_(reference_ids or [uuid.UUID(int=0)])
            )
        )
    }
    candidates = generate_candidates(records, identities, key=key, name_threshold=threshold)
    if principal.role in {UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR}:
        candidates = [
            candidate
            for candidate in candidates
            if principal.institution_id in {candidate.institution_a_id, candidate.institution_b_id}
        ]
    created = 0
    rescanned = 0
    for candidate in candidates:
        inserted = db.execute(
            pg_insert(DuplicateCase)
            .values(
                record_a_id=candidate.record_a_id,
                record_b_id=candidate.record_b_id,
                institution_a_id=candidate.institution_a_id,
                institution_b_id=candidate.institution_b_id,
                match_type=candidate.match_type,
                confidence_band=candidate.confidence_band,
                reason_codes=list(candidate.reason_codes),
                explanation=candidate.explanation,
                status="OPEN",
                decision_history=[],
                scan_count=1,
            )
            .on_conflict_do_nothing(index_elements=["record_a_id", "record_b_id"])
            .returning(DuplicateCase.id)
        ).scalar_one_or_none()
        if inserted:
            created += 1
        else:
            case = db.scalar(
                select(DuplicateCase).where(
                    DuplicateCase.record_a_id == candidate.record_a_id,
                    DuplicateCase.record_b_id == candidate.record_b_id,
                )
            )
            if case:
                case.scan_count += 1
                # Keep existing human decisions intact. Refresh only machine evidence while open.
                if case.status == "OPEN":
                    case.match_type = candidate.match_type
                    case.confidence_band = candidate.confidence_band
                    case.reason_codes = list(candidate.reason_codes)
                    case.explanation = candidate.explanation
                rescanned += 1
    db.commit()
    return {
        "environment": settings.app_env.upper(),
        "candidates_examined": len(candidates),
        "cases_created": created,
        "cases_rescanned": rescanned,
    }


def _serialize_case(db: Session, case: DuplicateCase) -> dict:
    row_a = db.get(ImportBatchRow, case.record_a_id)
    row_b = db.get(ImportBatchRow, case.record_b_id)
    inst_a = db.get(Institution, case.institution_a_id)
    inst_b = db.get(Institution, case.institution_b_id)
    return {
        "case_id": str(case.id),
        "match_type": case.match_type,
        "confidence_band": case.confidence_band,
        "masked_fields": [
            {
                "institution_id": str(case.institution_a_id),
                "institution_name": inst_a.name if inst_a else None,
                "student_reference": _safe_mask(row_a.student_ref) if row_a else None,
                "name": _safe_mask(row_a.full_name) if row_a else None,
                "apaar": row_a.masked_apaar if row_a else None,
            },
            {
                "institution_id": str(case.institution_b_id),
                "institution_name": inst_b.name if inst_b else None,
                "student_reference": _safe_mask(row_b.student_ref) if row_b else None,
                "name": _safe_mask(row_b.full_name) if row_b else None,
                "apaar": row_b.masked_apaar if row_b else None,
            },
        ],
        "explanation": case.explanation,
        "reason_codes": case.reason_codes,
        "authorized_source_institution_ids": sorted(
            {str(case.institution_a_id), str(case.institution_b_id)}
        ),
        "review_status": case.status,
        "outcome": case.outcome,
        "decision_history": case.decision_history,
        "created_at": case.created_at.isoformat(),
    }


def list_duplicate_cases(db: Session, *, principal: Principal) -> dict:
    if principal.role in {UserRole.INSTITUTION_ADMIN, UserRole.INSTITUTION_OPERATOR}:
        if not principal.institution_id:
            raise HTTPException(status_code=403, detail="Institution membership is required.")
        statement = select(DuplicateCase).where(
            or_(
                DuplicateCase.institution_a_id == principal.institution_id,
                DuplicateCase.institution_b_id == principal.institution_id,
            )
        )
    elif principal.role in {UserRole.REGULATOR_ADMIN, UserRole.REGULATOR_OFFICER}:
        statement = select(DuplicateCase)
    else:
        raise HTTPException(status_code=403, detail="This role cannot access duplicate cases.")
    cases = list(db.scalars(statement.order_by(DuplicateCase.created_at.desc())))
    return {"cases": [_serialize_case(db, case) for case in cases]}


def decide_duplicate_case(
    db: Session, *, principal: Principal, case_id: uuid.UUID, outcome: str
) -> dict:
    authorize_record(principal, institution_id=None, action=Action.INVESTIGATE, resource="case")
    if outcome not in _OUTCOMES:
        raise HTTPException(status_code=422, detail="Unsupported review outcome.")
    case = db.get(DuplicateCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Duplicate case not found.")
    case.outcome = outcome
    case.status = "ESCALATED" if outcome == "ESCALATED" else "RESOLVED"
    history = list(case.decision_history or [])
    history.append(
        {
            "outcome": outcome,
            "reviewer_user_id": str(principal.user_id),
            "reviewed_at": __import__("datetime")
            .datetime.now(__import__("datetime").UTC)
            .isoformat(),
        }
    )
    case.decision_history = history
    db.commit()
    db.refresh(case)
    return _serialize_case(db, case)
