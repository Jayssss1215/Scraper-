from typing import List

import httpx

from src.models import Lead, MissionRequest, utc_now
from src.providers.base import LeadProvider, ProviderError
from src.services.normalize import normalize_phone, normalize_url


class GooglePlacesProvider(LeadProvider):
    URL = "https://places.googleapis.com/v1/places:searchText"

    def __init__(self, api_key: str, timeout: int = 20):
        self.api_key = api_key
        self.timeout = timeout

    def search(self, mission: MissionRequest) -> List[Lead]:
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.primaryType,places.googleMapsUri,places.addressComponents",
        }
        try:
            response = httpx.post(self.URL, headers=headers, json={"textQuery": f"{mission.business_type} in {mission.location}", "pageSize": min(mission.result_limit, 20)}, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 429:
                raise ProviderError("The provider rate limit was reached. Wait, lower the mission size, then try again.") from exc
            if code in {401, 403}:
                raise ProviderError("The Google Places key was rejected. Check the key, API access, restrictions, and billing.") from exc
            raise ProviderError(f"The provider returned an error ({code}). No invented results were added.") from exc
        except httpx.RequestError as exc:
            raise ProviderError("The provider could not be reached. Check your connection and try again.") from exc
        leads = []
        for place in response.json().get("places", []):
            components = {c.get("types", [""])[0]: c.get("longText") for c in place.get("addressComponents", [])}
            leads.append(Lead(provider="google", provider_place_id=place.get("id"), business_name=place.get("displayName", {}).get("text", "Unknown business"), phone=normalize_phone(place.get("nationalPhoneNumber")), address=place.get("formattedAddress"), suburb=components.get("locality"), state=components.get("administrative_area_level_1"), postcode=components.get("postal_code"), website=normalize_url(place.get("websiteUri")), category=place.get("primaryType"), source_url=place.get("googleMapsUri"), retrieved_at=utc_now()))
        return leads

