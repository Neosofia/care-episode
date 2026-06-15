from __future__ import annotations

import datetime
from typing import Any

from authorization_in_the_middle.rest_entities import _entities_for_write_member, _resource_uid_for_write_member
from authorization_in_the_middle.security import with_security
from authorization_in_the_middle.service_conventions import _import_entities_module
from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadGateway, BadRequest, NotFound

from src.authorization import entities as auth_entities
from src.bootstrap.config import settings
from src.bootstrap.request_telemetry import log_request_handled
from src.db.engine import SessionLocal
from src.services.care_episode_service import (
    create_episode_invite,
    list_recoveries,
    patient_appointments,
    mark_inbox_message_read,
    patient_inbox_messages,
    patient_records,
    replace_appointments,
    replace_inbox_messages,
    replace_records,
    upsert_recovery,
)
from src.services.chat_proxy_service import create_chat_interaction, proxy_chat_completion

bp = Blueprint("care-episodes", __name__, url_prefix="/api/v1/care-episodes")

_MEMBER_LIST = dict(action='Action::"care-episode:list"', id_arg="patient_uuid")
_MEMBER_CREATE = dict(action='Action::"care-episode:create"', id_arg="patient_uuid")


def _recovery_write_record() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return dict(payload) if isinstance(payload, dict) else {}


def _recovery_write_entities() -> list[dict[str, Any]]:
    return _entities_for_write_member(
        _import_entities_module(),
        "care_episode",
        _recovery_write_record(),
        namespace=auth_entities.NAMESPACE,
    )


def _recovery_write_resource_uid() -> str:
    return _resource_uid_for_write_member(
        _import_entities_module(),
        "care_episode",
        _recovery_write_record(),
        namespace=auth_entities.NAMESPACE,
    )


def init_care_episode_routes(app, cedar_evaluator):
    app.extensions["cedar_evaluator"] = cedar_evaluator
    app.register_blueprint(bp)


@bp.get("/recoveries")
@with_security(rate_limit=settings.care_episode_read_rate_limit)
def get_recoveries() -> Response:
    tenant_uuid = request.args.get("tenant_uuid")
    with SessionLocal() as db:
        return jsonify({"items": list_recoveries(db, tenant_uuid=tenant_uuid)})


@bp.get("/<patient_uuid>/records")
@with_security(rate_limit=settings.care_episode_read_rate_limit, **_MEMBER_LIST)
def get_records(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": patient_records(db, patient_uuid)})


@bp.get("/<patient_uuid>/appointments")
@with_security(rate_limit=settings.care_episode_read_rate_limit, **_MEMBER_LIST)
def get_appointments(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": patient_appointments(db, patient_uuid)})


@bp.get("/<patient_uuid>/messages")
@with_security(rate_limit=settings.care_episode_read_rate_limit, **_MEMBER_LIST)
def get_messages(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": patient_inbox_messages(db, patient_uuid)})


@bp.post("/<patient_uuid>/appointments")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def post_appointments(patient_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list):
        raise BadRequest("items must be a list")
    with SessionLocal() as db:
        item = replace_appointments(
            db,
            patient_uuid,
            items,
            changed_by_uuid=payload.get("changed_by_uuid", "00000000-0000-7000-8000-000000000000"),
        )
    return jsonify(item), 201


@bp.patch("/<patient_uuid>/messages/<message_uuid>/read")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def patch_message_read(patient_uuid: str, message_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        item = mark_inbox_message_read(
            db,
            patient_uuid,
            message_uuid,
            changed_by_uuid=payload.get("changed_by_uuid", patient_uuid),
        )
    if item is None:
        raise NotFound("message not found")
    return jsonify(item)


@bp.post("/<patient_uuid>/messages")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def post_messages(patient_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list):
        raise BadRequest("items must be a list")
    with SessionLocal() as db:
        item = replace_inbox_messages(
            db,
            patient_uuid,
            items,
            changed_by_uuid=payload.get("changed_by_uuid", "00000000-0000-7000-8000-000000000000"),
        )
    return jsonify(item), 201


@bp.post("/invites")
@with_security(
    action='Action::"care-episode:create"',
    rate_limit=settings.care_episode_write_rate_limit,
)
def post_invite() -> Response:
    payload = request.get_json(silent=True) or {}
    required = ("patient_uuid", "procedure_type", "care_window_days")
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise BadRequest(f"missing required fields: {missing}")
    item = create_episode_invite(payload)
    return jsonify({"episode_uuid": item["episode_uuid"], "invite_token": item["invite_token"]}), 201


@bp.post("/recoveries")
@with_security(
    action='Action::"care-episode:create"',
    resource_fn=_recovery_write_resource_uid,
    entities_fn=_recovery_write_entities,
    rate_limit=settings.care_episode_write_rate_limit,
)
def post_recovery() -> Response:
    payload = request.get_json(silent=True) or {}
    required = (
        "patient_uuid",
        "tenant_uuid",
        "display_code",
        "display_name",
        "surgery",
        "procedure_date",
        "recovery_id",
        "risk_level",
    )
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise BadRequest(f"missing required fields: {missing}")
    try:
        datetime.date.fromisoformat(str(payload["procedure_date"]))
    except ValueError as exc:
        raise BadRequest("procedure_date must be YYYY-MM-DD") from exc
    with SessionLocal() as db:
        item = upsert_recovery(db, payload, changed_by_uuid=payload.get("changed_by_uuid", "00000000-0000-7000-8000-000000000000"))
    return jsonify(item), 201


@bp.post("/<patient_uuid>/chat/interactions")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def post_chat_interaction(patient_uuid: str) -> Response:
    try:
        with SessionLocal() as db:
            item = create_chat_interaction(db, patient_uuid)
    except NotFound:
        log_request_handled("chat_interaction_create", 404, outcome="no_recovery")
        raise
    except BadGateway:
        log_request_handled("chat_interaction_create", 502, outcome="chat_downstream")
        raise
    log_request_handled("chat_interaction_create", 201, outcome="success")
    return jsonify(item), 201


@bp.post("/<patient_uuid>/chat/interactions/<chat_interaction_uuid>/completions")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def post_chat_completion(patient_uuid: str, chat_interaction_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    try:
        with SessionLocal() as db:
            item = proxy_chat_completion(db, patient_uuid, chat_interaction_uuid, payload)
    except NotFound:
        log_request_handled("chat_completion_proxy", 404, outcome="no_recovery")
        raise
    except BadGateway:
        log_request_handled("chat_completion_proxy", 502, outcome="chat_downstream")
        raise
    log_request_handled("chat_completion_proxy", 200, outcome="success")
    return jsonify(item)


@bp.post("/<patient_uuid>/records")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def post_records(patient_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    records = payload.get("items")
    if not isinstance(records, list):
        raise BadRequest("items must be a list")
    with SessionLocal() as db:
        item = replace_records(
            db,
            patient_uuid,
            records,
            changed_by_uuid=payload.get("changed_by_uuid", "00000000-0000-7000-8000-000000000000"),
        )
    return jsonify(item), 201
