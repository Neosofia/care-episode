from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import case, func

from werkzeug.exceptions import Conflict, NotFound

from src.db.engine import SessionLocal
from src.models.care_episode import (
    EPISODE_STATUS_ACTIVE,
    EPISODE_STATUS_CLOSED,
    CareEpisode,
    CareEpisodeAppointment,
    CareEpisodeInboxMessage,
    CareEpisodeRecord,
)
from src.models.risk import InteractionRiskState

UTC = datetime.timezone.utc
DEFAULT_CARE_WINDOW_DAYS = 30


def _parse_care_window_days(payload: dict) -> int:
    raw = payload.get("care_window_days")
    if raw is None or raw == "":
        return DEFAULT_CARE_WINDOW_DAYS
    days = int(raw)
    if days <= 0:
        raise ValueError("care_window_days must be a positive integer")
    return days


def _parse_risk_level(payload: dict) -> str:
    level = str(payload.get("risk_level", "low")).strip().lower()
    return level if level in {"high", "medium", "low"} else "low"


def _default_last_activity(now: datetime.datetime | None = None) -> str:
    instant = now or datetime.datetime.now(UTC)
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_last_activity(payload: dict) -> str:
    last_activity = payload.get("last_activity")
    if last_activity is not None and str(last_activity).strip():
        return str(last_activity).strip()
    return _default_last_activity()


def _closed_at_iso(episode: CareEpisode) -> str | None:
    """Closure time from audit-maintained changed_at when the episode is closed."""
    if (episode.status or EPISODE_STATUS_ACTIVE) != EPISODE_STATUS_CLOSED:
        return None
    return episode.changed_at.astimezone(UTC).isoformat()


def _days_post_op(episode: CareEpisode) -> int:
    return (datetime.date.today() - episode.procedure_date).days


def _episode_dict(
    episode: CareEpisode,
    *,
    days_post_op: int | None = None,
    risk_summary: str = "",
    is_current: bool | None = None,
) -> dict:
    payload = {
        "episode_uuid": str(episode.episode_uuid),
        "patient_uuid": str(episode.patient_uuid),
        "display_code": episode.display_code,
        "display_name": episode.display_name,
        "surgery": episode.surgery,
        "procedure_date": episode.procedure_date.isoformat(),
        "recovery_id": episode.recovery_id,
        "risk_level": episode.risk_level or "low",
        "care_window_days": int(episode.care_window_days or DEFAULT_CARE_WINDOW_DAYS),
        "status": episode.status or EPISODE_STATUS_ACTIVE,
        "tenant_uuid": str(episode.tenant_uuid),
        "closed_at": _closed_at_iso(episode),
    }
    if days_post_op is not None:
        payload["days_post_op"] = int(days_post_op)
        payload["risk_summary"] = risk_summary
    if is_current is not None:
        payload["is_current"] = is_current
    return payload


