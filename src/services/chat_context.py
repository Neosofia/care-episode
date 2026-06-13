from __future__ import annotations

import datetime

from src.models.care_episode import CareEpisodeRecovery

UTC = datetime.timezone.utc


def days_post_op_for(recovery: CareEpisodeRecovery) -> int:
    return (datetime.date.today() - recovery.procedure_date).days


def build_interaction_context(
    recovery: CareEpisodeRecovery,
    *,
    tenant_uuid: str | None = None,
) -> dict[str, str | int]:
    """Authoritative interaction context from care episode recovery data."""
    context: dict[str, str | int] = {}
    tenant = (tenant_uuid or str(recovery.tenant_uuid)).strip()
    if tenant:
        context["tenant_uuid"] = tenant
    display_name = recovery.display_name.strip()
    if display_name:
        context["patient_display_name"] = display_name
        first_name = display_name.split(maxsplit=1)[0]
        if first_name:
            context["patient_first_name"] = first_name
    surgery = recovery.surgery.strip()
    if surgery:
        context["procedure_name"] = surgery
    context["procedure_date"] = recovery.procedure_date.isoformat()
    context["days_post_op"] = days_post_op_for(recovery)
    risk = (recovery.risk_level or "low").strip().lower()
    if risk in {"low", "medium", "high"}:
        context["risk_level"] = risk
    return context
