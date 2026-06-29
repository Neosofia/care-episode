from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.bootstrap.logging_config import log_event
from src.db.engine import SessionLocal
from src.models.care_episode import EPISODE_STATUS_ACTIVE
from src.services.care_episode_service import get_episode_row
from src.services.risk_evaluation_service import update_risk_after_patient_chat_message

_executor: ThreadPoolExecutor | None = None


def _risk_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="risk-eval")
        atexit.register(_shutdown_risk_executor)
    return _executor


def _shutdown_risk_executor() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=False)
        _executor = None


def schedule_risk_evaluation_after_chat(
    *,
    patient_uuid: str,
    episode_uuid: str,
    chat_interaction_uuid: str,
    message_uuid: str,
    patient_message: str,
    tenant_uuid: str | None,
    patient_display_name: str | None,
) -> None:
    """Run risk scoring and optional escalation off the chat completion request thread."""
    _risk_executor().submit(
        _run_risk_evaluation,
        patient_uuid,
        episode_uuid,
        chat_interaction_uuid,
        message_uuid,
        patient_message,
        tenant_uuid,
        patient_display_name,
    )


def _run_risk_evaluation(
    patient_uuid: str,
    episode_uuid: str,
    chat_interaction_uuid: str,
    message_uuid: str,
    patient_message: str,
    tenant_uuid: str | None,
    patient_display_name: str | None,
) -> None:
    try:
        with SessionLocal() as db:
            episode = get_episode_row(db, episode_uuid)
            if episode is None or str(episode.patient_uuid) != patient_uuid:
                log_event(
                    "risk_evaluation.background_skipped",
                    reason="episode_not_found",
                    patient_uuid=patient_uuid,
                    episode_uuid=episode_uuid,
                )
                return
            if episode.status != EPISODE_STATUS_ACTIVE:
                log_event(
                    "risk_evaluation.background_skipped",
                    reason="episode_not_active",
                    patient_uuid=patient_uuid,
                    episode_uuid=episode_uuid,
                )
                return

            update_risk_after_patient_chat_message(
                db,
                episode=episode,
                chat_interaction_uuid=chat_interaction_uuid,
                message_uuid=message_uuid,
                patient_message=patient_message,
                tenant_uuid=tenant_uuid,
                patient_display_name=patient_display_name,
            )
    except Exception:
        log_event(
            "risk_evaluation.background_failed",
            patient_uuid=patient_uuid,
            episode_uuid=episode_uuid,
            chat_interaction_uuid=chat_interaction_uuid,
        )
