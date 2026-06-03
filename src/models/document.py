from typing import Any
from authorization_in_the_middle import build_entity_payload, build_entity_ref

NAMESPACE = "demo"

def build_document_entity(document_id: str, document: dict[str, Any]) -> dict[str, Any]:
    return build_entity_payload(
        f"{NAMESPACE}::Document",
        document_id,
        {
            "owner": build_entity_ref(f"{NAMESPACE}::Patient", document["owner_patient_id"]),
            "clinic_id": document["clinic_id"],
        },
    )
