from __future__ import annotations

import datetime

from src.models.care_episode import CareEpisode

UTC = datetime.timezone.utc


def days_post_op_for(episode: CareEpisode) -> int:
    return (datetime.date.today() - episode.procedure_date).days


def build_interaction_context(
    episode: CareEpisode,
    *,
    tenant_uuid: str | None = None,
    patient_display_name: str | None = None,
) -> dict[str, str | int]:
    """Interaction context from care episode data plus optional client-supplied greeting name."""
    context: dict[str, str | int] = {}
    tenant = (tenant_uuid or str(episode.tenant_uuid)).strip()
    if tenant:
        context["tenant_uuid"] = tenant
    display_name = str(patient_display_name or "").strip()
    if display_name:
        context["patient_display_name"] = display_name
        first_name = display_name.split(maxsplit=1)[0]
        if first_name:
            context["patient_first_name"] = first_name
    surgery = episode.surgery.strip()
    if surgery:
        context["procedure_name"] = surgery
    context["procedure_date"] = episode.procedure_date.isoformat()
    context["days_post_op"] = days_post_op_for(episode)
    risk = (episode.risk_level or "low").strip().lower()
    if risk in {"low", "medium", "high"}:
        context["risk_level"] = risk
    return context
