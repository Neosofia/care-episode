import datetime
import uuid
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.exceptions import Conflict

from src.services.care_episode_service import (
    DEFAULT_CARE_WINDOW_DAYS,
    list_episodes,
    list_patient_episodes,
    roster_filter_counts,
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
    episode.last_activity = "2026-06-01T12:00:00Z"
    return episode


def _list_episode_row(*, status: str = "active", surgery: str = "Appendectomy") -> MagicMock:
    row = MagicMock()
    row.episode_uuid = EPISODE_ID
    row.patient_uuid = PATIENT_ID
    row.surgery = surgery
    row.procedure_date = datetime.date(2026, 5, 28)
    row.recovery_id = "S-1"
    row.risk_level = "high"
    row.care_window_days = 30
    row.status = status
    row.tenant_uuid = TENANT_ID
    row.changed_at = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    row.last_activity = "2026-06-01T12:00:00Z"
    row.days_post_op = 13
    return row


def _mock_filtered_subquery():
    subq = MagicMock()
    subq.c.last_activity = MagicMock()
    subq.c.risk_level = MagicMock()
    subq.c.surgery = MagicMock()
    return subq


@patch("src.services.care_episode_service._latest_risk_summaries_by_patient")
@patch("src.services.care_episode_service._filtered_episode_rows_subquery")
def test_list_episodes_includes_latest_risk_summary(mock_filtered_subquery, mock_summaries):
    row = _list_episode_row()
    mock_filtered_subquery.return_value = _mock_filtered_subquery()

    db = MagicMock()
    count_query = MagicMock()
    count_query.select_from.return_value = count_query
    count_query.scalar.return_value = 1

    page_query = MagicMock()
    page_query.order_by.return_value = page_query
    page_query.offset.return_value = page_query
    page_query.limit.return_value = page_query
    page_query.all.return_value = [row]

    db.query.side_effect = [count_query, page_query]
    mock_summaries.return_value = {PATIENT_ID: "Patient reports crushing chest pain."}

    items, total = list_episodes(db)

    assert total == 1
    assert len(items) == 1
    assert items[0]["patient_uuid"] == str(PATIENT_ID)
    assert items[0]["episode_uuid"] == str(EPISODE_ID)
    assert items[0]["risk_summary"] == "Patient reports crushing chest pain."
    assert items[0]["care_window_days"] == DEFAULT_CARE_WINDOW_DAYS


@patch("src.services.care_episode_service._latest_risk_summaries_by_patient", return_value={})
@patch("src.services.care_episode_service._filtered_episode_rows_subquery")
def test_list_episodes_registry_match_uuids_filter(mock_filtered_subquery, _mock_summaries):
    row = _list_episode_row()
    mock_filtered_subquery.return_value = _mock_filtered_subquery()

    db = MagicMock()
    count_query = MagicMock()
    count_query.select_from.return_value = count_query
    count_query.scalar.return_value = 1

    page_query = MagicMock()
    page_query.order_by.return_value = page_query
    page_query.offset.return_value = page_query
    page_query.limit.return_value = page_query
    page_query.all.return_value = [row]

    db.query.side_effect = [count_query, page_query]

    items, total = list_episodes(
        db,
        registry_match_uuids=[PATIENT_ID],
        page=1,
        page_size=20,
    )

    assert total == 1
    assert len(items) == 1
    mock_filtered_subquery.assert_called_once()
    assert mock_filtered_subquery.call_args.kwargs["registry_match_uuids"] == [PATIENT_ID]


@patch("src.services.care_episode_service._filtered_episode_rows_subquery")
def test_roster_filter_counts_aggregates_in_one_query(mock_filtered_subquery):
    subq = _mock_filtered_subquery()
    mock_filtered_subquery.return_value = subq

    db = MagicMock()
    counts_query = MagicMock()
    counts_query.select_from.return_value = counts_query
    counts_query.one.return_value = (3, 2, 5, 1)
    db.query.return_value = counts_query

    counts = roster_filter_counts(db, str(TENANT_ID))

    assert counts == {
        "high_risk_count": 3,
        "medium_risk_count": 2,
        "chats_today_count": 5,
        "active_patients_30m_count": 1,
    }
    mock_filtered_subquery.assert_called_once()
    db.query.assert_called_once()


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
        changed_by_type=1,
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
            changed_by_type=1,
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
