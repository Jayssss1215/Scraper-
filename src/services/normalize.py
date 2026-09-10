import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


def normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if digits.startswith("61"):
        digits = "0" + digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        if digits.startswith("04"):
            return f"{digits[:4]} {digits[4:7]} {digits[7:]}"
        return f"{digits[:2]} {digits[2:6]} {digits[6:]}"
    return value.strip()


def normalize_url(value: Optional[str]) -> Optional[str]:
    if not value or not value.strip():
        return None
    candidate = value.strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", candidate) and not candidate.lower().startswith(("http://", "https://")):
        return None
    if "://" not in candidate:
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return None
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def normalized_text(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
