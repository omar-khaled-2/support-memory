# Ingest Service

Accepts support events, validates the schema, handles global idempotency, stores raw events in PostgreSQL, and publishes them to RabbitMQ.

## Run locally

```bash
docker compose up --build
```

## API

### `POST /api/v1/events`

Accepts a JSON array of events. Returns per-event results with `status`:
- `created`
- `duplicate`
- `conflict`

```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '[{"idempotency_key":"idem-1001","occurred_at":"2026-04-01T09:00:00Z","source":"crm","actor":"system","entity_type":"account","entity_id":"acct_helios_269","related_entity_ids":[],"reliability":"medium","text":"Account created","payload":{"account_name":"Helios Apps"}}]'
```

### `GET /api/v1/events/{event_id}`

Retrieve a stored event.

## Environment variables

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/ingest` |
| `RABBITMQ_URL` | `amqp://guest:guest@rabbitmq:5672/` |
| `APP_HOST` | `0.0.0.0` |
| `APP_PORT` | `8000` |
| `PUBLISH_INTERVAL_SECONDS` | `5.0` |