def _latest_risk_summaries_by_patient(db, patient_uuids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not patient_uuids:
        return {}
    rows = (
        db.query(InteractionRiskState.patient_uuid, InteractionRiskState.summary)
        .filter(
            InteractionRiskState.patient_uuid.in_(patient_uuids),
            InteractionRiskState.summary != "",
        )
        .order_by(
            InteractionRiskState.patient_uuid.asc(),
            InteractionRiskState.changed_at.desc(),
        )
        .distinct(InteractionRiskState.patient_uuid)
        .all()
    )
    return {row.patient_uuid: row.summary for row in rows}


def get_active_episode(db, patient_uuid: str) -> CareEpisode | None:
    patient_id = uuid.UUID(str(patient_uuid))
    return (
        db.query(CareEpisode)
        .filter(
            CareEpisode.patient_uuid == patient_id,
            CareEpisode.status == EPISODE_STATUS_ACTIVE,
        )
        .one_or_none()
    )


def get_latest_closed_episode(db, patient_uuid: str) -> CareEpisode | None:
    patient_id = uuid.UUID(str(patient_uuid))
    return (
        db.query(CareEpisode)
        .filter(
            CareEpisode.patient_uuid == patient_id,
            CareEpisode.status == EPISODE_STATUS_CLOSED,
        )
        .order_by(CareEpisode.changed_at.desc())
        .first()
    )


def get_current_episode(db, patient_uuid: str) -> CareEpisode | None:
    return get_active_episode(db, patient_uuid) or get_latest_closed_episode(db, patient_uuid)


def _episode_priority():
    return case(
        (CareEpisode.status == EPISODE_STATUS_ACTIVE, 0),
        else_=1,
    )


def list_patient_episodes(db, patient_uuid: str) -> list[dict]:
    patient_id = uuid.UUID(str(patient_uuid))
    active = get_active_episode(db, patient_uuid)
    rows = (
        db.query(CareEpisode)
        .filter(CareEpisode.patient_uuid == patient_id)
        .order_by(
            _episode_priority(),
            CareEpisode.procedure_date.desc(),
            CareEpisode.changed_at.desc(),
        )
        .all()
    )
    return [
        _episode_dict(
            row,
            is_current=active is not None and row.episode_uuid == active.episode_uuid,
        )
        for row in rows
    ]


def list_episodes(db, tenant_uuid: str | None = None, *, status: str | None = None) -> list[dict]:
    days_post_op = (func.current_date() - CareEpisode.procedure_date).label("days_post_op")
    query = db.query(CareEpisode, days_post_op)
    if tenant_uuid:
        query = query.filter(CareEpisode.tenant_uuid == uuid.UUID(str(tenant_uuid)))
    if status:
        normalized = str(status).strip().lower()
        if normalized in {EPISODE_STATUS_ACTIVE, EPISODE_STATUS_CLOSED}:
            query = query.filter(CareEpisode.status == normalized)
    rows = (
        query.distinct(CareEpisode.patient_uuid)
        .order_by(
            CareEpisode.patient_uuid,
            _episode_priority(),
            CareEpisode.changed_at.desc(),
            CareEpisode.procedure_date.desc(),
            CareEpisode.display_name.asc(),
        )
        .all()
    )
    summaries = _latest_risk_summaries_by_patient(db, [episode.patient_uuid for episode, _ in rows])
    return [
        _episode_dict(
            episode,
            days_post_op=int(days),
            risk_summary=summaries.get(episode.patient_uuid, ""),
        )
        for episode, days in rows
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


def _apply_episode_payload(
    episode: CareEpisode,
    payload: dict,
    *,
    changed_by_uuid: str,
    changed_by_type: int,
    care_window_optional: bool = False,
) -> None:
    episode.display_code = str(payload["display_code"])
    episode.display_name = str(payload["display_name"])
    episode.surgery = str(payload["surgery"])
    episode.procedure_date = datetime.date.fromisoformat(str(payload["procedure_date"]))
    episode.recovery_id = str(payload["recovery_id"])
    episode.last_activity = _normalize_last_activity(payload)
    episode.risk_level = _parse_risk_level(payload)
    if not care_window_optional or "care_window_days" in payload:
        episode.care_window_days = _parse_care_window_days(payload)
    episode.tenant_uuid = uuid.UUID(str(payload["tenant_uuid"]))
    episode.changed_by_uuid = uuid.UUID(str(changed_by_uuid))
    episode.changed_by_type = changed_by_type


def _build_episode_row(
    payload: dict,
    *,
    patient_uuid: uuid.UUID,
    changed_by_uuid: str,
    changed_by_type: int,
) -> CareEpisode:
    row = CareEpisode(
        episode_uuid=uuid.uuid7(),
        patient_uuid=patient_uuid,
        status=EPISODE_STATUS_ACTIVE,
    )
    _apply_episode_payload(
        row,
        payload,
        changed_by_uuid=changed_by_uuid,
        changed_by_type=changed_by_type,
    )
    return row


def upsert_episode(db, payload: dict, *, changed_by_uuid: str, changed_by_type: int = 2) -> dict:
    patient_uuid = uuid.UUID(str(payload["patient_uuid"]))
    reactivate = bool(payload.get("reactivate"))
    if reactivate:
        return start_new_episode(
            db,
            str(patient_uuid),
            payload,
            changed_by_uuid=changed_by_uuid,
            changed_by_type=changed_by_type,
        )

    row = get_active_episode(db, str(patient_uuid))
    if row is None:
        if get_latest_closed_episode(db, str(patient_uuid)) is not None:
            raise Conflict("care episode is closed; reopen or set reactivate=true to start a new episode")
        row = _build_episode_row(
            payload,
            patient_uuid=patient_uuid,
            changed_by_uuid=changed_by_uuid,
            changed_by_type=changed_by_type,
        )
        db.add(row)
    else:
        _apply_episode_payload(
            row,
            payload,
            changed_by_uuid=changed_by_uuid,
            changed_by_type=changed_by_type,
            care_window_optional=True,
        )

    db.commit()
    db.refresh(row)
    return _episode_dict(row, days_post_op=_days_post_op(row))


def get_episode_row(db, episode_uuid: str) -> CareEpisode | None:
    episode_id = uuid.UUID(str(episode_uuid))
    return (
        db.query(CareEpisode)
        .filter(CareEpisode.episode_uuid == episode_id)
        .one_or_none()
    )


def load_episode_for_auth(episode_uuid: str) -> dict[str, Any]:
    """Load member attrs for Cedar when the path id is ``episode_uuid``."""
    with SessionLocal() as db:
        row = get_episode_row(db, episode_uuid)
    if row is None:
        raise NotFound("care episode not found")
    return {
        "patient_uuid": str(row.patient_uuid),
        "episode_uuid": str(row.episode_uuid),
        "tenant_uuid": str(row.tenant_uuid),
    }


def load_patient_for_auth(patient_uuid: str) -> dict[str, Any]:
    """Load member attrs for Cedar when the path id is ``patient_uuid``."""
    with SessionLocal() as db:
        row = get_current_episode(db, patient_uuid)
    attrs: dict[str, Any] = {"patient_uuid": str(patient_uuid)}
    if row is not None:
        attrs["tenant_uuid"] = str(row.tenant_uuid)
    return attrs


def get_episode(db, episode_uuid: str) -> dict | None:
    row = get_episode_row(db, episode_uuid)
    if row is None:
        return None
    active = get_active_episode(db, str(row.patient_uuid))
    is_current = active is not None and row.episode_uuid == active.episode_uuid
    payload = _episode_dict(row, days_post_op=_days_post_op(row))
    payload["is_current"] = is_current
    return payload


def patch_episode(
    db,
    episode_uuid: str,
    payload: dict,
    *,
    changed_by_uuid: str,
    changed_by_type: int = 2,
) -> dict | None:
    row = get_episode_row(db, episode_uuid)
    if row is None:
        return None

    actor_id = uuid.UUID(str(changed_by_uuid))
    patch_fields = {key for key in ("status", "care_window_days") if key in payload}
    if not patch_fields:
        raise ValueError("patch requires at least one of status, care_window_days")

    if "status" in payload:
        new_status = str(payload["status"]).strip().lower()
        if new_status == EPISODE_STATUS_CLOSED:
            if row.status != EPISODE_STATUS_CLOSED:
                row.status = EPISODE_STATUS_CLOSED
        elif new_status == EPISODE_STATUS_ACTIVE:
            if row.status != EPISODE_STATUS_ACTIVE:
                if get_active_episode(db, str(row.patient_uuid)) is not None:
                    raise Conflict("an active care episode exists; close it before reopening this episode")
                row.status = EPISODE_STATUS_ACTIVE
        else:
            raise ValueError("status must be active or closed")

    if "care_window_days" in payload:
        if row.status != EPISODE_STATUS_ACTIVE:
            raise Conflict("cannot change care window on a closed episode")
        row.care_window_days = _parse_care_window_days(payload)

    row.changed_by_uuid = actor_id
    row.changed_by_type = changed_by_type
    db.commit()
    db.refresh(row)
    return _episode_dict(row, days_post_op=_days_post_op(row))


def bulk_close_episodes(
    db,
    patient_uuids: list[str],
    *,
    changed_by_uuid: str,
    changed_by_type: int = 2,
) -> dict:
    actor_id = uuid.UUID(str(changed_by_uuid))
    closed: list[str] = []
    skipped: list[str] = []
    for raw_uuid in patient_uuids:
        patient_id = uuid.UUID(str(raw_uuid))
        row = get_active_episode(db, str(patient_id))
        if row is None:
            skipped.append(str(patient_id))
            continue
        row.status = EPISODE_STATUS_CLOSED
        row.changed_by_uuid = actor_id
        row.changed_by_type = changed_by_type
        closed.append(str(patient_id))
    db.commit()
    return {"closed": closed, "skipped": skipped, "count": len(closed)}


def start_new_episode(
    db,
    patient_uuid: str,
    payload: dict,
    *,
    changed_by_uuid: str,
    changed_by_type: int = 2,
) -> dict:
    if get_active_episode(db, patient_uuid) is not None:
        raise Conflict("an active care episode exists; close it before starting a new procedure")
    patient_id = uuid.UUID(str(patient_uuid))
    row = _build_episode_row(
        payload,
        patient_uuid=patient_id,
        changed_by_uuid=changed_by_uuid,
        changed_by_type=changed_by_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _episode_dict(row, days_post_op=_days_post_op(row))


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
