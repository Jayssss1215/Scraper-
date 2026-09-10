import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from src.models import Lead
from src.services.deduplicate import lead_key

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions (
 id INTEGER PRIMARY KEY, query TEXT NOT NULL, location TEXT NOT NULL, targeting_rule TEXT,
 provider TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT NOT NULL,
 result_count INTEGER DEFAULT 0, provider_calls INTEGER DEFAULT 0, llm_calls INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS leads (
 id INTEGER PRIMARY KEY, canonical_key TEXT UNIQUE NOT NULL, mission_id INTEGER NOT NULL,
 provider TEXT NOT NULL, provider_place_id TEXT, business_name TEXT NOT NULL, phone TEXT,
 address TEXT, suburb TEXT, state TEXT, postcode TEXT, website TEXT, category TEXT,
 source_url TEXT, retrieved_at TEXT, fit TEXT DEFAULT 'not assessed', classification_reason TEXT,
 saved INTEGER DEFAULT 0, user_status TEXT DEFAULT 'new', notes TEXT DEFAULT '',
 FOREIGN KEY(mission_id) REFERENCES missions(id)
);
CREATE TABLE IF NOT EXISTS classifications (
 id INTEGER PRIMARY KEY, canonical_key TEXT NOT NULL, rubric_hash TEXT NOT NULL, model TEXT NOT NULL,
 result TEXT NOT NULL, reason TEXT NOT NULL, evidence TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(canonical_key, rubric_hash, model)
);
CREATE TABLE IF NOT EXISTS usage_events (
 id INTEGER PRIMARY KEY, mission_id INTEGER, service TEXT NOT NULL, operation TEXT NOT NULL,
 request_count INTEGER DEFAULT 1, input_tokens INTEGER, output_tokens INTEGER,
 estimated_cost REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def create_mission(self, query: str, location: str, rule: str, provider: str) -> int:
        with self.connect() as conn:
            cursor = conn.execute("INSERT INTO missions(query,location,targeting_rule,provider,status) VALUES(?,?,?,?,?)", (query, location, rule, provider, "running"))
            return int(cursor.lastrowid)

    def finish_mission(self, mission_id: int, count: int, status: str = "complete", llm_calls: int = 0):
        with self.connect() as conn:
            conn.execute("UPDATE missions SET status=?, result_count=?, provider_calls=1, llm_calls=? WHERE id=?", (status, count, llm_calls, mission_id))

    def add_results(self, mission_id: int, leads: List[Lead]):
        with self.connect() as conn:
            for lead in leads:
                conn.execute("""INSERT INTO leads(canonical_key,mission_id,provider,provider_place_id,business_name,phone,address,suburb,state,postcode,website,category,source_url,retrieved_at,fit,classification_reason)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(canonical_key) DO UPDATE SET mission_id=excluded.mission_id, phone=COALESCE(excluded.phone,leads.phone), website=COALESCE(excluded.website,leads.website), fit=excluded.fit, classification_reason=excluded.classification_reason""",
                (lead_key(lead), mission_id, lead.provider, lead.provider_place_id, lead.business_name, lead.phone, lead.address, lead.suburb, lead.state, lead.postcode, lead.website, lead.category, lead.source_url, lead.retrieved_at, lead.fit, lead.classification_reason))

    def save_keys(self, keys: List[str]):
        if not keys:
            return
        marks = ",".join("?" for _ in keys)
        with self.connect() as conn:
            conn.execute(f"UPDATE leads SET saved=1 WHERE canonical_key IN ({marks})", keys)

    def rows(self, saved_only: bool = False) -> List[Dict]:
        query = "SELECT leads.*, missions.query AS mission_query, missions.location AS mission_location FROM leads JOIN missions ON missions.id=leads.mission_id"
        if saved_only:
            query += " WHERE saved=1"
        query += " ORDER BY leads.id DESC"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query)]

    def update_saved(self, lead_id: int, status: str, notes: str):
        with self.connect() as conn:
            conn.execute("UPDATE leads SET user_status=?, notes=? WHERE id=? AND saved=1", (status, notes, lead_id))

    def delete_saved(self, lead_id: int):
        with self.connect() as conn:
            conn.execute("UPDATE leads SET saved=0, notes='', user_status='new' WHERE id=?", (lead_id,))

    def cached_classification(self, key: str, rubric_hash: str, model: str) -> Optional[Dict]:
        with self.connect() as conn:
            row = conn.execute("SELECT result,reason,evidence FROM classifications WHERE canonical_key=? AND rubric_hash=? AND model=?", (key, rubric_hash, model)).fetchone()
            return dict(row) if row else None

    def cache_classification(self, key: str, rubric_hash: str, model: str, result: str, reason: str, evidence: str):
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO classifications(canonical_key,rubric_hash,model,result,reason,evidence) VALUES(?,?,?,?,?,?)", (key, rubric_hash, model, result, reason, evidence))

