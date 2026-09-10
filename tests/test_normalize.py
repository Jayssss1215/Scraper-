from src.services.normalize import normalize_phone, normalize_url


def test_australian_phone_normalisation():
    assert normalize_phone("+61 3 9123 4567") == "03 9123 4567"
    assert normalize_phone("0412-345-678") == "0412 345 678"


def test_url_validation():
    assert normalize_url("Example.COM/path/") == "https://example.com/path"
    assert normalize_url("javascript:alert(1)") is None

