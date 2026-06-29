from __future__ import annotations

import datetime
import uuid
from typing import Any

from authorization_in_the_middle.audit_attribution import (
    reject_client_audit_attribution,
    request_audit_actor,
)
from authorization_in_the_middle.rest_entities import (
    _entities_for_write_member,
    _resource_uid_for_write_member,
    _resource_uid_from_entity,
    _rest_entities_for_item,
)
from authorization_in_the_middle.security import with_security
from authorization_in_the_middle.service_conventions import _import_entities_module
from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadGateway, BadRequest, Conflict, NotFound

from src.authorization import entities as auth_entities
from src.bootstrap.config import settings
from src.bootstrap.request_telemetry import log_request_handled
from src.clients import user_client
from src.db.engine import SessionLocal
from src.services.care_episode_service import (
    bulk_close_episodes,
    enrolled_patient_uuids,
    get_episode,
    list_episodes,
    list_patient_episodes,
    load_episode_for_auth,
    load_patient_for_auth,
    patch_episode,
    patient_appointments,
    mark_inbox_message_read,
    patient_inbox_messages,
    patient_records,
    replace_appointments,
    replace_inbox_messages,
    replace_records,
    roster_summary,
    start_new_episode,
    upsert_episode,
)
from src.services.patient_audit_service import (
    InvalidAuditSourceError,
    PatientNotFoundError,
    get_patient_audits,
)
from src.services.procedure_catalog import procedure_catalog_response
from src.services.chat_proxy_service import (
    create_chat_interaction,
    proxy_chat_completion,
)

bp = Blueprint("care-episodes", __name__, url_prefix="/api/v1/care-episodes")

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100
_PROCEDURE_CATALOG_CACHE_SECONDS = 30 * 60


def _parse_pagination() -> tuple[int, int] | tuple[None, tuple]:
    try:
        page = max(1, int(request.args.get("page", 1)))
        page_size = min(
            _MAX_PAGE_SIZE,
            max(1, int(request.args.get("page_size", _DEFAULT_PAGE_SIZE))),
        )
    except (TypeError, ValueError):
        return None, (
            jsonify({"error": "invalid pagination", "message": "page and page_size must be integers"}),
            400,
        )
    return (page, page_size), None

_MEMBER_LIST = dict(
    action='Action::"care-episode:list"',
    id_arg="patient_uuid",
    resource_loader=load_patient_for_auth,
)
_MEMBER_CREATE = dict(
    action='Action::"care-episode:create"',
    id_arg="patient_uuid",
    resource_loader=load_patient_for_auth,
)


def _catalog_tenant_attrs() -> dict[str, str]:
    tenant_uuid = str(request.args.get("tenant_uuid") or "").strip()
    return {"tenantId": tenant_uuid}


def _principal_tenant_catalog_attrs() -> dict[str, str]:
    principal = auth_entities.resolve_principal()
    tenant_id = str((principal.get("attrs") or {}).get("tenantId") or "").strip()
    return {"tenantId": tenant_id}


def _episode_write_record() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return dict(payload) if isinstance(payload, dict) else {}


def _patient_episode_write_record() -> dict[str, Any]:
    record = _episode_write_record()
    patient_uuid = (request.view_args or {}).get("patient_uuid")
    if patient_uuid:
        record["patient_uuid"] = patient_uuid
    return record


def _episode_write_entities() -> list[dict[str, Any]]:
    return _entities_for_write_member(
        _import_entities_module(),
        "care_episode",
        _episode_write_record(),
        namespace=auth_entities.NAMESPACE,
    )


def _patient_episode_write_entities() -> list[dict[str, Any]]:
    return _entities_for_write_member(
        _import_entities_module(),
        "care_episode",
        _patient_episode_write_record(),
        namespace=auth_entities.NAMESPACE,
    )


def _episode_write_resource_uid() -> str:
    return _resource_uid_for_write_member(
        _import_entities_module(),
        "care_episode",
        _episode_write_record(),
        namespace=auth_entities.NAMESPACE,
    )


def _patient_episode_write_resource_uid() -> str:
    return _resource_uid_for_write_member(
        _import_entities_module(),
        "care_episode",
        _patient_episode_write_record(),
        namespace=auth_entities.NAMESPACE,
    )


