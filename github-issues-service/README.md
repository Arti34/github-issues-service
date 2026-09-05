# GitHub Issues Gateway

Author: Arti

A FastAPI service that wraps GitHub REST Issues API and receives/verifies GitHub webhooks.

## Features

- Issue create/list/get/update/close/reopen
- Issue comments
- GitHub webhook HMAC SHA-256 verification
- Webhook delivery deduplication using delivery ID
- SQLite event persistence
- Pagination and GitHub Link header forwarding
- GitHub error mapping
- Health endpoint
- OpenAPI 3.1 contract
- Unit tests
- Docker support

## Setup

Create `.env` from `.env.example`:

```env
GITHUB_TOKEN=...
GITHUB_OWNER=...
GITHUB_REPO=...
WEBHOOK_SECRET=...
PORT=8000
```

Never commit `.env`.

## Local run

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## Docker

```bash
docker build -t github-issues-service .
docker run --env-file .env -p 8000:8000 github-issues-service
```

## API examples

Create:
```bash
curl -X POST http://localhost:8000/issues \
  -H "Content-Type: application/json" \
  -d '{"title":"Test issue","body":"Created through gateway","labels":["bug"]}'
```

List:
```bash
curl "http://localhost:8000/issues?state=open&per_page=10"
```

Get:
```bash
curl http://localhost:8000/issues/1
```

Update/close:
```bash
curl -X PATCH http://localhost:8000/issues/1 \
  -H "Content-Type: application/json" \
  -d '{"title":"Updated title","state":"closed"}'
```

Comment:
```bash
curl -X POST http://localhost:8000/issues/1/comments \
  -H "Content-Type: application/json" \
  -d '{"body":"Comment from gateway"}'
```

Events:
```bash
curl http://localhost:8000/events
```

Health:
```bash
curl http://localhost:8000/healthz
```

## Webhook

In the GitHub repository:
Settings → Webhooks → Add webhook.

Payload URL:
`https://YOUR_PUBLIC_URL/webhook`

Content type:
`application/json`

Secret:
same value as `WEBHOOK_SECRET`

Select individual events:
- Issues
- Issue comments

GitHub's Ping event can also be accepted.

For local development use a public tunnel such as ngrok or Cloudflare Tunnel.

## Testing

```bash
pytest -q
pytest --cov=app --cov-report=term-missing
```

## Design

See DESIGN.md.
