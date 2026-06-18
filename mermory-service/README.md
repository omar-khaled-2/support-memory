# Memory Service

Reads events, extracts facts, detects contradictions and ambiguous identities, and builds belief snapshots.

## Tables

- `facts` — extracted attribute/value pairs per entity
- `conflicts` — recorded contradictions for an entity/attribute
- `snapshots` — serialized belief state for an entity at a point in time

## API

- `POST /api/v1/events/process` — process one or more events
- `GET /api/v1/entities/{entity_id}/beliefs` — current beliefs
- `POST /api/v1/entities/{entity_id}/snapshots` — create a new snapshot
- `GET /api/v1/entities/{entity_id}/snapshots` — list snapshots
- `GET /api/v1/facts` — list facts (optional `entity_id`, `status` filters)
- `GET /api/v1/conflicts` — list conflicts (optional `entity_id` filter)
- `GET /api/v1/ambiguities` — detect identity ambiguities

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest --cov=app --cov-report=term-missing tests/
```

## Docker

Built and started via the root `docker-compose.yml`. Uses the `memory` database on the shared Postgres service.
