from __future__ import annotations

import datetime

from src.models.care_episode import CareEpisodeSession

UTC = datetime.timezone.utc


def days_post_op_for(session: CareEpisodeSession) -> int:
    return (datetime.date.today() - session.procedure_date).days


def build_interaction_context(
    session: CareEpisodeSession,
    *,
    tenant_uuid: str | None = None,
) -> dict[str, str | int]:
    """Authoritative interaction context from care episode session data."""
    context: dict[str, str | int] = {}
    tenant = (tenant_uuid or str(session.tenant_uuid)).strip()
    if tenant:
        context["tenant_uuid"] = tenant
    display_name = session.display_name.strip()
    if display_name:
        context["patient_display_name"] = display_name
        first_name = display_name.split(maxsplit=1)[0]
        if first_name:
            context["patient_first_name"] = first_name
    surgery = session.surgery.strip()
    if surgery:
        context["procedure_name"] = surgery
    context["procedure_date"] = session.procedure_date.isoformat()
    context["days_post_op"] = days_post_op_for(session)
    risk = (session.risk_level or "low").strip().lower()
    if risk in {"low", "medium", "high"}:
        context["risk_level"] = risk
    return context
