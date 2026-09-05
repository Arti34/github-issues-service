import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .models import IssueCreate, IssueUpdate, CommentCreate
from .github_client import GitHubClient, GitHubError
from .storage import init_db, save_event, list_events
from .webhook import verify_signature, parse_event

load_dotenv()
client = GitHubClient()

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(
    title="GitHub Issues Gateway",
    version="1.0.0",
    description="A small service wrapping the GitHub REST Issues API."
    " Author: Arti",
    lifespan=lifespan
)

def map_error(exc: GitHubError):
    if exc.status_code == 401:
        return JSONResponse(status_code=401, content={"error":"GitHub authentication failed","detail":exc.message})
    if exc.status_code == 403:
        retry = exc.headers.get("retry-after")
        detail = exc.message + (f" Retry-After: {retry}" if retry else "")
        return JSONResponse(status_code=429 if retry else 403, content={"error":"GitHub access/rate-limit error","detail":detail})
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"error":"Issue or repository not found","detail":exc.message})
    if 400 <= exc.status_code < 500:
        return JSONResponse(status_code=400, content={"error":"GitHub validation error","detail":exc.message})
    return JSONResponse(status_code=503, content={"error":"GitHub service unavailable","detail":exc.message})

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/issues", status_code=201)
async def create_issue(payload: IssueCreate):
    try:
        r = await client.create_issue(payload.model_dump(exclude_none=True))
        data = r.json()
        result = {
            "number": data["number"], "html_url": data["html_url"],
            "state": data["state"], "title": data["title"], "body": data.get("body"),
            "labels": [x["name"] for x in data.get("labels", [])],
            "created_at": data["created_at"], "updated_at": data["updated_at"]
        }
        return JSONResponse(
            status_code=201, content=result,
            headers={"Location": f"/issues/{data['number']}"}
        )
    except GitHubError as e:
        return map_error(e)

@app.get("/issues")
async def list_issues(
    state: str = Query("open", pattern="^(open|closed|all)$"),
    labels: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100)
):
    try:
        params = {"state": state, "page": page, "per_page": per_page}
        if labels:
            params["labels"] = labels
        r = await client.list_issues(params)
        response = JSONResponse(content=[
            {
                "number": x["number"], "title": x["title"],
                "state": x["state"],
                "labels": [l["name"] for l in x.get("labels", [])],
                "html_url": x["html_url"],
                "body": x.get("body"),
                "created_at": x["created_at"],
                "updated_at": x["updated_at"]
            } for x in r.json()
        ])
        if "link" in r.headers:
            response.headers["Link"] = r.headers["link"]
        return response
    except GitHubError as e:
        return map_error(e)

@app.get("/issues/{number}")
async def get_issue(number: int):
    try:
        r = await client.get_issue(number)
        return r.json()
    except GitHubError as e:
        return map_error(e)

@app.patch("/issues/{number}")
async def update_issue(number: int, payload: IssueUpdate):
    data = payload.model_dump(exclude_none=True)
    if "state" in data and data["state"] not in ("open", "closed"):
        return JSONResponse(status_code=400, content={"error":"state must be open or closed"})
    try:
        return (await client.update_issue(number, data)).json()
    except GitHubError as e:
        return map_error(e)

@app.post("/issues/{number}/comments", status_code=201)
async def create_comment(number: int, payload: CommentCreate):
    try:
        data = (await client.create_comment(number, payload.model_dump())).json()
        return JSONResponse(status_code=201, content={
            "id": data["id"], "body": data["body"],
            "user": data["user"], "created_at": data["created_at"],
            "html_url": data["html_url"]
        })
    except GitHubError as e:
        return map_error(e)

@app.post("/webhook", status_code=204)
async def webhook(request: Request):
    body = await request.body()
    secret = os.getenv("WEBHOOK_SECRET", "")
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(secret, body, signature):
        return Response(status_code=401)

    event = request.headers.get("X-GitHub-Event", "")
    delivery = request.headers.get("X-GitHub-Delivery", "")
    if event == "ping":
        return Response(status_code=204)
    if event not in ("issues", "issue_comment"):
        return JSONResponse(status_code=400, content={"error":"unknown GitHub event"})

    try:
        action, issue_number = parse_event(body)
    except Exception:
        return JSONResponse(status_code=400, content={"error":"invalid webhook JSON"})

    if not action:
        return JSONResponse(status_code=400, content={"error":"missing webhook action"})

    save_event(delivery, event, action, issue_number)
    return Response(status_code=204)

@app.get("/events")
async def events(limit: int = Query(50, ge=1, le=100)):
    return list_events(limit)
