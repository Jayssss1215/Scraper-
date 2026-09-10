from src.models import Lead


def lead_xp(lead: Lead) -> int:
    if not lead.business_name or not lead.address:
        return 0
    return 10 + (5 if lead.phone or lead.website else 0)

