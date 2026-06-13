from __future__ import annotations

import uuid
from typing import Any

from werkzeug.exceptions import NotFound

from src.authorization.entities import principal_tenant_uuid
from src.clients import chat_client
from src.models.care_episode import CareEpisodeRecovery
from src.services.care_episode_service import _default_last_activity
from src.services.chat_context import build_interaction_context
from src.services.risk_evaluation_service import update_risk_after_patient_chat_message


def require_recovery(db, patient_uuid: str) -> CareEpisodeRecovery:
    patient_id = uuid.UUID(str(patient_uuid))
    recovery = db.get(CareEpisodeRecovery, patient_id)
    if recovery is None:
        raise NotFound("care episode recovery not found")
    return recovery


def create_chat_interaction(db, patient_uuid: str) -> dict[str, Any]:
    recovery = require_recovery(db, patient_uuid)
    context = build_interaction_context(recovery, tenant_uuid=principal_tenant_uuid())
    interaction = chat_client.create_interaction(patient_uuid, context=context)
    return {**interaction, "care_episode_uuid": patient_uuid}


def _maybe_evaluate_risk(
    db,
    *,
    recovery: CareEpisodeRecovery,
    patient_uuid: str,
    chat_interaction_uuid: str,
    payload: dict[str, Any],
    chat_result: dict[str, Any],
) -> dict[str, Any] | None:
    content = str(payload.get("content") or "").strip()
    if not content or payload.get("session_start") or chat_result.get("intervention"):
        return None

    user_message = chat_result.get("user_message") or {}
    message_uuid = user_message.get("message_uuid")
    if not message_uuid:
        return None

    return update_risk_after_patient_chat_message(
        db,
        recovery=recovery,
        chat_interaction_uuid=chat_interaction_uuid,
        message_uuid=str(message_uuid),
        patient_message=content,
        tenant_uuid=principal_tenant_uuid(),
    )


def proxy_chat_completion(
    db,
    patient_uuid: str,
    chat_interaction_uuid: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    recovery = require_recovery(db, patient_uuid)
    result = chat_client.create_completion(patient_uuid, chat_interaction_uuid, payload)

    risk_outcome = _maybe_evaluate_risk(
        db,
        recovery=recovery,
        patient_uuid=patient_uuid,
        chat_interaction_uuid=chat_interaction_uuid,
        payload=payload,
        chat_result=result,
    )
    if risk_outcome is not None:
        result["risk_evaluation"] = risk_outcome

    if payload.get("content") or payload.get("session_start"):
        row = db.get(CareEpisodeRecovery, uuid.UUID(str(patient_uuid)))
        if row is not None:
            row.last_activity = _default_last_activity()
            db.commit()
    return result
