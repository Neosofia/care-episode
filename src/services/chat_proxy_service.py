from __future__ import annotations

import uuid
from typing import Any

from werkzeug.exceptions import NotFound

from src.authorization.entities import principal_tenant_uuid
from src.clients import chat_client
from src.models.care_episode import CareEpisodeSession
from src.services.care_episode_service import _default_last_activity
from src.services.chat_context import build_interaction_context


def require_session(db, patient_uuid: str) -> CareEpisodeSession:
    patient_id = uuid.UUID(str(patient_uuid))
    session = db.get(CareEpisodeSession, patient_id)
    if session is None:
        raise NotFound("care episode session not found")
    return session


def create_chat_interaction(db, patient_uuid: str) -> dict[str, Any]:
    session = require_session(db, patient_uuid)
    context = build_interaction_context(session, tenant_uuid=principal_tenant_uuid())
    interaction = chat_client.create_interaction(patient_uuid, context=context)
    return {**interaction, "care_episode_uuid": patient_uuid}


def proxy_chat_completion(
    db,
    patient_uuid: str,
    chat_interaction_uuid: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    require_session(db, patient_uuid)
    result = chat_client.create_completion(patient_uuid, chat_interaction_uuid, payload)
    if payload.get("content") or payload.get("session_start"):
        session = db.get(CareEpisodeSession, uuid.UUID(str(patient_uuid)))
        if session is not None:
            session.last_activity = _default_last_activity()
            db.commit()
    return result
