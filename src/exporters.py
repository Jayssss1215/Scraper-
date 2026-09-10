import csv
import io
from typing import Iterable

from src.models import Lead


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def leads_csv(leads: Iterable[Lead]) -> bytes:
    fields = ["business_name", "phone", "address", "suburb", "state", "postcode", "website", "category", "fit", "classification_reason", "provider", "source_url", "retrieved_at"]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for lead in leads:
        writer.writerow({field: safe_cell(getattr(lead, field)) for field in fields})
    return stream.getvalue().encode("utf-8-sig")

