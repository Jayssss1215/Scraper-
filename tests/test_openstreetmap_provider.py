import httpx

from src.models import MissionRequest
from src.providers.base import ProviderError
from src.providers.openstreetmap import OpenStreetMapProvider


def test_osm_florists_are_normalized_and_gaps_sort_first(monkeypatch):
    payload = {
        "elements": [
            {"type": "node", "id": 2, "tags": {"name": "Website Flowers", "shop": "florist", "website": "flowers.test"}},
            {"type": "way", "id": 1, "tags": {"name": "Gap Blooms", "shop": "florist", "phone": "+61 3 9123 4567", "addr:housenumber": "10", "addr:street": "Rose St", "addr:suburb": "Melbourne"}},
        ]
    }

    def fake_post(*args, **kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("POST", args[0]))

    monkeypatch.setattr(httpx, "post", fake_post)
    leads = OpenStreetMapProvider().search(MissionRequest(business_type="florist", location="Melbourne", result_limit=10))

    assert [lead.business_name for lead in leads] == ["Gap Blooms", "Website Flowers"]
    assert leads[0].fit == "match"
    assert leads[0].website is None
    assert leads[0].address == "10 Rose St, Melbourne"
    assert leads[0].phone == "03 9123 4567"
    assert leads[1].website == "https://flowers.test"
    assert leads[1].fit == "not a match"


def test_osm_provider_rejects_unsupported_scope():
    provider = OpenStreetMapProvider()
    try:
        provider.search(MissionRequest(business_type="plumber", location="Melbourne", result_limit=10))
    except ProviderError as exc:
        assert "florists only" in str(exc)
    else:
        raise AssertionError("Expected an unsupported-category error")
