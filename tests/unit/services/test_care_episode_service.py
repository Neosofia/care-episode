import datetime
import uuid
from unittest.mock import MagicMock

import pytest
from werkzeug.exceptions import Conflict

from src.services.care_episode_service import (
    DEFAULT_CARE_WINDOW_DAYS,
    list_episodes,
    list_patient_episodes,
    start_new_episode,
    upsert_episode,
)

UTC = datetime.timezone.utc
PATIENT_ID = uuid.uuid4()
EPISODE_ID = uuid.uuid7()
TENANT_ID = uuid.uuid4()


def _episode_mock(*, status: str = "active", surgery: str = "Appendectomy") -> MagicMock:
    episode = MagicMock()
    episode.episode_uuid = EPISODE_ID
    episode.patient_uuid = PATIENT_ID
    episode.surgery = surgery
    episode.procedure_date = datetime.date(2026, 5, 28)
    episode.recovery_id = "S-1"
    episode.risk_level = "high"
    episode.care_window_days = 30
    episode.status = status
    episode.tenant_uuid = TENANT_ID
    episode.changed_at = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    return episode


def test_list_episodes_includes_latest_risk_summary():
    episode = _episode_mock()
    summary_row = MagicMock()
    summary_row.patient_uuid = PATIENT_ID
    summary_row.summary = "Patient reports crushing chest pain."

    db = MagicMock()
    episodes_query = MagicMock()
    episodes_query.filter.return_value = episodes_query
    episodes_query.distinct.return_value = episodes_query
    episodes_query.order_by.return_value = episodes_query
    episodes_query.all.return_value = [(episode, 13)]

    summaries_query = MagicMock()
    summaries_query.filter.return_value = summaries_query
    summaries_query.order_by.return_value = summaries_query
    summaries_query.distinct.return_value = summaries_query
    summaries_query.all.return_value = [summary_row]

    db.query.side_effect = [episodes_query, summaries_query]

    items = list_episodes(db)

    assert len(items) == 1
    assert items[0]["patient_uuid"] == str(PATIENT_ID)
    assert items[0]["episode_uuid"] == str(EPISODE_ID)
    assert items[0]["risk_summary"] == "Patient reports crushing chest pain."
    assert items[0]["care_window_days"] == DEFAULT_CARE_WINDOW_DAYS


def test_upsert_episode_updates_care_window_days_on_active_episode():
    active = _episode_mock()
    db = MagicMock()
    active_query = MagicMock()
    active_query.filter.return_value = active_query
    active_query.one_or_none.return_value = active
    db.query.return_value = active_query

    upsert_episode(
        db,
        {
            "patient_uuid": str(PATIENT_ID),
            "tenant_uuid": str(TENANT_ID),
            "surgery": "Appendectomy",
            "procedure_date": "2026-06-01",
            "recovery_id": "EP-PAT1",
            "risk_level": "low",
            "care_window_days": 14,
        },
        changed_by_uuid=str(uuid.uuid4()),
    )

    assert active.care_window_days == 14


def test_list_patient_episodes_returns_all_episode_rows():
    active = _episode_mock(status="active", surgery="Hip replacement")
    prior = _episode_mock(status="closed", surgery="Knee arthroscopy")
    prior.episode_uuid = uuid.uuid7()

    db = MagicMock()
    active_query = MagicMock()
    active_query.filter.return_value = active_query
    active_query.one_or_none.return_value = active

    history_query = MagicMock()
    history_query.filter.return_value = history_query
    history_query.order_by.return_value = history_query
    history_query.all.return_value = [active, prior]

    db.query.side_effect = [active_query, history_query]

    items = list_patient_episodes(db, str(PATIENT_ID))

    assert len(items) == 2
    assert items[0]["is_current"] is True
    assert items[1]["surgery"] == "Knee arthroscopy"
    assert items[1]["is_current"] is False
    assert items[1]["closed_at"] == prior.changed_at.astimezone(UTC).isoformat()


def test_start_new_episode_rejects_active_episode():
    active = _episode_mock(status="active")
    db = MagicMock()
    active_query = MagicMock()
    active_query.filter.return_value = active_query
    active_query.one_or_none.return_value = active
    db.query.return_value = active_query

    with pytest.raises(Conflict, match="active care episode exists"):
        start_new_episode(
            db,
            str(PATIENT_ID),
            {
                "tenant_uuid": str(TENANT_ID),
                "surgery": "Appendectomy",
                "procedure_date": "2026-06-01",
                "recovery_id": "EP-PAT1",
                "risk_level": "low",
            },
            changed_by_uuid=str(uuid.uuid4()),
        )


def test_upsert_episode_rejects_update_when_only_closed_episodes_exist():
    closed = _episode_mock(status="closed")
    db = MagicMock()
    active_query = MagicMock()
    active_query.filter.return_value = active_query
    active_query.one_or_none.return_value = None
    closed_query = MagicMock()
    closed_query.filter.return_value = closed_query
    closed_query.order_by.return_value = closed_query
    closed_query.first.return_value = closed
    db.query.side_effect = [active_query, closed_query]

    with pytest.raises(Conflict, match="care episode is closed"):
        upsert_episode(
            db,
            {
                "patient_uuid": str(PATIENT_ID),
                "tenant_uuid": str(TENANT_ID),
                "surgery": "Appendectomy",
                "procedure_date": "2026-06-01",
                "recovery_id": "EP-PAT1",
                "risk_level": "low",
            },
            changed_by_uuid=str(uuid.uuid4()),
        )
