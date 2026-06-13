import datetime
import uuid
from unittest.mock import MagicMock

from src.services.care_episode_service import list_recoveries


def test_list_recoveries_includes_latest_risk_summary():
    patient_id = uuid.uuid4()
    recovery = MagicMock()
    recovery.patient_uuid = patient_id
    recovery.display_code = "PAT-1"
    recovery.display_name = "Alice Hartley"
    recovery.surgery = "Appendectomy"
    recovery.procedure_date = datetime.date(2026, 5, 28)
    recovery.recovery_id = "S-1"
    recovery.risk_level = "high"

    summary_row = MagicMock()
    summary_row.patient_uuid = patient_id
    summary_row.summary = "Patient reports crushing chest pain."

    db = MagicMock()
    recoveries_query = MagicMock()
    recoveries_query.filter.return_value = recoveries_query
    recoveries_query.order_by.return_value = recoveries_query
    recoveries_query.all.return_value = [(recovery, 13)]

    summaries_query = MagicMock()
    summaries_query.filter.return_value = summaries_query
    summaries_query.order_by.return_value = summaries_query
    summaries_query.distinct.return_value = summaries_query
    summaries_query.all.return_value = [summary_row]

    db.query.side_effect = [recoveries_query, summaries_query]

    items = list_recoveries(db)

    assert len(items) == 1
    assert items[0]["patient_uuid"] == str(patient_id)
    assert items[0]["risk_summary"] == "Patient reports crushing chest pain."
