from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text
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

# Align with cdp/scripts/demo_seed_payload.py dashboard_appointments (Alice / PAT-2847).
_UPCOMING_APPOINTMENT_OFFSETS: tuple[tuple[int, int, int], ...] = (
    (2, 10, 30),
    (8, 14, 0),
    (23, 9, 0),
)
_INBOX_SENT_AGO: tuple[timedelta, ...] = (
    timedelta(hours=1),
    timedelta(hours=3),
    timedelta(days=1, hours=2),
)


def scheduled_at_for_demo_appointment(now: datetime, index: int) -> datetime:
    """Return a future appointment time for demo dashboards (now + a few days)."""
    if index < len(_UPCOMING_APPOINTMENT_OFFSETS):
        days, hours, minutes = _UPCOMING_APPOINTMENT_OFFSETS[index]
        return now + timedelta(days=days, hours=hours, minutes=minutes)
    last_days, last_hours, last_minutes = _UPCOMING_APPOINTMENT_OFFSETS[-1]
    extra_weeks = index - len(_UPCOMING_APPOINTMENT_OFFSETS) + 1
    return now + timedelta(
        days=last_days + extra_weeks * 7,
        hours=last_hours,
        minutes=last_minutes,
    )


def sent_at_for_demo_inbox_message(now: datetime, index: int) -> datetime:
    if index < len(_INBOX_SENT_AGO):
        return now - _INBOX_SENT_AGO[index]
    return now - timedelta(hours=6 * (index + 1))


def read_at_for_demo_inbox_message(now: datetime, index: int, template_had_read: bool) -> datetime | None:
    if not template_had_read:
        return None
    if index == 2:
        return now - timedelta(hours=20)
    return now - timedelta(hours=2)


def _load_template_meta() -> dict:
    return json.loads(_TEMPLATE_FILE.read_text(encoding="utf-8"))


def template_patient_uuid() -> uuid.UUID:
    meta = _load_template_meta()
    return uuid.UUID(str(meta["template_patient_uuid"]))


def demo_marker_record_title() -> str:
    meta = _load_template_meta()
    return str(meta["marker_record_title"])


def patient_has_demo_marker_record(db, patient_id: uuid.UUID) -> bool:
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


def patient_has_demo_dashboard(db, patient_id: uuid.UUID) -> bool:
    """True when the patient has the full demo dashboard (not only records from a failed clone)."""
    if not patient_has_demo_marker_record(db, patient_id):
        return False
    if db.get(CareEpisodeSession, patient_id) is None:
        return False
    has_appointment = (
        db.query(CareEpisodeAppointment.appointment_uuid)
        .filter(CareEpisodeAppointment.patient_uuid == patient_id)
        .limit(1)
        .first()
        is not None
    )
    has_message = (
        db.query(CareEpisodeInboxMessage.message_uuid)
        .filter(CareEpisodeInboxMessage.patient_uuid == patient_id)
        .limit(1)
        .first()
        is not None
    )
    return has_appointment and has_message


def _lock_patient_demo_clone(db, patient_id: uuid.UUID) -> None:
    """Serialize concurrent clone-demo requests for the same patient."""
    lock_key = patient_id.int % ((2**63) - 1)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})


def _soft_delete_row(row, *, changed_by_uuid: uuid.UUID, changed_by_type: int) -> None:
    row.change_type = 3
    row.changed_by_uuid = changed_by_uuid
    row.changed_by_type = changed_by_type


def _dedupe_demo_inbox_messages(
    db,
    patient_id: uuid.UUID,
    *,
    changed_by_uuid: uuid.UUID,
    changed_by_type: int,
) -> int:
    """Drop duplicate inbox rows with the same sender and body, keeping the newest."""
    rows = (
        db.query(CareEpisodeInboxMessage)
        .filter(CareEpisodeInboxMessage.patient_uuid == patient_id)
        .order_by(
            CareEpisodeInboxMessage.sent_at.desc(),
            CareEpisodeInboxMessage.message_uuid.desc(),
        )
        .all()
    )
    seen: set[tuple[str, str]] = set()
    removed = 0
    for row in rows:
        key = (row.sender_display_name, row.body)
        if key in seen:
            _soft_delete_row(
                row,
                changed_by_uuid=changed_by_uuid,
                changed_by_type=changed_by_type,
            )
            removed += 1
        else:
            seen.add(key)
    return removed


def _dedupe_demo_appointments(
    db,
    patient_id: uuid.UUID,
    *,
    changed_by_uuid: uuid.UUID,
    changed_by_type: int,
) -> int:
    """Drop duplicate appointments for the same clinician and specialty, keeping the newest."""
    rows = (
        db.query(CareEpisodeAppointment)
        .filter(CareEpisodeAppointment.patient_uuid == patient_id)
        .order_by(
            CareEpisodeAppointment.scheduled_at.desc(),
            CareEpisodeAppointment.appointment_uuid.desc(),
        )
        .all()
    )
    seen: set[tuple[str, str]] = set()
    removed = 0
    for row in rows:
        key = (row.clinician_display_name, row.specialty)
        if key in seen:
            _soft_delete_row(
                row,
                changed_by_uuid=changed_by_uuid,
                changed_by_type=changed_by_type,
            )
            removed += 1
        else:
            seen.add(key)
    return removed


