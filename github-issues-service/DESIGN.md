# Design Note — GitHub Issues Gateway

## Architecture

FastAPI provides the public API. A dedicated GitHubClient isolates third-party HTTP calls. SQLite stores webhook delivery metadata for debugging and idempotency.

## Error mapping

GitHub 401 becomes 401. GitHub 404 becomes 404. Client validation errors become 400. GitHub 403/rate-limit responses are surfaced as 403 or 429 when Retry-After is available. Unexpected upstream failures become 503.

## Pagination

The gateway accepts `page` and `per_page` and forwards them to GitHub. GitHub's `Link` header is returned to the caller so clients can preserve GitHub pagination semantics.

## Webhook security

The receiver validates `X-Hub-Signature-256` with HMAC-SHA256 over the raw request body. `hmac.compare_digest` provides constant-time comparison. Secrets and signatures are never logged.

## Idempotency

`X-GitHub-Delivery` is used as the unique delivery key in SQLite. A repeated delivery is therefore safe to process without creating a second event record.

## Reliability

Webhook processing is deliberately small: validate, parse, persist, acknowledge. Long-running work should be moved to a queue in a production deployment.

## Security trade-offs

The service keeps the GitHub token server-side and reads it from environment variables. The recommended token is a fine-grained PAT limited to the test repository with Issues read/write permission.
