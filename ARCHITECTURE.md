# Architecture

## Overview

Support Memory is an event-driven, multi-service application that turns raw
support events into a queryable customer memory. It has three backend services
and one frontend UI, all exposed behind a single nginx reverse proxy.

```
                    ┌─────────────┐
                    │   nginx     │
                    │  port 3000  │
                    └──────┬──────┘
                           │
       ┌──────────┬────────┼────────┬──────────┐
       │          │        │        │          │
   ┌───┴───┐ ┌────┴────┐ ┌─┴─────┐ ┌┴────────┐ │
   │frontend│ │ ingest  │ │memory │ │  query  │ │
   │  SPA   │ │ port 8000│ │port 8001│ │ port 8002│ │
   └───┬───┘ └────┬────┘ └───┬───┘ └────┬────┘ │
       │          │          │          │      │
       │      ┌───┴───┐      │      ┌───┴───┐  │
       │      │  DB   │      │      │ LLM   │  │
       │      │ingest │      │      │(OpenAI)│  │
       │      └───────┘      │      └───────┘  │
       │                     │                 │
       │              ┌──────┴──────┐          │
       │              │  RabbitMQ   │          │
       │              │   outbox    │          │
       │              └──────┬──────┘          │
       │                     │                 │
       │              ┌──────┴──────┐          │
       │              │  memory DB  │          │
       │              └─────────────┘          │
       │                                       │
       └───────────────────────────────────────┘
```

## Ingest service

Responsibilities:
- Accept batches of events via `POST /api/v1/events`.
- Validate and normalize each event.
- Write events to PostgreSQL (`ingest` database).
- Use a RabbitMQ outbox (`EventPublisher`) to publish events asynchronously.
- Enforce idempotency keys globally.

Key files:
- `ingest-service/app/views/event_views.py` — FastAPI routes.
- `ingest-service/app/controllers/event_controller.py` — business logic.
- `ingest-service/app/services/publisher.py` — outbox publisher.

Design choices:
- Per-event results in batch responses; failures do not fail the whole batch.
- Globally unique idempotency keys prevent duplicate ingestion.
- `PUBLISH_INTERVAL_SECONDS` controls outbox polling.

## Memory service

Responsibilities:
- Consume events from RabbitMQ.
- Extract facts and relationships using an LLM (`extractor.py`).
- Build a scored belief graph per entity.
- Resolve conflicts by source authority weights.
- Hide sensitive attributes unless explicitly scoped.
- Provide briefings, snapshots, beliefs, and context-change digests.

Key files:
- `mermory-service/app/services/consumer.py` — RabbitMQ consumer.
- `mermory-service/app/services/extractor.py` — LLM-based extraction.
- `mermory-service/app/controllers/memory_controller.py` — graph logic.
- `mermory-service/app/views/memory_views.py` — FastAPI routes.

Design choices:
- Beliefs are stored with `value`, `confidence`, and `source`.
- `SOURCE_WEIGHTS` gives contract and billing data higher authority than CRM or
  chat.
- Conflicts are tracked but the highest-authority source wins.
- Digests compare the latest two snapshots to show what changed.

## Query service

Responsibilities:
- Accept natural-language questions via `POST /api/v1/query`.
- Resolve which entity the question is about.
- Detect digest-intent questions.
- Fetch context from the memory service.
- Generate an answer with an LLM or a structured fallback.
- Expose raw digest endpoint `GET /entities/{id}/digest`.

Key files:
- `query-service/app/views/query_views.py` — FastAPI routes.
- `query-service/app/controllers/query_controller.py` — orchestration.
- `query-service/app/services/memory_client.py` — HTTP client to memory.
- `query-service/app/services/llm_client.py` — OpenAI client.

Design choices:
- Entity resolution is keyword-based for simplicity.
- Digest questions bypass the LLM and return a formatted diff.
- Fallback answers are deterministic when the LLM is unavailable.

## Frontend

Responsibilities:
- Single-page React app served by nginx.
- Allows the user to ask a question and renders the Markdown answer.

Key files:
- `frontend/src/App.tsx` — main UI.
- `frontend/src/components/ui/*` — shadcn/ui primitives.
- `frontend/nginx/nginx.conf` — SPA static file serving.

## Data flow

1. Client sends events to `/ingest/api/v1/events`.
2. Ingest stores events and publishes them to RabbitMQ via outbox.
3. Memory consumes events, extracts facts, and updates the belief graph.
4. Client asks a question at `/query/api/v1/query`.
5. Query resolves the entity, fetches a briefing/digest from memory, and
   returns an answer.

## Security & privacy

- No authentication is implemented yet.
- Sensitive attributes are redacted in memory responses unless explicitly
  requested.
- Secrets are passed via `.env`, which is gitignored.

## Local deployment

See [`README.md`](./README.md) for instructions.
