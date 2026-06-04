from __future__ import annotations

import datetime

from authorization_in_the_middle.security import with_security
from flask import Blueprint, Response, g, jsonify, request
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from src.authorization.entities import care_episode_catalog_entities, care_episode_catalog_resource_uid
from src.bootstrap.capabilities import Capabilities
from src.bootstrap.config import settings
from src.db.engine import SessionLocal
from src.services.care_episode_service import (
    create_episode_invite,
    list_sessions,
    patient_appointments,
    mark_inbox_message_read,
    patient_inbox_messages,
    patient_records,
    patient_transcript,
    replace_appointments,
    replace_inbox_messages,
    replace_records,
    replace_transcript,
    upsert_session,
)
from src.services.demo_clone_service import clone_patient_demo_from_template

bp = Blueprint("care-episodes", __name__, url_prefix="/api/v1/care-episodes")

_READ = dict(
    action=Capabilities.CARE_EPISODE_READ,
    resource_fn=care_episode_catalog_resource_uid,
    entities_fn=care_episode_catalog_entities,
    rate_limit=settings.care_episode_read_rate_limit,
)
_WRITE = dict(
    action=Capabilities.CARE_EPISODE_CREATE,
    resource_type="CareEpisodeCatalog",
    rate_limit=settings.care_episode_write_rate_limit,
)


def init_care_episode_routes(app, cedar_evaluator):
    app.extensions["cedar_evaluator"] = cedar_evaluator
    app.register_blueprint(bp)


@bp.get("/sessions")
@with_security(**_READ)
def get_sessions() -> Response:
    tenant_uuid = request.args.get("tenant_uuid")
    with SessionLocal() as db:
        return jsonify({"items": list_sessions(db, tenant_uuid=tenant_uuid)})


@bp.get("/<patient_uuid>/records")
@with_security(**_READ)
def get_records(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": patient_records(db, patient_uuid)})


@bp.get("/<patient_uuid>/transcript")
@with_security(**_READ)
def get_transcript(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": patient_transcript(db, patient_uuid)})


@bp.get("/<patient_uuid>/appointments")
@with_security(**_READ)
def get_appointments(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": patient_appointments(db, patient_uuid)})


@bp.get("/<patient_uuid>/messages")
@with_security(**_READ)
def get_messages(patient_uuid: str) -> Response:
    with SessionLocal() as db:
        return jsonify({"items": patient_inbox_messages(db, patient_uuid)})


@bp.post("/<patient_uuid>/appointments")
@with_security(**_WRITE)
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
@with_security(**_WRITE)
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
@with_security(**_WRITE)
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
@with_security(**_WRITE)
def post_invite() -> Response:
    payload = request.get_json(silent=True) or {}
    required = ("patient_uuid", "procedure_type", "care_window_days")
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise BadRequest(f"missing required fields: {missing}")
    item = create_episode_invite(payload)
    return jsonify({"episode_uuid": item["episode_uuid"], "invite_token": item["invite_token"]}), 201


@bp.post("/sessions")
@with_security(**_WRITE)
def post_session() -> Response:
    payload = request.get_json(silent=True) or {}
    required = (
        "patient_uuid",
        "tenant_uuid",
        "display_code",
        "display_name",
        "surgery",
        "procedure_date",
        "session_id",
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
        item = upsert_session(db, payload, changed_by_uuid=payload.get("changed_by_uuid", "00000000-0000-7000-8000-000000000000"))
    return jsonify(item), 201


_CLONE_DEMO_ACTORS = frozenset({"operator", "clinician", "patient"})


def _authorize_clone_demo(active_actor: str, patient_uuid: str) -> None:
    if active_actor not in _CLONE_DEMO_ACTORS:
        raise Forbidden(
            "operator, clinician, or patient actor required to clone demo patient data"
        )
    if active_actor == "patient":
        claims = getattr(g, "jwt_claims", None) or {}
        principal_uuid = str(claims.get("sub") or "").strip()
        if principal_uuid != str(patient_uuid).strip():
            raise Forbidden("patient may only clone demo data for self")


@bp.post("/<patient_uuid>/clone-demo")
@with_security(**_WRITE)
def post_clone_demo(patient_uuid: str) -> Response:
    active_actor = (request.headers.get("X-Active-Actor") or "").strip().lower()
    _authorize_clone_demo(active_actor, patient_uuid)

    payload = request.get_json(silent=True) or {}
    required = ("tenant_uuid", "display_name", "display_code")
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise BadRequest(f"missing required fields: {missing}")

    with SessionLocal() as db:
        result = clone_patient_demo_from_template(
            db,
            patient_uuid,
            tenant_uuid=str(payload["tenant_uuid"]),
            display_name=str(payload["display_name"]),
            display_code=str(payload["display_code"]),
            changed_by_uuid=str(payload.get("changed_by_uuid", patient_uuid)),
        )
    status = 201 if result.get("cloned") else 200
    return jsonify(result), status


@bp.post("/<patient_uuid>/records")
@with_security(**_WRITE)
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


@bp.post("/<patient_uuid>/transcript")
@with_security(**_WRITE)
def post_transcript(patient_uuid: str) -> Response:
    payload = request.get_json(silent=True) or {}
    messages = payload.get("items")
    if not isinstance(messages, list):
        raise BadRequest("items must be a list")
    with SessionLocal() as db:
        item = replace_transcript(
            db,
            patient_uuid,
            messages,
            changed_by_uuid=payload.get("changed_by_uuid", "00000000-0000-7000-8000-000000000000"),
        )
    return jsonify(item), 201
