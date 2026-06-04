#!/usr/bin/env python3
"""Write care-episode/openapi.json from the service contract (run after API changes)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "openapi.json"

ERROR_RESPONSE = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "string",
            "enum": [
                "invalid_request",
                "not_found",
                "method_not_allowed",
                "payload_too_large",
                "http_error",
                "authorization_unavailable",
                "internal_server_error",
            ],
        }
    },
}

RISK_LEVEL = {"type": "string", "enum": ["high", "medium", "low"]}


def _error(_status: int) -> dict:
    return {
        "description": "Error",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
    }


def _patient_uuid_param() -> dict:
    return {
        "name": "patient_uuid",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "format": "uuid"},
    }


def _message_uuid_param() -> dict:
    return {
        "name": "message_uuid",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "format": "uuid"},
    }


def _items_request(item_schema: str) -> dict:
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["items"],
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"$ref": f"#/components/schemas/{item_schema}"},
                        },
                        "changed_by_uuid": {"type": "string", "format": "uuid"},
                    },
                }
            }
        },
    }


def _items_response(_list_schema: str, item_schema: str) -> dict:
    return {
        "200": {
            "description": "Items",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["items"],
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {"$ref": f"#/components/schemas/{item_schema}"},
                            }
                        },
                    }
                }
            },
        },
        "400": _error(400),
        "403": _error(403),
        "503": _error(503),
    }


def _count_response(status: int) -> dict:
    return {
        str(status): {
            "description": "Rows inserted",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ReplaceCountResponse"},
                }
            },
        },
        "400": _error(400),
        "403": _error(403),
        "503": _error(503),
    }


def build_spec() -> dict:
    return {
    "openapi": "3.0.3",
    "info": {
        "title": "Care Episode Service API",
        "version": "0.2.0",
        "description": "Care episodes, demo sessions, records, transcripts, appointments, and inbox messages.",
    },
    "paths": {
        "/health": {
            "get": {
                "operationId": "getHealth",
                "responses": {
                    "200": {
                        "description": "Service health",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            }
                        },
                    }
                },
            }
        },
        "/api/v1/care-episodes/sessions": {
            "get": {
                "operationId": "listCareEpisodeSessions",
                "parameters": [
                    {
                        "name": "tenant_uuid",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "format": "uuid"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Active care episode sessions",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SessionListResponse"},
                            }
                        },
                    },
                    "400": _error(400),
                    "403": _error(403),
                    "503": _error(503),
                },
            },
            "post": {
                "operationId": "upsertCareEpisodeSession",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UpsertSessionRequest"},
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Session upserted",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CareEpisodeSession"},
                            }
                        },
                    },
                    "400": _error(400),
                    "403": _error(403),
                    "503": _error(503),
                },
            },
        },
        "/api/v1/care-episodes/invites": {
            "post": {
                "operationId": "createCareEpisodeInvite",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CreateInviteRequest"},
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Invite created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CreateInviteResponse"},
                            }
                        },
                    },
                    "400": _error(400),
                    "403": _error(403),
                    "503": _error(503),
                },
            }
        },
        "/api/v1/care-episodes/{patient_uuid}/records": {
            "get": {
                "operationId": "listCareEpisodeRecords",
                "parameters": [_patient_uuid_param()],
                "responses": _items_response("RecordListResponse", "CareEpisodeRecord"),
            },
            "post": {
                "operationId": "replaceCareEpisodeRecords",
                "parameters": [_patient_uuid_param()],
                "requestBody": _items_request("RecordUpsertItem"),
                "responses": _count_response(201),
            },
        },
        "/api/v1/care-episodes/{patient_uuid}/transcript": {
            "get": {
                "operationId": "listCareEpisodeTranscript",
                "parameters": [_patient_uuid_param()],
                "responses": _items_response("TranscriptListResponse", "TranscriptMessage"),
            },
            "post": {
                "operationId": "replaceCareEpisodeTranscript",
                "parameters": [_patient_uuid_param()],
                "requestBody": _items_request("TranscriptUpsertItem"),
                "responses": _count_response(201),
            },
        },
        "/api/v1/care-episodes/{patient_uuid}/appointments": {
            "get": {
                "operationId": "listCareEpisodeAppointments",
                "parameters": [_patient_uuid_param()],
                "responses": _items_response("AppointmentListResponse", "CareEpisodeAppointment"),
            },
            "post": {
                "operationId": "replaceCareEpisodeAppointments",
                "parameters": [_patient_uuid_param()],
                "requestBody": _items_request("AppointmentUpsertItem"),
                "responses": _count_response(201),
            },
        },
        "/api/v1/care-episodes/{patient_uuid}/messages": {
            "get": {
                "operationId": "listCareEpisodeInboxMessages",
                "parameters": [_patient_uuid_param()],
                "responses": _items_response("InboxMessageListResponse", "CareEpisodeInboxMessage"),
            },
            "post": {
                "operationId": "replaceCareEpisodeInboxMessages",
                "parameters": [_patient_uuid_param()],
                "requestBody": _items_request("InboxMessageUpsertItem"),
                "responses": _count_response(201),
            },
        },
        "/api/v1/care-episodes/{patient_uuid}/messages/{message_uuid}/read": {
            "patch": {
                "operationId": "markCareEpisodeInboxMessageRead",
                "parameters": [_patient_uuid_param(), _message_uuid_param()],
                "responses": {
                    "200": {
                        "description": "Message marked read",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CareEpisodeInboxMessage"},
                            }
                        },
                    },
                    "404": _error(404),
                    "400": _error(400),
                    "403": _error(403),
                    "503": _error(503),
                },
            }
        },
        "/api/v1/care-episodes/{patient_uuid}/clone-demo": {
            "post": {
                "operationId": "clonePatientDemoCareEpisode",
                "parameters": [_patient_uuid_param()],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CloneDemoRequest"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Demo data already present (may refresh timestamps)",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CloneDemoResponse"},
                            }
                        },
                    },
                    "201": {
                        "description": "Demo data cloned",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CloneDemoResponse"},
                            }
                        },
                    },
                    "400": _error(400),
                    "403": _error(403),
                    "404": _error(404),
                    "503": _error(503),
                },
            }
        },
    },
    "components": {
        "schemas": {
            "HealthResponse": {
                "type": "object",
                "required": ["status", "version"],
                "properties": {
                    "status": {"type": "string", "enum": ["ok"]},
                    "version": {
                        "type": "string",
                        "description": "Service semver from pyproject at install/build time.",
                    },
                },
            },
            "ErrorResponse": ERROR_RESPONSE,
            "CareEpisodeSession": {
                "type": "object",
                "required": [
                    "patient_uuid",
                    "display_code",
                    "display_name",
                    "surgery",
                    "procedure_date",
                    "days_post_op",
                    "session_id",
                    "risk_level",
                ],
                "properties": {
                    "patient_uuid": {"type": "string", "format": "uuid"},
                    "display_code": {"type": "string"},
                    "display_name": {"type": "string"},
                    "surgery": {"type": "string"},
                    "procedure_date": {"type": "string", "format": "date"},
                    "days_post_op": {"type": "integer"},
                    "session_id": {"type": "string"},
                    "risk_level": RISK_LEVEL,
                },
            },
            "UpsertSessionRequest": {
                "type": "object",
                "required": [
                    "patient_uuid",
                    "tenant_uuid",
                    "display_code",
                    "display_name",
                    "surgery",
                    "procedure_date",
                    "session_id",
                    "risk_level",
                ],
                "properties": {
                    "patient_uuid": {"type": "string", "format": "uuid"},
                    "tenant_uuid": {"type": "string", "format": "uuid"},
                    "display_code": {"type": "string"},
                    "display_name": {"type": "string"},
                    "surgery": {"type": "string"},
                    "procedure_date": {"type": "string", "format": "date"},
                    "session_id": {"type": "string"},
                    "risk_level": RISK_LEVEL,
                    "changed_by_uuid": {"type": "string", "format": "uuid"},
                },
            },
            "SessionListResponse": {
                "type": "object",
                "required": ["items"],
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/CareEpisodeSession"},
                    }
                },
            },
            "CreateInviteRequest": {
                "type": "object",
                "required": ["patient_uuid", "procedure_type", "care_window_days"],
                "properties": {
                    "patient_uuid": {"type": "string", "format": "uuid"},
                    "procedure_type": {"type": "string"},
                    "care_window_days": {"type": "integer"},
                    "emr_procedure_ref": {"type": "string"},
                },
            },
            "CreateInviteResponse": {
                "type": "object",
                "required": ["episode_uuid"],
                "properties": {
                    "episode_uuid": {"type": "string", "format": "uuid"},
                    "invite_token": {"type": "string"},
                },
            },
            "CloneDemoRequest": {
                "type": "object",
                "required": ["tenant_uuid", "display_name", "display_code"],
                "properties": {
                    "tenant_uuid": {"type": "string", "format": "uuid"},
                    "display_name": {"type": "string"},
                    "display_code": {"type": "string"},
                    "changed_by_uuid": {"type": "string", "format": "uuid"},
                },
            },
            "CloneDemoResponse": {
                "type": "object",
                "required": ["patient_uuid", "cloned"],
                "properties": {
                    "patient_uuid": {"type": "string", "format": "uuid"},
                    "cloned": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "records": {"type": "integer"},
                    "appointments": {"type": "integer"},
                    "messages": {"type": "integer"},
                    "appointments_refreshed": {"type": "integer"},
                    "messages_refreshed": {"type": "integer"},
                },
            },
            "CareEpisodeRecord": {
                "type": "object",
                "required": ["id", "title", "date", "type", "provider", "summary"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "type": {"type": "string"},
                    "provider": {"type": "string"},
                    "summary": {"type": "string"},
                    "imageKey": {"type": "string"},
                },
            },
            "RecordUpsertItem": {
                "type": "object",
                "required": ["title", "date", "type", "provider", "summary"],
                "properties": {
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "type": {"type": "string"},
                    "provider": {"type": "string"},
                    "summary": {"type": "string"},
                    "imageKey": {"type": "string"},
                },
            },
            "TranscriptMessage": {
                "type": "object",
                "required": ["id", "role", "content", "time"],
                "properties": {
                    "id": {"type": "string"},
                    "role": {"type": "string"},
                    "content": {"type": "string"},
                    "time": {"type": "string"},
                },
            },
            "TranscriptUpsertItem": {
                "type": "object",
                "required": ["role", "content", "time"],
                "properties": {
                    "role": {"type": "string"},
                    "content": {"type": "string"},
                    "time": {"type": "string"},
                },
            },
            "CareEpisodeAppointment": {
                "type": "object",
                "required": [
                    "id",
                    "patient_uuid",
                    "clinician_user_uuid",
                    "clinician_display_name",
                    "specialty",
                    "scheduled_at",
                    "status",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "patient_uuid": {"type": "string", "format": "uuid"},
                    "clinician_user_uuid": {"type": "string", "format": "uuid"},
                    "clinician_display_name": {"type": "string"},
                    "specialty": {"type": "string"},
                    "scheduled_at": {"type": "string", "format": "date-time"},
                    "status": {"type": "string"},
                },
            },
            "AppointmentUpsertItem": {
                "type": "object",
                "required": [
                    "clinician_user_uuid",
                    "clinician_display_name",
                    "specialty",
                    "scheduled_at",
                    "status",
                ],
                "properties": {
                    "clinician_user_uuid": {"type": "string", "format": "uuid"},
                    "clinician_display_name": {"type": "string"},
                    "specialty": {"type": "string"},
                    "scheduled_at": {"type": "string", "format": "date-time"},
                    "status": {"type": "string"},
                },
            },
            "CareEpisodeInboxMessage": {
                "type": "object",
                "required": ["id", "patient_uuid", "sender_display_name", "body", "sent_at"],
                "properties": {
                    "id": {"type": "string"},
                    "patient_uuid": {"type": "string", "format": "uuid"},
                    "sender_user_uuid": {"type": "string", "format": "uuid", "nullable": True},
                    "sender_display_name": {"type": "string"},
                    "body": {"type": "string"},
                    "sent_at": {"type": "string", "format": "date-time"},
                    "read_at": {"type": "string", "format": "date-time", "nullable": True},
                },
            },
            "InboxMessageUpsertItem": {
                "type": "object",
                "required": ["sender_display_name", "body", "sent_at"],
                "properties": {
                    "sender_user_uuid": {"type": "string", "format": "uuid"},
                    "sender_display_name": {"type": "string"},
                    "body": {"type": "string"},
                    "sent_at": {"type": "string", "format": "date-time"},
                    "read_at": {"type": "string", "format": "date-time"},
                },
            },
            "ReplaceCountResponse": {
                "type": "object",
                "required": ["patient_uuid", "count"],
                "properties": {
                    "patient_uuid": {"type": "string", "format": "uuid"},
                    "count": {"type": "integer"},
                },
            },
        }
    },
    }


def main() -> None:
    OUT.write_text(json.dumps(build_spec(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
