# Next steps

This document tracks planned production improvements for Support Memory.

## Infrastructure

### Kubernetes deployment
- Write `k8s/` manifests for all services.
- Split databases: one Postgres cluster with two logical databases, or
  dedicated instances per service.
- Add ConfigMaps for `SOURCE_WEIGHTS`, model names, and intervals.
- Add Secrets for `OPENAI_API_KEY` and database credentials.

### Helm chart
- Create a `helm/support-memory` chart.
- Parameterize replicas, resources, image tags, and feature flags.
- Support environment-specific `values.yaml` (local, staging, prod).

### Autoscaling
- Add HorizontalPodAutoscaler for ingest, memory, query, and frontend.
- Scale based on CPU/memory and custom metrics (queue depth, request latency).
- Consider KEDA for RabbitMQ consumer scaling.

## Messaging

### Dead-letter queue
- Configure a RabbitMQ DLX for events that fail processing after N retries.
- Add a DLQ inspection/replay endpoint in the memory service.
- Alert when DLQ depth grows.

### Exactly-once publishing
- Switch ingest outbox to a proper transactional outbox with idempotent
  consumers.
- Add event-level deduplication in memory service.

### Alternative message brokers
- Evaluate Kafka or NATS JetStream for higher throughput and replayability.

## Observability

### Metrics
- Export Prometheus metrics from all Python services.
- Track ingestion rate, queue depth, consumer lag, conflict rate, LLM latency,
  query latency, and error rate.
- Add service-level SLOs.

### Logs
- Centralize logs with Grafana Loki.
- Add structured JSON logging and correlation IDs.

### Tracing
- Add OpenTelemetry traces across ingest → RabbitMQ → memory → query.

### Dashboards and alerts
- Grafana dashboard for system health, business metrics, and LLM cost.
- PagerDuty/Slack alerts for high error rates, DLQ growth, and DB lag.

## Reliability

### Circuit breakers and retries
- Add circuit breakers around LLM calls and inter-service HTTP requests.
- Implement exponential backoff for external APIs.

### Database
- Add read replicas for memory/query read load.
- Implement connection pooling with PgBouncer.
- Add backups and point-in-time recovery.

### Rate limiting
- Add per-tenant rate limits on ingest and query APIs.

## Security

### Authentication and authorization
- Add API keys or OAuth2 for service-to-service calls.
- Role-based access for sensitive attributes.

### PII handling
- Detect and mask PII before storage.
- Add audit logging for access to sensitive data.

### Secrets management
- Move secrets to Vault, AWS Secrets Manager, or Kubernetes external-secrets.

## Features

### Better entity resolution
- Replace keyword matching with an embedding-based or LLM-based resolver.

### Multi-turn conversations
- Store conversation history and allow follow-up questions.

### Feedback loop
- Let support reps thumbs-up/down answers and feed corrections back into
  memory.

### Streaming answers
- Stream LLM responses to the frontend for lower perceived latency.

### Admin UI
- Add a page to inspect events, conflicts, snapshots, and digests.

## Testing

- Add contract tests between services.
- Add load tests for ingest and query endpoints.
- Add chaos engineering exercises (kill pods, partition networks).

## CI/CD

- GitHub Actions pipeline for lint, test, build, and push images.
- Automated Helm releases.
- Staging environment that runs integration tests on every PR.