def _refresh_demo_dashboard_times(
    db,
    target_id: uuid.UUID,
    *,
    changed_by_uuid: uuid.UUID,
    changed_by_type: int,
) -> tuple[int, int]:
    _dedupe_demo_appointments(
        db,
        target_id,
        changed_by_uuid=changed_by_uuid,
        changed_by_type=changed_by_type,
    )
    _dedupe_demo_inbox_messages(
        db,
        target_id,
        changed_by_uuid=changed_by_uuid,
        changed_by_type=changed_by_type,
    )
    now = datetime.now(UTC)
    appointments = (
        db.query(CareEpisodeAppointment)
        .filter(CareEpisodeAppointment.patient_uuid == target_id)
        .order_by(CareEpisodeAppointment.scheduled_at.asc())
        .all()
    )
    for idx, row in enumerate(appointments):
        row.scheduled_at = scheduled_at_for_demo_appointment(now, idx)
        row.changed_by_uuid = changed_by_uuid
        row.changed_by_type = changed_by_type

    messages = (
        db.query(CareEpisodeInboxMessage)
        .filter(CareEpisodeInboxMessage.patient_uuid == target_id)
        .order_by(CareEpisodeInboxMessage.sent_at.asc())
        .all()
    )
    for idx, row in enumerate(messages):
        row.sent_at = sent_at_for_demo_inbox_message(now, idx)
        row.read_at = read_at_for_demo_inbox_message(now, idx, row.read_at is not None)
        row.changed_by_uuid = changed_by_uuid
        row.changed_by_type = changed_by_type

    return len(appointments), len(messages)


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
    """Copy session, records, appointments, and inbox from the hidden template patient."""
    target_id = uuid.UUID(str(target_patient_uuid))
    source_id = template_patient_uuid()
    if target_id == source_id:
        raise BadRequest("cannot clone demo data onto the template patient")

    actor_id = uuid.UUID(str(changed_by_uuid))

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

    _lock_patient_demo_clone(db, target_id)

    if patient_has_demo_dashboard(db, target_id):
        appt_count, msg_count = _refresh_demo_dashboard_times(
            db,
            target_id,
            changed_by_uuid=actor_id,
            changed_by_type=changed_by_type,
        )
        db.commit()
        return {
            "patient_uuid": str(target_id),
            "cloned": False,
            "reason": "already_present",
            "appointments_refreshed": appt_count,
            "messages_refreshed": msg_count,
        }

    repair_incomplete = patient_has_demo_marker_record(db, target_id)
    now = datetime.now(UTC)

    if db.get(CareEpisodeSession, target_id) is None:
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
                "last_activity": template_session.last_activity,
                "risk_level": "low",
            },
            changed_by_uuid=changed_by_uuid,
            changed_by_type=changed_by_type,
        )
    db.flush()

    records_added = 0
    if not repair_incomplete:
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
        records_added = len(template_records)

    _dedupe_demo_appointments(
        db,
        target_id,
        changed_by_uuid=actor_id,
        changed_by_type=changed_by_type,
    )
    appointment_count = (
        db.query(CareEpisodeAppointment.appointment_uuid)
        .filter(CareEpisodeAppointment.patient_uuid == target_id)
        .count()
    )
    appointments_added = 0
    sorted_appointments = sorted(template_appointments, key=lambda r: r.scheduled_at)
    if appointment_count == 0:
        for idx, row in enumerate(sorted_appointments):
            shifted = scheduled_at_for_demo_appointment(now, idx)
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
        appointments_added = len(template_appointments)

    _dedupe_demo_inbox_messages(
        db,
        target_id,
        changed_by_uuid=actor_id,
        changed_by_type=changed_by_type,
    )
    message_count = (
        db.query(CareEpisodeInboxMessage.message_uuid)
        .filter(CareEpisodeInboxMessage.patient_uuid == target_id)
        .count()
    )
    messages_added = 0
    sorted_messages = sorted(template_messages, key=lambda r: r.sent_at)
    if message_count == 0:
        for idx, row in enumerate(sorted_messages):
            shifted_sent = sent_at_for_demo_inbox_message(now, idx)
            read_at = read_at_for_demo_inbox_message(now, idx, row.read_at is not None)
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
        messages_added = len(template_messages)
    elif message_count > 0:
        _refresh_demo_dashboard_times(
            db,
            target_id,
            changed_by_uuid=actor_id,
            changed_by_type=changed_by_type,
        )

    db.commit()
    return {
        "patient_uuid": str(target_id),
        "cloned": True,
        "repaired_incomplete": repair_incomplete,
        "records": records_added,
        "appointments": appointments_added,
        "messages": messages_added,
    }
