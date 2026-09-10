import json
from pathlib import Path
from typing import List

from src.models import Lead, MissionRequest
from src.providers.base import LeadProvider
from src.services.normalize import normalize_phone, normalize_url


class FixtureProvider(LeadProvider):
    def __init__(self, path: Path = Path("data/fixtures/sample_leads.json")):
        self.path = path

    def search(self, mission: MissionRequest) -> List[Lead]:
        records = json.loads(self.path.read_text(encoding="utf-8"))
        query = mission.business_type.lower().strip()
        location = mission.location.lower().strip()
        matches = []
        for row in records:
            searchable = " ".join(str(row.get(k, "")) for k in ("business_name", "category", "suburb", "postcode", "address")).lower()
            if query in searchable and location in searchable:
                row["phone"] = normalize_phone(row.get("phone"))
                row["website"] = normalize_url(row.get("website"))
                matches.append(Lead(**row))
        return matches[: mission.result_limit]

