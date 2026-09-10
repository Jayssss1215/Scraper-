from typing import Iterable, List

from src.models import Lead
from src.services.normalize import normalized_text


def lead_key(lead: Lead) -> str:
    if lead.provider_place_id:
        return f"{lead.provider}:{lead.provider_place_id}"
    return "|".join([
        normalized_text(lead.business_name),
        normalized_text(lead.address),
        normalized_text(lead.phone),
    ])


def deduplicate(leads: Iterable[Lead]) -> List[Lead]:
    chosen = {}
    for lead in leads:
        key = lead_key(lead)
        if key not in chosen:
            chosen[key] = lead
            continue
        old = chosen[key]
        for field in ("phone", "address", "suburb", "state", "postcode", "website", "category", "source_url"):
            if not getattr(old, field) and getattr(lead, field):
                setattr(old, field, getattr(lead, field))
    return list(chosen.values())

