from werkzeug.exceptions import NotFound
from src.db.data import DOCUMENTS

def get_document_or_404(document_id: str) -> dict[str, str]:
    document = DOCUMENTS.get(document_id)
    if document is None:
        raise NotFound()
    return document
