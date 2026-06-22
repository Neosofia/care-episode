import pytest

from src.services.procedure_catalog import (
    load_procedure_catalog,
    procedure_catalog,
    procedure_catalog_response,
    search_procedure_catalog,
)

pytestmark = pytest.mark.unit


def test_procedure_catalog_loads_entries():
    catalog = load_procedure_catalog()
    assert len(catalog.procedures) >= 50
    assert catalog.procedure_type_labels["general-surgery"] == "General surgery"


def test_search_procedure_catalog_filters_by_name():
    matches = search_procedure_catalog("cholecystectomy")
    assert len(matches) == 1
    assert matches[0]["id"] == "lap-chole"


def test_search_procedure_catalog_filters_by_specialty():
    matches = search_procedure_catalog("orthopedics")
    assert matches
    assert all("Orthopedics" in entry["specialty"] for entry in matches)


def test_search_procedure_catalog_empty_query_returns_all():
    all_entries = search_procedure_catalog("")
    filtered = search_procedure_catalog("knee")
    assert len(all_entries) > len(filtered)


def test_procedure_catalog_response_includes_labels():
    response = procedure_catalog_response("cabg")
    assert response["procedure_type_labels"]["cardiac"] == "Cardiac"
    assert len(response["items"]) == 1
    assert response["items"][0]["id"] == "cabg"


def test_procedure_catalog_ids_are_unique():
    catalog = procedure_catalog()
    ids = [entry.id for entry in catalog.procedures]
    assert len(ids) == len(set(ids))
