# Support Memory

A mono-repo platform that ingests support-related events, builds a scored,
conflict-aware memory graph, and answers natural-language questions for support
reps before customer calls.

## Quick start

```bash
cp .env.example .env
# add your OPENAI_API_KEY to .env
docker compose up -d --build
```

Wait for the stack to become healthy, then seed sample data:

```bash
curl -X POST http://localhost:3000/ingest/api/v1/events \
  -H 'Content-Type: application/json' \
  -d @seed_data.json
```

Open the UI at `http://localhost:3000` and ask:

```text
What should the support rep know before calling Helios?
```

Or use the API directly:

```bash
curl -X POST http://localhost:3000/query/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "What changed since the last context build for Helios?"}'
```

## Repository layout

```
.
├── docker-compose.yml         # local orchestration
├── seed_data.json             # 20-event demo dataset
├── nginx/nginx.conf           # reverse proxy on port 3000
├── .env.example               # required environment variables
├── ingest-service/            # event ingestion + outbox publisher
├── mermory-service/           # event consumer + memory graph + digest
├── query-service/             # question answering API
├── postgres/init.sql          # creates ingest and memory databases
└── frontend/                  # React + shadcn/ui question page
```

## Services

| Service | Port | Path prefix | Responsibility |
|---------|------|-------------|----------------|
| nginx | 3000 | `/` | reverse proxy + static UI |
| ingest | 8000 | `/ingest/` | batch events, idempotency, outbox to RabbitMQ |
| memory | 8001 | `/memory/` | consume events, resolve conflicts, build briefings/digests |
| query | 8002 | `/query/` | entity resolution, LLM answer, digest fallback |
| frontend | 80 (internal) | `/` | single-page question UI |

## Environment variables

See `.env.example`. The most important ones are:

- `OPENAI_API_KEY` – required by memory and query services.
- `OPENAI_MODEL` – defaults to `gpt-5.4-nano`.
- `OPENAI_TEMPERATURE` – defaults to `0`.
- `SOURCE_WEIGHTS` – authority per source type (used for conflict resolution).

## Running tests

### Backend

```bash
cd ingest-service && pytest -q --cov=app
cd mermory-service && pytest -q --cov=app
cd query-service && pytest -q --cov=app
```

### Frontend

```bash
cd frontend
npm install
npm run lint
npm run build
```

## Roadmap

See [`NEXT.md`](./NEXT.md) for planned production improvements including
Kubernetes, Helm, autoscaling, dead-letter queues, observability, and more.

## License

MIT
