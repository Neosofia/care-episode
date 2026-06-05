from __future__ import annotations

import datetime
import uuid
from sqlalchemy import func

from src.models.care_episode import (
    CareEpisodeAppointment,
    CareEpisodeInboxMessage,
    CareEpisodeRecord,
    CareEpisodeSession,
)

UTC = datetime.timezone.utc


def _default_last_activity(now: datetime.datetime | None = None) -> str:
    instant = now or datetime.datetime.now(UTC)
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def list_sessions(db, tenant_uuid: str | None = None) -> list[dict]:
    days_post_op = (func.current_date() - CareEpisodeSession.procedure_date).label("days_post_op")
    query = db.query(CareEpisodeSession, days_post_op)
    if tenant_uuid:
        query = query.filter(CareEpisodeSession.tenant_uuid == uuid.UUID(str(tenant_uuid)))
    rows = query.order_by(CareEpisodeSession.display_name.asc()).all()
    return [
        {
            "patient_uuid": str(session.patient_uuid),
            "display_code": session.display_code,
            "display_name": session.display_name,
            "surgery": session.surgery,
            "procedure_date": session.procedure_date.isoformat(),
            "days_post_op": int(days),
            "session_id": session.session_id,
            "risk_level": session.risk_level or "low",
        }
        for session, days in rows
    ]


def patient_records(db, patient_uuid: str) -> list[dict]:
    rows = (
        db.query(CareEpisodeRecord)
        .filter(CareEpisodeRecord.patient_uuid == uuid.UUID(str(patient_uuid)))
        .order_by(CareEpisodeRecord.date.desc())
        .all()
    )
    return [
        {
            "id": str(row.record_uuid),
            "title": row.title,
            "date": row.date,
            "type": row.type,
            "provider": row.provider,
            "summary": row.summary,
            "imageKey": row.image_key,
        }
        for row in rows
    ]


def create_episode_invite(payload: dict) -> dict:
    patient_uuid = str(uuid.UUID(str(payload["patient_uuid"])))
    return {
        "episode_uuid": str(uuid.uuid7()),
        "invite_token": f"episode_{uuid.uuid4().hex}",
        "patient_uuid": patient_uuid,
    }


def upsert_session(db, payload: dict, *, changed_by_uuid: str, changed_by_type: int = 2) -> dict:
    patient_uuid = uuid.UUID(str(payload["patient_uuid"]))
    row = db.get(CareEpisodeSession, patient_uuid)
    if row is None:
        row = CareEpisodeSession(
            patient_uuid=patient_uuid,
            changed_by_uuid=uuid.UUID(str(changed_by_uuid)),
            changed_by_type=changed_by_type,
        )
        db.add(row)

    row.display_code = str(payload["display_code"])
    row.display_name = str(payload["display_name"])
    row.surgery = str(payload["surgery"])
    row.procedure_date = datetime.date.fromisoformat(str(payload["procedure_date"]))
    row.session_id = str(payload["session_id"])
    last_activity = payload.get("last_activity")
    row.last_activity = (
        str(last_activity).strip()
        if last_activity is not None and str(last_activity).strip()
        else _default_last_activity()
    )
    level = str(payload.get("risk_level", "low")).strip().lower()
    row.risk_level = level if level in {"high", "medium", "low"} else "low"
    row.tenant_uuid = uuid.UUID(str(payload["tenant_uuid"]))
    row.changed_by_uuid = uuid.UUID(str(changed_by_uuid))
    row.changed_by_type = changed_by_type
    db.commit()
    db.refresh(row)
    return {
        "patient_uuid": str(row.patient_uuid),
        "display_code": row.display_code,
        "display_name": row.display_name,
        "surgery": row.surgery,
        "procedure_date": row.procedure_date.isoformat(),
        "days_post_op": (datetime.date.today() - row.procedure_date).days,
        "session_id": row.session_id,
        "risk_level": row.risk_level,
    }


def replace_records(db, patient_uuid: str, records: list[dict], *, changed_by_uuid: str, changed_by_type: int = 2) -> dict:
    patient_id = uuid.UUID(str(patient_uuid))
    existing_rows = (
        db.query(CareEpisodeRecord)
        .filter(CareEpisodeRecord.patient_uuid == patient_id)
        .all()
    )
    existing = {
        (row.title, row.date, row.type, row.provider, row.summary, row.image_key)
        for row in existing_rows
    }

    inserted = 0
    for record in records:
        candidate = (
            str(record["title"]),
            str(record["date"]),
            str(record["type"]),
            str(record["provider"]),
            str(record["summary"]),
            str(record["imageKey"]) if record.get("imageKey") else None,
        )
        if candidate in existing:
            continue
        db.add(
            CareEpisodeRecord(
                patient_uuid=patient_id,
                title=candidate[0],
                date=candidate[1],
                type=candidate[2],
                provider=candidate[3],
                summary=candidate[4],
                image_key=candidate[5],
                changed_by_uuid=uuid.UUID(str(changed_by_uuid)),
                changed_by_type=changed_by_type,
            )
        )
        existing.add(candidate)
        inserted += 1
    db.commit()
    return {"patient_uuid": str(patient_id), "count": inserted}