def _episode_member_entities() -> list[dict[str, Any]]:
    return _rest_entities_for_item(
        "care_episode",
        "care_episode",
        "episode_uuid",
        _import_entities_module(),
        load_episode_for_auth,
        namespace=auth_entities.NAMESPACE,
    )


def _episode_member_resource_uid() -> str:
    return _resource_uid_from_entity(_episode_member_entities()[1])


def _audit_actor_from_request(payload: dict | None = None):
    reject_client_audit_attribution(payload)
    return request_audit_actor()


def _registry_search(tenant_uuid: str | None, search: str | None) -> tuple[list, dict[str, dict]]:
    trimmed_tenant = str(tenant_uuid or "").strip()
    trimmed_search = str(search or "").strip()
    if not trimmed_tenant or not trimmed_search:
        return [], {}
    users = user_client.list_tenant_patient_users(trimmed_tenant, search=trimmed_search)
    registry_uuids: list = []
    profiles: dict[str, dict] = {}
    for user in users:
        user_uuid = str(user.get("uuid") or "").strip()
        if not user_uuid:
            continue
        registry_uuids.append(uuid.UUID(user_uuid))
        profiles[user_uuid] = user_client.patient_profile_from_user(user)
    return registry_uuids, profiles


def _attach_patient_profiles(
    items: list[dict],
    prefetched_profiles: dict[str, dict] | None = None,
) -> None:
    if not items:
        return
    profiles = dict(prefetched_profiles or {})
    patient_uuids = [str(item["patient_uuid"]) for item in items]
    missing = [user_uuid for user_uuid in patient_uuids if user_uuid not in profiles]
    tenant_uuid = str(items[0].get("tenant_uuid") or "").strip()
    if missing and tenant_uuid:
        profiles.update(user_client.get_patient_profiles_for_tenant(tenant_uuid, missing))
    for item in items:
        profile = profiles.get(str(item["patient_uuid"]))
        if profile:
            item["patient"] = profile


def init_care_episode_routes(app, cedar_evaluator):
    app.extensions["cedar_evaluator"] = cedar_evaluator
    app.register_blueprint(bp)


@bp.get("")
@with_security(
    rate_limit=settings.care_episode_read_rate_limit,
    catalog_attrs=_catalog_tenant_attrs,
)
def get_care_episodes() -> Response:
    tenant_uuid = request.args.get("tenant_uuid")
    status = request.args.get("status")
    risk = request.args.get("risk")
    q = request.args.get("q")
    activity = request.args.get("activity")
    min_days_post_op = request.args.get("min_days_post_op")
    min_days_since_chat = request.args.get("min_days_since_chat")
    pagination, error = _parse_pagination()
    if error is not None:
        return error
    page, page_size = pagination
    parsed_min_days_post_op = None
    parsed_min_days_since_chat = None
    try:
        if min_days_post_op is not None and str(min_days_post_op).strip():
            parsed_min_days_post_op = int(min_days_post_op)
        if min_days_since_chat is not None and str(min_days_since_chat).strip():
            parsed_min_days_since_chat = int(min_days_since_chat)
    except (TypeError, ValueError):
        return (
            jsonify({"error": "invalid filter", "message": "min_days_post_op and min_days_since_chat must be integers"}),
            400,
        )
    with SessionLocal() as db:
        registry_matches, registry_profiles = _registry_search(tenant_uuid, q)
        items, total = list_episodes(
            db,
            tenant_uuid=tenant_uuid,
            status=status,
            risk=risk,
            q=q,
            registry_match_uuids=registry_matches,
            min_days_post_op=parsed_min_days_post_op,
            activity=activity,
            min_days_since_activity=parsed_min_days_since_chat,
            page=page,
            page_size=page_size,
        )
        _attach_patient_profiles(items, registry_profiles)
        return jsonify({"items": items, "total": total, "page": page, "page_size": page_size})


@bp.get("/roster-summary")
@with_security(
    rate_limit=settings.care_episode_read_rate_limit,
    catalog_attrs=_catalog_tenant_attrs,
)
def get_roster_summary() -> Response:
    tenant_uuid = str(request.args.get("tenant_uuid") or "").strip()
    if not tenant_uuid:
        return jsonify({"error": "invalid_request", "message": "tenant_uuid is required"}), 400
    pagination, error = _parse_pagination()
    if error is not None:
        return error
    preview_page, preview_page_size = pagination
    with SessionLocal() as db:
        summary = roster_summary(
            db,
            tenant_uuid,
            preview_page=preview_page,
            preview_page_size=preview_page_size,
            active_chat_page_size=10,
        )
        _attach_patient_profiles(
            summary["preview"]["items"] + summary["active_chats"]["items"],
        )
        return jsonify(summary)


