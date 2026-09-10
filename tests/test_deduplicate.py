from src.models import Lead
from src.services.deduplicate import deduplicate


def test_provider_id_wins_and_missing_fields_merge():
    leads = [Lead(provider="x", provider_place_id="1", business_name="A", address="1 Road"), Lead(provider="x", provider_place_id="1", business_name="A", address="1 Rd", phone="03 9000 0000")]
    result = deduplicate(leads)
    assert len(result) == 1
    assert result[0].phone == "03 9000 0000"

