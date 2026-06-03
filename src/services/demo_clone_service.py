from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.exceptions import BadRequest, NotFound

from src.models.care_episode import (
    CareEpisodeAppointment,
    CareEpisodeInboxMessage,
    CareEpisodeRecord,
    CareEpisodeSession,
)
from src.services.care_episode_service import upsert_session

UTC = timezone.utc
_TEMPLATE_FILE = Path(__file__).resolve().parents[1] / "data" / "demo_patient_template.json"


def _load_template_meta() -> dict:
    return json.loads(_TEMPLATE_FILE.read_text(encoding="utf-8"))


def template_patient_uuid() -> uuid.UUID:
    meta = _load_template_meta()
    return uuid.UUID(str(meta["template_patient_uuid"]))


def demo_marker_record_title() -> str:
    meta = _load_template_meta()
    return str(meta["marker_record_title"])


def patient_has_demo_dashboard(db, patient_id: uuid.UUID) -> bool:
    marker = demo_marker_record_title()
    return (
        db.query(CareEpisodeRecord.record_uuid)
        .filter(
            CareEpisodeRecord.patient_uuid == patient_id,
            CareEpisodeRecord.title == marker,
        )
        .limit(1)
        .first()
        is not None
    )


def _latest_template_timestamp(
    appointments: list[CareEpisodeAppointment],
    messages: list[CareEpisodeInboxMessage],
) -> datetime:
    candidates: list[datetime] = []
    for row in appointments:
        candidates.append(row.scheduled_at.astimezone(UTC))
    for row in messages:
        candidates.append(row.sent_at.astimezone(UTC))
    if not candidates:
        return datetime.now(UTC)
    return max(candidates)


def clone_patient_demo_from_template(
    db,
    target_patient_uuid: str,
    *,
    tenant_uuid: str,
    display_name: str,
    display_code: str,
    changed_by_uuid: str,
    changed_by_type: int = 2,
) -> dict:
    """Copy session, records, appointments, and inbox from the hidden template patient (no transcript)."""
    target_id = uuid.UUID(str(target_patient_uuid))
    source_id = template_patient_uuid()
    if target_id == source_id:
        raise BadRequest("cannot clone demo data onto the template patient")

    if patient_has_demo_dashboard(db, target_id):
        return {
            "patient_uuid": str(target_id),
            "cloned": False,
            "reason": "already_present",
        }

    template_session = db.get(CareEpisodeSession, source_id)
    if template_session is None:
        raise NotFound("demo template patient is not seeded")

    template_records = (
        db.query(CareEpisodeRecord).filter(CareEpisodeRecord.patient_uuid == source_id).all()
    )
    template_appointments = (
        db.query(CareEpisodeAppointment).filter(CareEpisodeAppointment.patient_uuid == source_id).all()
    )
    template_messages = (
        db.query(CareEpisodeInboxMessage).filter(CareEpisodeInboxMessage.patient_uuid == source_id).all()
    )

    actor_id = uuid.UUID(str(changed_by_uuid))
    now = datetime.now(UTC)
    time_anchor = _latest_template_timestamp(template_appointments, template_messages)

    upsert_session(
        db,
        {
            "patient_uuid": str(target_id),
            "tenant_uuid": tenant_uuid,
            "display_code": display_code,
            "display_name": display_name,
            "surgery": template_session.surgery,
            "procedure_date": template_session.procedure_date.isoformat(),
            "session_id": template_session.session_id,
            "featured": False,
        },
        changed_by_uuid=changed_by_uuid,
        changed_by_type=changed_by_type,
    )

    for row in template_records:
        db.add(
            CareEpisodeRecord(
                patient_uuid=target_id,
                title=row.title,
                date=row.date,
                type=row.type,
                provider=row.provider,
                summary=row.summary,
                image_key=row.image_key,
                changed_by_uuid=actor_id,
                changed_by_type=changed_by_type,
            )
        )

    for row in template_appointments:
        scheduled = row.scheduled_at.astimezone(UTC)
        shifted = now + (scheduled - time_anchor)
        db.add(
            CareEpisodeAppointment(
                patient_uuid=target_id,
                clinician_user_uuid=row.clinician_user_uuid,
                clinician_display_name=row.clinician_display_name,
                specialty=row.specialty,
                scheduled_at=shifted,
                status=row.status,
                changed_by_uuid=actor_id,
                changed_by_type=changed_by_type,
            )
        )

    for row in template_messages:
        sent = row.sent_at.astimezone(UTC)
        shifted_sent = now + (sent - time_anchor)
        read_at = None
        if row.read_at is not None:
            read_src = row.read_at.astimezone(UTC)
            read_at = now + (read_src - time_anchor)
        db.add(
            CareEpisodeInboxMessage(
                patient_uuid=target_id,
                sender_user_uuid=row.sender_user_uuid,
                sender_display_name=row.sender_display_name,
                body=row.body,
                sent_at=shifted_sent,
                read_at=read_at,
                changed_by_uuid=actor_id,
                changed_by_type=changed_by_type,
            )
        )

    db.commit()
    return {
        "patient_uuid": str(target_id),
        "cloned": True,
        "records": len(template_records),
        "appointments": len(template_appointments),
        "messages": len(template_messages),
    }
