from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.policies import Principal
from app.models.audit import AuditEvent
from app.models.enums import AuditEntityType

_SAFE_KEYS = frozenset(
    {
        "outcome",
        "reason_code",
        "row_count",
        "claim_names",
        "purpose_code",
        "source",
        "format",
        "_serialization_version",
    }
)
_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,80}$")
_ALLOWED_CLAIMS = {"enrolment_status", "program_code", "academic_year", "award_status"}


def safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Allow only named non-identifying fields; discard caller-provided free text."""
    result: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if key not in _SAFE_KEYS - {"outcome", "_serialization_version"}:
            continue
        if (
            key in {"reason_code", "purpose_code"}
            and isinstance(value, str)
            and _SAFE_CODE.fullmatch(value)
        ):
            result[key] = value
        elif key == "claim_names" and isinstance(value, str):
            claims = value.split(",")
            if claims and set(claims) <= _ALLOWED_CLAIMS:
                result[key] = ",".join(sorted(set(claims)))
        elif key == "format" and value in {"csv", "validation_csv"}:
            result[key] = value
        elif key == "source" and value == "WEAVE_RECORD_CHECK":
            result[key] = value
        elif key == "row_count" and isinstance(value, int) and value >= 0:
            result[key] = value
    return result


def append_audit(
    db: Session,
    *,
    principal: Principal | None,
    action: str,
    resource_type: AuditEntityType,
    resource_id: uuid.UUID | None,
    request_id: str,
    outcome: str,
    institution_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    previous = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.institution_id == institution_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
        .with_for_update()
    )
    event_id, now = uuid.uuid4(), datetime.now(UTC)
    payload = {
        **safe_metadata(metadata),
        "outcome": outcome,
        "_serialization_version": 2,
    }
    material = {
        "id": str(event_id),
        "institution_id": str(institution_id) if institution_id else None,
        "actor_user_id": str(principal.user_id) if principal else None,
        "action": action,
        "resource_type": resource_type.value,
        "resource_id": str(resource_id) if resource_id else None,
        "timestamp": now.isoformat(),
        "request_id": request_id,
        "payload": payload,
        "previous_hash": previous.event_hash if previous else None,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    event = AuditEvent(
        id=event_id,
        institution_id=institution_id,
        actor_user_id=principal.user_id if principal else None,
        action=action,
        entity_type=resource_type,
        entity_id=resource_id,
        request_id=request_id,
        summary=f"{action} {outcome.lower()}",
        payload=payload,
        previous_hash=previous.event_hash if previous else None,
        event_hash=digest,
        created_at=now,
        updated_at=now,
    )
    db.add(event)
    return event


def verify_audit_chain(events: list[AuditEvent]) -> bool:
    previous_hash = None
    for event in events:
        if event.payload.get("_serialization_version") != 2:
            legacy = {
                "action": event.action,
                "actor_user_id": str(event.actor_user_id),
                "created_at": event.created_at.isoformat(),
                "entity_id": str(event.entity_id),
                "institution_id": str(event.institution_id),
                "payload": event.payload,
                "previous_hash": previous_hash,
                "request_id": event.request_id,
            }
            digest = hashlib.sha256(
                json.dumps(legacy, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if event.previous_hash != previous_hash or event.event_hash != digest:
                return False
            previous_hash = event.event_hash
            continue
        material = {
            "id": str(event.id),
            "institution_id": str(event.institution_id) if event.institution_id else None,
            "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
            "action": event.action,
            "resource_type": event.entity_type.value,
            "resource_id": str(event.entity_id) if event.entity_id else None,
            "timestamp": event.created_at.isoformat(),
            "request_id": event.request_id,
            "payload": event.payload,
            "previous_hash": previous_hash,
        }
        digest = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if event.previous_hash != previous_hash or event.event_hash != digest:
            return False
        previous_hash = event.event_hash
    return True