def _parse_datetime(value: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def patient_appointments(db, patient_uuid: str) -> list[dict]:
    rows = (
        db.query(CareEpisodeAppointment)
        .filter(CareEpisodeAppointment.patient_uuid == uuid.UUID(str(patient_uuid)))
        .order_by(CareEpisodeAppointment.scheduled_at.asc())
        .all()
    )
    return [
        {
            "id": str(row.appointment_uuid),
            "patient_uuid": str(row.patient_uuid),
            "clinician_user_uuid": str(row.clinician_user_uuid),
            "clinician_display_name": row.clinician_display_name,
            "specialty": row.specialty,
            "scheduled_at": row.scheduled_at.astimezone(UTC).isoformat(),
            "status": row.status,
        }
        for row in rows
    ]


def _inbox_message_dict(row: CareEpisodeInboxMessage) -> dict:
    return {
        "id": str(row.message_uuid),
        "patient_uuid": str(row.patient_uuid),
        "sender_user_uuid": str(row.sender_user_uuid) if row.sender_user_uuid else None,
        "sender_display_name": row.sender_display_name,
        "body": row.body,
        "read_at": row.read_at.astimezone(UTC).isoformat() if row.read_at else None,
        "sent_at": row.sent_at.astimezone(UTC).isoformat(),
    }


def patient_inbox_messages(db, patient_uuid: str) -> list[dict]:
    rows = (
        db.query(CareEpisodeInboxMessage)
        .filter(CareEpisodeInboxMessage.patient_uuid == uuid.UUID(str(patient_uuid)))
        .order_by(CareEpisodeInboxMessage.sent_at.desc())
        .all()
    )
    return [_inbox_message_dict(row) for row in rows]


def mark_inbox_message_read(
    db,
    patient_uuid: str,
    message_uuid: str,
    *,
    changed_by_uuid: str,
    changed_by_type: int = 2,
) -> dict | None:
    patient_id = uuid.UUID(str(patient_uuid))
    message_id = uuid.UUID(str(message_uuid))
    actor_id = uuid.UUID(str(changed_by_uuid))
    row = (
        db.query(CareEpisodeInboxMessage)
        .filter(
            CareEpisodeInboxMessage.patient_uuid == patient_id,
            CareEpisodeInboxMessage.message_uuid == message_id,
        )
        .one_or_none()
    )
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = datetime.datetime.now(UTC)
        row.changed_by_uuid = actor_id
        row.changed_by_type = changed_by_type
        db.commit()
    return _inbox_message_dict(row)


def replace_appointments(
    db,
    patient_uuid: str,
    items: list[dict],
    *,
    changed_by_uuid: str,
    changed_by_type: int = 2,
) -> dict:
    patient_id = uuid.UUID(str(patient_uuid))
    actor_id = uuid.UUID(str(changed_by_uuid))
    existing_rows = (
        db.query(CareEpisodeAppointment)
        .filter(CareEpisodeAppointment.patient_uuid == patient_id)
        .all()
    )
    existing = {
        (
            str(row.clinician_user_uuid),
            row.clinician_display_name,
            row.specialty,
            row.scheduled_at.astimezone(UTC),
            row.status,
        )
        for row in existing_rows
    }

    inserted = 0
    for item in items:
        scheduled_at = _parse_datetime(str(item["scheduled_at"]))
        candidate = (
            str(item["clinician_user_uuid"]),
            str(item["clinician_display_name"]),
            str(item["specialty"]),
            scheduled_at,
            str(item["status"]),
        )
        if candidate in existing:
            continue
        db.add(
            CareEpisodeAppointment(
                patient_uuid=patient_id,
                clinician_user_uuid=uuid.UUID(str(item["clinician_user_uuid"])),
                clinician_display_name=candidate[1],
                specialty=candidate[2],
                scheduled_at=scheduled_at,
                status=candidate[4],
                changed_by_uuid=actor_id,
                changed_by_type=changed_by_type,
            )
        )
        existing.add(candidate)
        inserted += 1
    db.commit()
    return {"patient_uuid": str(patient_id), "count": inserted}


def replace_inbox_messages(
    db,
    patient_uuid: str,
    items: list[dict],
    *,
    changed_by_uuid: str,
    changed_by_type: int = 2,
) -> dict:
    patient_id = uuid.UUID(str(patient_uuid))
    actor_id = uuid.UUID(str(changed_by_uuid))
    existing_rows = (
        db.query(CareEpisodeInboxMessage)
        .filter(CareEpisodeInboxMessage.patient_uuid == patient_id)
        .all()
    )
    existing = {
        (
            str(row.sender_user_uuid) if row.sender_user_uuid else None,
            row.sender_display_name,
            row.body,
            row.sent_at.astimezone(UTC),
            row.read_at.astimezone(UTC) if row.read_at else None,
        )
        for row in existing_rows
    }

    inserted = 0
    for item in items:
        read_at = _parse_datetime(str(item["read_at"])) if item.get("read_at") else None
        sent_at = _parse_datetime(str(item["sent_at"]))
        sender_uuid = str(item["sender_user_uuid"]) if item.get("sender_user_uuid") else None
        candidate = (
            sender_uuid,
            str(item["sender_display_name"]),
            str(item["body"]),
            sent_at,
            read_at,
        )
        if candidate in existing:
            continue
        db.add(
            CareEpisodeInboxMessage(
                patient_uuid=patient_id,
                sender_user_uuid=uuid.UUID(sender_uuid) if sender_uuid else None,
                sender_display_name=candidate[1],
                body=candidate[2],
                read_at=read_at,
                sent_at=sent_at,
                changed_by_uuid=actor_id,
                changed_by_type=changed_by_type,
            )
        )
        existing.add(candidate)
        inserted += 1
    db.commit()
    return {"patient_uuid": str(patient_id), "count": inserted}


