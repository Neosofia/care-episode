from __future__ import annotations

import uuid
from typing import Any

from authorization_in_the_middle.audit_attribution import request_audit_actor
from authorization_in_the_middle.flask_identity import jwt_claim_principal_attributes
from flask import g, has_request_context
from werkzeug.exceptions import Conflict, NotFound

from src.clients import chat_client
from src.models.care_episode import EPISODE_STATUS_ACTIVE, CareEpisode
from src.services.care_episode_service import (
    _default_last_activity,
    get_active_episode,
)
from src.services.chat_context import build_interaction_context
from src.services.risk_evaluation_service import update_risk_after_patient_chat_message


def _jwt_tenant_uuid() -> str:
    if not has_request_context():
        return ""
    claims = getattr(g, "jwt_claims", None) or {}
    if not claims:
        return ""
    _, _, attrs = jwt_claim_principal_attributes(claims)
    return str(attrs.get("tenantId") or "").strip()


def _patient_display_name(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    name = str(payload.get("patient_display_name") or "").strip()
    return name or None


def require_episode(db, patient_uuid: str) -> CareEpisode:
    episode = get_active_episode(db, patient_uuid)
    if episode is None:
        raise NotFound("care episode not found")
    return episode


def require_active_episode(db, patient_uuid: str) -> CareEpisode:
    episode = require_episode(db, patient_uuid)
    if episode.status != EPISODE_STATUS_ACTIVE:
        raise Conflict("care episode is closed")
    return episode


def create_chat_interaction(
    db,
    patient_uuid: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    episode = require_active_episode(db, patient_uuid)
    context = build_interaction_context(
        episode,
        tenant_uuid=_jwt_tenant_uuid(),
        patient_display_name=_patient_display_name(payload),
    )
    interaction = chat_client.create_interaction(patient_uuid, context=context)
    return {**interaction, "care_episode_uuid": str(episode.episode_uuid)}


def _maybe_evaluate_risk(
    db,
    *,
    episode: CareEpisode,
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
        episode=episode,
        chat_interaction_uuid=chat_interaction_uuid,
        message_uuid=str(message_uuid),
        patient_message=content,
        tenant_uuid=_jwt_tenant_uuid(),
        patient_display_name=_patient_display_name(payload),
    )


def proxy_chat_completion(
    db,
    patient_uuid: str,
    chat_interaction_uuid: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    episode = require_active_episode(db, patient_uuid)
    result = chat_client.create_completion(patient_uuid, chat_interaction_uuid, payload)

    risk_outcome = _maybe_evaluate_risk(
        db,
        episode=episode,
        patient_uuid=patient_uuid,
        chat_interaction_uuid=chat_interaction_uuid,
        payload=payload,
        chat_result=result,
    )
    if risk_outcome is not None:
        result["risk_evaluation"] = risk_outcome

    if payload.get("content") or payload.get("session_start"):
        row = get_active_episode(db, patient_uuid)
        if row is not None:
            actor = request_audit_actor()
            row.last_activity = _default_last_activity()
            row.changed_by_uuid = uuid.UUID(actor.uuid)
            row.changed_by_type = actor.type
            db.commit()
    return result
