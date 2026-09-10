from src.models import Lead
from src.scoring import lead_xp


def test_xp_is_transparent():
    assert lead_xp(Lead(provider="x", business_name="A", address="1 Road")) == 10
    assert lead_xp(Lead(provider="x", business_name="A", address="1 Road", website="https://a.example")) == 15
    assert lead_xp(Lead(provider="x", business_name="A")) == 0

