from __future__ import annotations

import uuid

from sqlalchemy import func, select

from src.models.audit_history import CareEpisodeRecoveryHistory, InteractionRiskStateHistory
from src.models.care_episode import CareEpisode

VALID_AUDIT_SOURCES = frozenset({"episode", "risk"})


class InvalidAuditSourceError(ValueError):
    pass


class PatientNotFoundError(LookupError):
    pass


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _map_episode_audit_row(row) -> dict:
    return {
        "history_uuid": str(row["history_uuid"]) if row["history_uuid"] else None,
        "episode_uuid": str(row["episode_uuid"]),
        "patient_uuid": str(row["patient_uuid"]),
        "surgery": row["surgery"],
        "procedure_date": row["procedure_date"].isoformat() if row["procedure_date"] else None,
        "recovery_id": row["recovery_id"],
        "risk_level": row["risk_level"],
        "care_window_days": int(row["care_window_days"]),
        "status": row["status"],
        "tenant_uuid": str(row["tenant_uuid"]),
        "changed_at": _iso(row["changed_at"]),
        "changed_by_uuid": str(row["changed_by_uuid"]),
        "changed_by_type": row["changed_by_type"],
        "change_type": row["change_type"],
    }


def _map_risk_audit_row(row) -> dict:
    return {
        "history_uuid": str(row["history_uuid"]) if row["history_uuid"] else None,
        "chat_interaction_uuid": str(row["chat_interaction_uuid"]),
        "patient_uuid": str(row["patient_uuid"]),
        "summary": row["summary"] or "",
        "changed_at": _iso(row["changed_at"]),
        "changed_by_uuid": str(row["changed_by_uuid"]),
        "changed_by_type": row["changed_by_type"],
        "change_type": row["change_type"],
    }


def _patient_has_episode(db, patient_uuid: uuid.UUID) -> bool:
    return (
        db.query(CareEpisode.episode_uuid)
        .filter(CareEpisode.patient_uuid == patient_uuid)
        .limit(1)
        .first()
        is not None
    )


def get_patient_audits(
    db,
    patient_uuid: str,
    source: str,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    if source not in VALID_AUDIT_SOURCES:
        raise InvalidAuditSourceError("source must be 'episode' or 'risk'")

    target = uuid.UUID(str(patient_uuid))
    if not _patient_has_episode(db, target):
        raise PatientNotFoundError(patient_uuid)

    if source == "episode":
        history_table = CareEpisodeRecoveryHistory.__table__
        mapper = _map_episode_audit_row
    else:
        history_table = InteractionRiskStateHistory.__table__
        mapper = _map_risk_audit_row

    where_clause = history_table.c.patient_uuid == target
    query = (
        select(history_table)
        .where(where_clause)
        .order_by(history_table.c.changed_at.desc())
    )

    total = db.scalar(
        select(func.count()).select_from(
            select(history_table).where(where_clause).subquery()
        )
    )
    rows = db.execute(query.offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return [mapper(row) for row in rows], int(total or 0)
