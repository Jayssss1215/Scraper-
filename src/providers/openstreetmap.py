from typing import Any, Dict, List, Optional

import httpx

from src.models import Lead, MissionRequest, utc_now
from src.providers.base import LeadProvider, ProviderError
from src.services.normalize import normalize_phone, normalize_url


class OpenStreetMapProvider(LeadProvider):
    """Small-batch public business discovery using OpenStreetMap's Overpass API."""

    URL = "https://overpass-api.de/api/interpreter"
    # Central and inner Melbourne. Keeping V1 geographically bounded makes one
    # polite request practical on shared, donation-funded Overpass servers.
    MELBOURNE_BBOX = (-37.95, 144.80, -37.65, 145.25)
    SUPPORTED_CATEGORIES = {
        "florist": ("shop", "florist"),
        "florists": ("shop", "florist"),
        "flower shop": ("shop", "florist"),
        "flower shops": ("shop", "florist"),
    }

    def __init__(self, timeout: int = 30, endpoint: Optional[str] = None):
        self.timeout = timeout
        self.endpoint = endpoint or self.URL

    def search(self, mission: MissionRequest) -> List[Lead]:
        location = mission.location.casefold().strip()
        if "melbourne" not in location:
            raise ProviderError("The free Website Gap prototype currently supports Melbourne only.")
        category = self.SUPPORTED_CATEGORIES.get(mission.business_type.casefold().strip())
        if not category:
            raise ProviderError("The free Website Gap prototype currently supports florists only.")

        key, value = category
        south, west, north, east = self.MELBOURNE_BBOX
        query = f"""[out:json][timeout:25];
(
  nwr[\"{key}\"=\"{value}\"][\"name\"]({south},{west},{north},{east});
);
out tags center;"""
        try:
            response = httpx.post(
                self.endpoint,
                data={"data": query},
                headers={"User-Agent": "JaysAIControlRoom/0.2 (local learning prototype)"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {429, 502, 503, 504}:
                raise ProviderError("The free OpenStreetMap server is busy. Wait a minute and try again.") from exc
            raise ProviderError(f"OpenStreetMap returned an error ({exc.response.status_code}).") from exc
        except (httpx.RequestError, ValueError) as exc:
            raise ProviderError("OpenStreetMap could not be reached or returned an invalid response.") from exc

        leads = [self._to_lead(item) for item in payload.get("elements", []) if item.get("tags", {}).get("name")]
        leads.sort(key=lambda lead: (lead.website is not None, lead.business_name.casefold()))
        return leads[: mission.result_limit]

    @staticmethod
    def _to_lead(item: Dict[str, Any]) -> Lead:
        tags = item.get("tags", {})
        website = normalize_url(tags.get("website") or tags.get("contact:website"))
        address_parts = [
            " ".join(filter(None, [tags.get("addr:housenumber"), tags.get("addr:street")])),
            tags.get("addr:suburb") or tags.get("addr:city"),
            tags.get("addr:state"),
            tags.get("addr:postcode"),
        ]
        address = ", ".join(part for part in address_parts if part) or None
        element_type = item.get("type", "node")
        element_id = str(item.get("id", ""))
        has_gap = website is None
        return Lead(
            provider="osm",
            provider_place_id=f"{element_type}/{element_id}",
            business_name=tags["name"],
            phone=normalize_phone(tags.get("phone") or tags.get("contact:phone")),
            address=address,
            suburb=tags.get("addr:suburb") or tags.get("addr:city"),
            state=tags.get("addr:state"),
            postcode=tags.get("addr:postcode"),
            website=website,
            category="Florist",
            source_url=f"https://www.openstreetmap.org/{element_type}/{element_id}",
            retrieved_at=utc_now(),
            fit="match" if has_gap else "not a match",
            classification_reason=(
                "No website is listed in OpenStreetMap; verify manually before outreach."
                if has_gap
                else "An independent website is listed in OpenStreetMap."
            ),
        )