@bp.get("/enrollable-patients")
@with_security(
    rate_limit=settings.care_episode_read_rate_limit,
    catalog_attrs=_catalog_tenant_attrs,
)
def get_enrollable_patients() -> Response:
    tenant_uuid = str(request.args.get("tenant_uuid") or "").strip()
    if not tenant_uuid:
        return jsonify({"error": "invalid_request", "message": "tenant_uuid is required"}), 400
    search = str(request.args.get("q") or "").strip()
    registry_users = user_client.list_tenant_patient_users(tenant_uuid, search=search or None)
    with SessionLocal() as db:
        enrolled = enrolled_patient_uuids(db, tenant_uuid)
    items = [
        row
        for row in registry_users
        if row.get("uuid") and uuid.UUID(str(row["uuid"])) not in enrolled
    ]
    return jsonify({"items": items, "total": len(items)})


@bp.get("/procedures")
@with_security(
    rate_limit=settings.care_episode_read_rate_limit,
    catalog_attrs=_principal_tenant_catalog_attrs,
)
def get_procedure_catalog() -> Response:
    query = request.args.get("q")
    response = jsonify(procedure_catalog_response(query))
    response.headers["Cache-Control"] = f"private, max-age={_PROCEDURE_CATALOG_CACHE_SECONDS}"
    return response


@bp.post("/bulk-close")
@with_security(
    action='Action::"care-episode:create"',
    rate_limit=settings.care_episode_write_rate_limit,
    catalog_attrs=_principal_tenant_catalog_attrs,
)
def post_bulk_close_episodes() -> Response:
    payload = request.get_json(silent=True) or {}
    reject_client_audit_attribution(payload)
    patient_uuids = payload.get("patient_uuids")
    if not isinstance(patient_uuids, list) or not patient_uuids:
        raise BadRequest("patient_uuids must be a non-empty list")
    actor = request_audit_actor()
    with SessionLocal() as db:
        item = bulk_close_episodes(
            db,
            [str(value) for value in patient_uuids],
            changed_by_uuid=actor.uuid,
            changed_by_type=actor.type,
        )
    return jsonify(item)


@bp.get("/<episode_uuid>")
@with_security(
    action='Action::"care-episode:list"',
    rate_limit=settings.care_episode_read_rate_limit,
    entities_fn=_episode_member_entities,
    resource_fn=_episode_member_resource_uid,
)
def get_episode_by_uuid(episode_uuid: str) -> Response:
    with SessionLocal() as db:
        item = get_episode(db, episode_uuid)
    if item is None:
        raise NotFound("care episode not found")
    return jsonify(item)


