from __future__ import annotations

import base64
import json
from itertools import combinations
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.auth.policies import Action, Principal, authorize_record
from app.core.config import Settings
from app.models.duplicate import DuplicateCase
from app.models.enums import UserRole
from app.models.identity import StudentIdentityReference
from app.services.duplicate_detection import (
    MatchRecord,
    apaar_fingerprints,
    generate_candidates,
)


def _record(
    name: str,
    dob: str | None,
    *,
    institution: UUID | None = None,
    reference: UUID | None = None,
    student_ref: str | None = None,
) -> MatchRecord:
    return MatchRecord(uuid4(), institution or uuid4(), student_ref, name, dob, reference)


def _findings(records: list[MatchRecord], *, threshold: float = 0.88):
    reference_ids = {r.identity_reference_id for r in records if r.identity_reference_id}
    identities = {
        ref: StudentIdentityReference(
            id=ref,
            key_version="test-v1",
            normalization_version="identity-norm-v1",
            hmac_digest="a" * 64,
            masked_apaar="****-****-1234",
        )
        for ref in reference_ids
    }
    return generate_candidates(
        records, identities, key=b"synthetic-test-key-32-bytes-long!!", name_threshold=threshold
    )


def test_exact_duplicate_within_and_across_institutions() -> None:
    identity = uuid4()
    own_institution, other_institution = uuid4(), uuid4()
    own_a = _record("Aarav Sharma", "2005-04-02", institution=own_institution, reference=identity)
    own_b = _record("Aarav Sharma", "2005-04-02", institution=own_institution, reference=identity)
    cross = _record("Aarav Sharma", "2005-04-02", institution=other_institution, reference=identity)

    results = _findings([own_a, own_b, cross])
    assert len(results) == 3
    assert sum(item.match_type == "EXACT_WITHIN_INSTITUTION" for item in results) == 1
    assert sum(item.match_type == "POTENTIAL_CROSS_INSTITUTION" for item in results) == 2
    assert all("APAAR_FINGERPRINT_MATCH" in item.reason_codes for item in results)


def test_name_typo_is_candidate_with_explainable_reasons() -> None:
    left = _record("Aarav Sharma", "2005-04-02")
    right = _record("Arav Sharma", "2005-04-02", institution=left.institution_id)

    [candidate] = _findings([left, right])
    assert candidate.match_type == "POTENTIAL_WITHIN_INSTITUTION"
    assert candidate.confidence_band == "HIGH"
    assert candidate.reason_codes == ("DOB_BLOCK_MATCH", "NAME_VARIANT_SIMILARITY")
    assert "manual review" in candidate.explanation


def test_missing_apaar_is_not_a_fraud_signal_and_can_still_match_permitted_fields() -> None:
    left = _record("Meera Iyer", "2004-11-19")
    right = _record("Meera Iyer", "2004-11-19", institution=left.institution_id)

    [candidate] = _findings([left, right])
    assert "APAAR_FINGERPRINT_MATCH" not in candidate.reason_codes
    assert candidate.reason_codes == ("DOB_BLOCK_MATCH", "NORMALIZED_NAME_MATCH")
    assert "fraud" not in candidate.explanation.casefold()


def test_same_dob_with_dissimilar_names_is_not_a_candidate() -> None:
    left = _record("Ananya Mukherjee", "2005-04-02")
    right = _record("Dev Patel", "2005-04-02", institution=left.institution_id)
    assert _findings([left, right]) == []


def test_repeated_scans_produce_stable_pair_for_database_deduplication() -> None:
    identity = uuid4()
    left = _record("Aarav Sharma", "2005-04-02", reference=identity)
    right = _record(
        "Aarav Sharma", "2005-04-02", institution=left.institution_id, reference=identity
    )
    first = _findings([left, right])
    second = _findings([left, right])
    assert [(c.record_a_id, c.record_b_id) for c in first] == [
        (c.record_a_id, c.record_b_id) for c in second
    ]
    unique_pair_index = next(
        index
        for index in DuplicateCase.__table__.indexes
        if index.name == "uq_duplicate_case_record_pair"
    )
    assert unique_pair_index.unique is True
    assert [column.name for column in unique_pair_index.columns] == ["record_a_id", "record_b_id"]


def test_key_rotation_uses_retained_key_to_link_to_existing_identity_reference() -> None:
    old_key, new_key = b"old-synthetic-test-key-32-bytes!!", b"new-synthetic-test-key-32-bytes!!"

    def encoded(key: bytes) -> str:
        return base64.urlsafe_b64encode(key).decode().rstrip("=")

    settings = Settings(
        apaar_hmac_key=SecretStr(encoded(new_key)),
        apaar_hmac_key_version="v2",
        apaar_hmac_previous_keys=SecretStr(json.dumps({"v1": encoded(old_key)})),
    )
    ring = settings.require_apaar_hmac_keyring()
    assert set(ring) == {"v1", "v2"}
    known_old_fingerprint = next(iter(apaar_fingerprints("234567890123", {"v1": old_key})))
    incoming_fingerprints = apaar_fingerprints("2345-6789-0123", ring)
    assert known_old_fingerprint in incoming_fingerprints
    assert apaar_fingerprints("234567890123", {"v1": old_key}) != apaar_fingerprints(
        "234567890123", {"v2": new_key}
    )


def test_case_access_and_outcome_authorization() -> None:
    institution = uuid4()
    operator = Principal(uuid4(), UserRole.INSTITUTION_OPERATOR, institution_id=institution)
    authorize_record(operator, institution_id=institution, action=Action.READ, resource="case")
    with pytest.raises(HTTPException) as denied:
        authorize_record(
            operator, institution_id=institution, action=Action.INVESTIGATE, resource="case"
        )
    assert denied.value.status_code == 403
    regulator = Principal(uuid4(), UserRole.REGULATOR_ADMIN)
    authorize_record(regulator, institution_id=None, action=Action.INVESTIGATE, resource="case")


def test_labelled_synthetic_metrics_are_measured_and_expected() -> None:
    identity = uuid4()
    records = [
        _record("Aarav Sharma", "2005-04-02", reference=identity),
        _record("Aarav Sharma", "2005-04-02", reference=identity),
        _record("Meera Iyer", "2004-11-19"),
        _record("Mera Iyer", "2004-11-19"),
        _record("Ananya Mukherjee", "2005-04-02"),
        _record("Dev Patel", "2005-04-02"),
    ]
    positive_labels = {
        frozenset((records[0].record_id, records[1].record_id)),
        frozenset((records[2].record_id, records[3].record_id)),
    }
    labels = {
        frozenset((left.record_id, right.record_id)): frozenset((left.record_id, right.record_id))
        in positive_labels
        for left, right in combinations(records, 2)
    }
    predicted = {
        frozenset((candidate.record_a_id, candidate.record_b_id))
        for candidate in _findings(records)
    }
    tp = sum(label and pair in predicted for pair, label in labels.items())
    fp = sum(not label and pair in predicted for pair, label in labels.items())
    fn = sum(label and pair not in predicted for pair, label in labels.items())
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    print(f"synthetic labelled precision={precision:.3f} recall={recall:.3f} (n={len(labels)})")
    assert (tp, fp, fn) == (2, 0, 0)
    assert precision == recall == 1.0
