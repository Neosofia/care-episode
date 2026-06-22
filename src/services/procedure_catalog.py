"""Post-operative procedure catalog for enrollment and episode creation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

PROCEDURE_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "procedure_catalog.json"

VALID_PROCEDURE_TYPES = frozenset({"general-surgery", "orthopedic", "cardiac", "other"})


@dataclass(frozen=True)
class ProcedureCatalogEntry:
    id: str
    name: str
    procedure_type: str
    emr_ref: str
    specialty: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "procedure_type": self.procedure_type,
            "emr_ref": self.emr_ref,
            "specialty": self.specialty,
        }


@dataclass(frozen=True)
class ProcedureCatalog:
    procedure_type_labels: dict[str, str]
    procedures: tuple[ProcedureCatalogEntry, ...]

    @property
    def by_id(self) -> dict[str, ProcedureCatalogEntry]:
        return {entry.id: entry for entry in self.procedures}


def _parse_entry(raw: dict[str, Any], *, source: Path) -> ProcedureCatalogEntry:
    entry_id = str(raw.get("id", "")).strip()
    name = str(raw.get("name", "")).strip()
    procedure_type = str(raw.get("procedure_type", "")).strip()
    emr_ref = str(raw.get("emr_ref", "")).strip()
    specialty = str(raw.get("specialty", "")).strip()
    if not entry_id or not name or not procedure_type or not emr_ref or not specialty:
        raise ValueError(f"{source} procedure entries require id, name, procedure_type, emr_ref, and specialty")
    if procedure_type not in VALID_PROCEDURE_TYPES:
        raise ValueError(f"{source} has unknown procedure_type {procedure_type!r} for id {entry_id!r}")
    return ProcedureCatalogEntry(
        id=entry_id,
        name=name,
        procedure_type=procedure_type,
        emr_ref=emr_ref,
        specialty=specialty,
    )


def load_procedure_catalog(path: Path = PROCEDURE_CATALOG_PATH) -> ProcedureCatalog:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")

    raw_labels = data.get("procedure_type_labels")
    if not isinstance(raw_labels, dict):
        raise ValueError(f"{path} must include procedure_type_labels")
    procedure_type_labels = {
        str(key).strip(): str(value).strip()
        for key, value in raw_labels.items()
        if str(key).strip() and str(value).strip()
    }
    missing_labels = sorted(VALID_PROCEDURE_TYPES - set(procedure_type_labels))
    if missing_labels:
        raise ValueError(f"{path} is missing procedure_type_labels for: {missing_labels}")

    raw_procedures = data.get("procedures")
    if not isinstance(raw_procedures, list) or not raw_procedures:
        raise ValueError(f"{path} must include a non-empty procedures list")

    procedures: list[ProcedureCatalogEntry] = []
    seen_ids: set[str] = set()
    for raw in raw_procedures:
        if not isinstance(raw, dict):
            raise ValueError(f"{path} procedures entries must be objects")
        entry = _parse_entry(raw, source=path)
        if entry.id in seen_ids:
            raise ValueError(f"{path} contains duplicate procedure id {entry.id!r}")
        seen_ids.add(entry.id)
        procedures.append(entry)

    return ProcedureCatalog(
        procedure_type_labels=procedure_type_labels,
        procedures=tuple(procedures),
    )


@lru_cache(maxsize=1)
def procedure_catalog() -> ProcedureCatalog:
    return load_procedure_catalog()


def search_procedure_catalog(query: str | None = None) -> list[dict[str, str]]:
    catalog = procedure_catalog()
    normalized = (query or "").strip().lower()
    if not normalized:
        return [entry.to_dict() for entry in catalog.procedures]

    matches: list[ProcedureCatalogEntry] = []
    for entry in catalog.procedures:
        haystack = " ".join(
            [
                entry.name,
                entry.specialty,
                entry.emr_ref,
                catalog.procedure_type_labels.get(entry.procedure_type, entry.procedure_type),
                entry.procedure_type,
            ]
        ).lower()
        if normalized in haystack:
            matches.append(entry)
    return [entry.to_dict() for entry in matches]


def procedure_catalog_response(query: str | None = None) -> dict[str, Any]:
    catalog = procedure_catalog()
    return {
        "items": search_procedure_catalog(query),
        "procedure_type_labels": dict(catalog.procedure_type_labels),
    }
