# Jay's AI Control Room

A local-first Streamlit dashboard for finding and reviewing public local-business leads. V1 ships with a free Training Ground fixture, an optional authorised Google Places API adapter, local SQLite storage, safe CSV exports, and an optional OpenRouter-powered classifier.

The app never performs outreach. It never invents missing facts: missing values are shown as **Not available**.

## Quick start on a Mac

You need Python 3.11 or newer. In Terminal, open this project folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Streamlit will print a local address, usually `http://localhost:8501`. Open it in your browser. Choose **cafe** and **Fitzroy**, then select **Start Mission**. This fixture demo needs no API key and makes no paid calls.

After the first setup, the one-command launch is:

```bash
source .venv/bin/activate && streamlit run app.py
```

## What works

- Control Room with character level, Lead Hunter, transparent XP, mission preview, and locked future skills
- Fixture missions with realistic Australian records, duplicates, and intentionally missing values
- Normalisation for Australian phone numbers and safe HTTP(S) URLs
- Deduplication by provider ID, then normalised identifying fields
- Search and filters, select/save workflow, local Lead Vault, notes and statuses
- Confirmed removal from the Vault and formula-injection-safe CSV export
- Optional Google Places API (New) text search with a minimal field mask and actionable error states
- Optional OpenRouter classification using structured JSON, uncertainty, per-mission caps, and a local cache

XP is deterministic: a unique saved lead with a business name and address earns 10 XP, plus 5 if it has a phone or website. Saving the same canonical lead again does not create another record or award duplicate XP. XP has no monetary value.

## Settings and local data

Copy `.env.example` to `.env` and edit only `.env`. The default settings use the fixture provider and keep AI off. The SQLite database is stored at `data/leads.db`; generated databases, exports, secrets, logs, and caches are ignored by Git.

Mission caps are configured with:

```dotenv
MAX_RESULTS_PER_MISSION=25
MAX_PROVIDER_REQUESTS_PER_MISSION=10
MAX_LLM_CLASSIFICATIONS_PER_MISSION=10
```

V1 makes one provider search request per mission. The lower of the mission result limit and configured classification cap is used for AI assessment.

## Optional Google Places setup

Before enabling Google, confirm that its current terms permit your intended storage, display, and export of business data. Create a dedicated Google Cloud API key, enable Places API (New), add a small quota and billing alerts, and apply the strongest practical API/application restrictions.

Set these values in `.env`:

```dotenv
LEAD_PROVIDER=google
GOOGLE_MAPS_API_KEY=your_key_here
```

This project calls the authorised Places API and does not scrape Google Maps pages. Requested fields can affect billing, and costs change; review the live [pricing](https://developers.google.com/maps/billing-and-pricing/pricing), [Places usage and billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing), and [API-key security guidance](https://developers.google.com/maps/api-security-best-practices) before use.

OpenStreetMap's public Nominatim service is not used. Its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) discourages systematic bulk collection and imposes strict requirements.

## Optional Scout Brain

OpenRouter is useful only when a targeting rule needs subjective judgement. Exact category, suburb, postcode, keyword, sorting, deduplication, and export logic remain deterministic.

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
ENABLE_AI_CLASSIFICATION=true
```

Model availability and pricing can change, so review your chosen model before use. The classifier sends only the business name, category, suburb, and website value alongside your rubric. It validates structured JSON, supports `uncertain`, caches by lead/rubric/model, and stops at the configured cap. If the key is missing or AI is off, it makes zero OpenRouter calls.

## Tests

```bash
pytest -q
```

Tests cover phone and URL normalisation, deduplication, XP, missing values, AI-disabled behavior, result caps, and an end-to-end fixture mission.

## Troubleshooting

- **Python is too old:** install Python 3.11+ from python.org or Homebrew, then recreate `.venv`.
- **No fixture results:** use `cafe` and `Fitzroy`; fixture search is intentionally literal and predictable.
- **Google key rejected:** check that Places API (New) is enabled, billing is active, and restrictions permit this server-side request.
- **Provider rate limit:** wait, reduce mission size, and inspect the quota in the provider console.
- **Scout Brain offline:** this is safe and expected unless both the feature flag and OpenRouter key are configured.

Public provider and website text is treated as untrusted data. Human review is mandatory. This V1 does not contact businesses, bypass access controls, run scheduled searches, or automate marketing.
