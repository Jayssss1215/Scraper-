from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Lead(BaseModel):
    provider: str
    provider_place_id: Optional[str] = None
    business_name: str = Field(min_length=1)
    phone: Optional[str] = None
    address: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: str = Field(default_factory=utc_now)
    fit: Literal["match", "not a match", "uncertain", "not assessed"] = "not assessed"
    classification_reason: Optional[str] = None

    @field_validator("website", "source_url")
    @classmethod
    def safe_url(cls, value: Optional[str]) -> Optional[str]:
        if value and not value.lower().startswith(("http://", "https://")):
            raise ValueError("Only http/https URLs are permitted")
        return value


class MissionRequest(BaseModel):
    business_type: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=150)
    result_limit: int = Field(ge=1, le=100)
    targeting_rule: str = Field(default="", max_length=1000)

