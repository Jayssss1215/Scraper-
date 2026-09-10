from pathlib import Path

from src.config import Settings
from src.db import Database
from src.missions import run_mission
from src.models import MissionRequest


def test_fixture_mission_missing_fields_ai_disabled_and_deduped(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_AI_CLASSIFICATION", "false")
    settings = Settings(database_path=tmp_path / "leads.db", ai_enabled=False)
    db = Database(settings.database_path)
    _, leads, llm_calls = run_mission(MissionRequest(business_type="cafe", location="Fitzroy", result_limit=10), settings, db)
    assert len(leads) == 3
    assert llm_calls == 0
    assert any(lead.phone is None for lead in leads)
    assert any(lead.website is None for lead in leads)
    assert all(lead.fit == "not assessed" for lead in leads)


def test_result_cap(tmp_path):
    settings = Settings(database_path=tmp_path / "leads.db", max_results=2, ai_enabled=False)
    _, leads, _ = run_mission(MissionRequest(business_type="cafe", location="Fitzroy", result_limit=10), settings, Database(settings.database_path))
    assert len(leads) <= 2

