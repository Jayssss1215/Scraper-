from typing import List, Tuple

from src.config import Settings
from src.db import Database
from src.models import Lead, MissionRequest
from src.providers.fixture_provider import FixtureProvider
from src.providers.google_places import GooglePlacesProvider
from src.services.classifier import classify
from src.services.deduplicate import deduplicate


def run_mission(request: MissionRequest, settings: Settings, db: Database) -> Tuple[int, List[Lead], int]:
    settings.validate()
    request.result_limit = min(request.result_limit, settings.max_results)
    provider = FixtureProvider() if settings.lead_provider == "fixture" else GooglePlacesProvider(settings.google_key, settings.request_timeout)
    mission_id = db.create_mission(request.business_type, request.location, request.targeting_rule, settings.lead_provider)
    leads = deduplicate(provider.search(request))
    llm_calls = 0
    if settings.ai_enabled and settings.openrouter_key and request.targeting_rule.strip():
        leads, llm_calls = classify(leads, request.targeting_rule, db, settings.openrouter_key, settings.openrouter_model, settings.max_llm_classifications, settings.request_timeout)
    db.add_results(mission_id, leads)
    db.finish_mission(mission_id, len(leads), llm_calls=llm_calls)
    return mission_id, leads, llm_calls

