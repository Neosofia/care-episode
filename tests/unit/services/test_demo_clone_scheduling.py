from datetime import datetime, timezone

from src.services.demo_clone_service import (
    read_at_for_demo_inbox_message,
    scheduled_at_for_demo_appointment,
    sent_at_for_demo_inbox_message,
)

UTC = timezone.utc


def test_scheduled_appointments_are_in_the_future():
    now = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    first = scheduled_at_for_demo_appointment(now, 0)
    second = scheduled_at_for_demo_appointment(now, 1)
    third = scheduled_at_for_demo_appointment(now, 2)
    assert first > now
    assert second > first
    assert third > second
    assert (first - now).days == 2
    assert (second - now).days == 8
    assert (third - now).days == 23


def test_inbox_messages_are_in_the_past():
    now = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    sent = sent_at_for_demo_inbox_message(now, 0)
    assert sent < now
    assert read_at_for_demo_inbox_message(now, 2, True) < now