@bp.patch("/<episode_uuid>")
@with_security(
    action='Action::"care-episode:create"',
    rate_limit=settings.care_episode_write_rate_limit,
    entities_fn=_episode_member_entities,
    resource_fn=_episode_member_resource_uid,
)
def patch_episode_by_uuid(episode_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    actor = _audit_actor_from_request(payload)
    with SessionLocal() as db:
        try:
            item = patch_episode(
                db,
                episode_uuid,
                payload,
                changed_by_uuid=actor.uuid,
                changed_by_type=actor.type,
            )
        except Conflict as exc:
            raise BadRequest(str(exc)) from exc
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc
    if item is None:
        raise NotFound("care episode not found")
    return jsonify(item)


@bp.get("/<patient_uuid>/episodes")
@with_security(rate_limit=settings.care_episode_read_rate_limit, **_MEMBER_LIST)
def get_patient_episodes(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": list_patient_episodes(db, patient_uuid)})


@bp.post("/<patient_uuid>/episodes")
@with_security(
    rate_limit=settings.care_episode_write_rate_limit,
    action='Action::"care-episode:create"',
    id_arg="patient_uuid",
    entities_fn=_patient_episode_write_entities,
    resource_fn=_patient_episode_write_resource_uid,
)
def post_start_episode(patient_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    required = (
        "tenant_uuid",
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
        try:
            actor = _audit_actor_from_request(payload)
            item = start_new_episode(
                db,
                patient_uuid,
                payload,
                changed_by_uuid=actor.uuid,
                changed_by_type=actor.type,
            )
        except Conflict as exc:
            raise BadRequest(str(exc)) from exc
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc
    return jsonify(item), 201


@bp.get("/<patient_uuid>/audits")
@with_security(rate_limit=settings.care_episode_read_rate_limit, **_MEMBER_LIST)
def get_patient_audit_history(patient_uuid: str) -> Response:
    pagination, error = _parse_pagination()
    if error:
        return error
    page, page_size = pagination
    source = (request.args.get("source") or "").strip().lower()
    if not source:
        return jsonify({"error": "invalid source", "message": "source must be 'episode' or 'risk'"}), 400
    try:
        with SessionLocal() as db:
            items, total = get_patient_audits(db, patient_uuid, source, page, page_size)
            return jsonify({
                "patient_uuid": patient_uuid,
                "source": source,
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }), 200
    except PatientNotFoundError:
        raise NotFound("patient care episodes not found")
    except InvalidAuditSourceError:
        return jsonify({"error": "invalid source", "message": "source must be 'episode' or 'risk'"}), 400


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
    actor = _audit_actor_from_request(payload)
    items = payload.get("items")
    if not isinstance(items, list):
        raise BadRequest("items must be a list")
    with SessionLocal() as db:
        item = replace_appointments(
            db,
            patient_uuid,
            items,
            changed_by_uuid=actor.uuid,
            changed_by_type=actor.type,
        )
    return jsonify(item), 201


@bp.patch("/<patient_uuid>/messages/<message_uuid>/read")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def patch_message_read(patient_uuid: str, message_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    actor = _audit_actor_from_request(payload)
    with SessionLocal() as db:
        item = mark_inbox_message_read(
            db,
            patient_uuid,
            message_uuid,
            changed_by_uuid=actor.uuid,
            changed_by_type=actor.type,
        )
    if item is None:
        raise NotFound("message not found")
    return jsonify(item)


@bp.post("/<patient_uuid>/messages")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def post_messages(patient_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    actor = _audit_actor_from_request(payload)
    items = payload.get("items")
    if not isinstance(items, list):
        raise BadRequest("items must be a list")
    with SessionLocal() as db:
        item = replace_inbox_messages(
            db,
            patient_uuid,
            items,
            changed_by_uuid=actor.uuid,
            changed_by_type=actor.type,
        )
    return jsonify(item), 201


@bp.post("")
@with_security(
    action='Action::"care-episode:create"',
    resource_fn=_episode_write_resource_uid,
    entities_fn=_episode_write_entities,
    rate_limit=settings.care_episode_write_rate_limit,
)
def post_care_episode() -> Response:
    payload = request.get_json(silent=True) or {}
    required = (
        "patient_uuid",
        "tenant_uuid",
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
        try:
            actor = _audit_actor_from_request(payload)
            item = upsert_episode(
                db,
                payload,
                changed_by_uuid=actor.uuid,
                changed_by_type=actor.type,
            )
        except Conflict as exc:
            raise BadRequest(str(exc)) from exc
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc
    return jsonify(item), 201


@bp.post("/<patient_uuid>/chat/interactions")
@with_security(rate_limit=settings.care_episode_write_rate_limit, **_MEMBER_CREATE)
def post_chat_interaction(patient_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    try:
        with SessionLocal() as db:
            item = create_chat_interaction(db, patient_uuid, payload)
    except NotFound:
        log_request_handled("chat_interaction_create", 404, outcome="no_episode")
        raise
    except Conflict:
        log_request_handled("chat_interaction_create", 409, outcome="episode_closed")
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
        log_request_handled("chat_completion_proxy", 404, outcome="no_episode")
        raise
    except Conflict:
        log_request_handled("chat_completion_proxy", 409, outcome="episode_closed")
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
    actor = _audit_actor_from_request(payload)
    records = payload.get("items")
    if not isinstance(records, list):
        raise BadRequest("items must be a list")
    with SessionLocal() as db:
        item = replace_records(
            db,
            patient_uuid,
            records,
            changed_by_uuid=actor.uuid,
            changed_by_type=actor.type,
        )
    return jsonify(item), 201
