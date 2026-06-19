from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.audit_mixin import HistoryColumnsMixin


class CareEpisodeRecoveryHistory(Base, HistoryColumnsMixin):
    __tablename__ = "care_episode_recoveries_history"

    episode_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    patient_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    surgery: Mapped[str] = mapped_column(String(255), nullable=False)
    procedure_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    recovery_id: Mapped[str] = mapped_column(String(64), nullable=False)
    last_activity: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    care_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    tenant_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class InteractionRiskStateHistory(Base, HistoryColumnsMixin):
    __tablename__ = "interaction_risk_states_history"

    chat_interaction_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    patient_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
