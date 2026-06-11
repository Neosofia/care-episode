from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

from src.services.demo_clone_service import (
    _dedupe_demo_appointments,
    _dedupe_demo_inbox_messages,
)

UTC = timezone.utc
PATIENT = UUID("00000000-0000-7000-8000-000000000099")
ACTOR = UUID("00000000-0000-7000-8000-000000000003")


def _mock_query(rows):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
    return db


def test_dedupe_inbox_messages_keeps_newest_per_sender_and_body():
    rows = [
        SimpleNamespace(
            sender_display_name="Dr. Sarah Chen",
            body="Your latest lab results look good.",
            sent_at=datetime(2026, 6, 10, 8, 0, tzinfo=UTC),
            message_uuid=UUID("00000000-0000-7000-8000-000000000001"),
        ),
        SimpleNamespace(
            sender_display_name="Dr. Sarah Chen",
            body="Your latest lab results look good.",
            sent_at=datetime(2026, 6, 10, 6, 0, tzinfo=UTC),
            message_uuid=UUID("00000000-0000-7000-8000-000000000002"),
        ),
        SimpleNamespace(
            sender_display_name="Care Coordinator",
            body="Reminder: please complete your pre-visit questionnaire.",
            sent_at=datetime(2026, 6, 10, 5, 0, tzinfo=UTC),
            message_uuid=UUID("00000000-0000-7000-8000-000000000003"),
        ),
    ]
    db = _mock_query(rows)

    removed = _dedupe_demo_inbox_messages(
        db,
        PATIENT,
        changed_by_uuid=ACTOR,
        changed_by_type=2,
    )

    assert removed == 1
    assert rows[1].change_type == 3
    assert rows[1].changed_by_uuid == ACTOR
    assert rows[1].changed_by_type == 2


def test_dedupe_appointments_keeps_newest_per_clinician_and_specialty():
    rows = [
        SimpleNamespace(
            clinician_display_name="Dr. Sarah Chen",
            specialty="Primary Care",
            scheduled_at=datetime(2026, 6, 20, 10, 0, tzinfo=UTC),
            appointment_uuid=UUID("00000000-0000-7000-8000-000000000011"),
        ),
        SimpleNamespace(
            clinician_display_name="Dr. Sarah Chen",
            specialty="Primary Care",
            scheduled_at=datetime(2026, 6, 18, 10, 0, tzinfo=UTC),
            appointment_uuid=UUID("00000000-0000-7000-8000-000000000012"),
        ),
    ]
    db = _mock_query(rows)

    removed = _dedupe_demo_appointments(
        db,
        PATIENT,
        changed_by_uuid=ACTOR,
        changed_by_type=2,
    )

    assert removed == 1
    assert rows[1].change_type == 3
    assert rows[1].changed_by_uuid == ACTOR
    assert rows[1].changed_by_type == 2
