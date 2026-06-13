from __future__ import annotations

import uuid

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.audit_mixin import AuditColumnsMixin


class InteractionRiskState(Base, AuditColumnsMixin):
    __tablename__ = "interaction_risk_states"

    chat_interaction_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    patient_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
