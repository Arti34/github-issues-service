import os
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.github_client import GitHubError


client = TestClient(app)


def github_issue(number=1):
    return {
        "number": number,
        "html_url": f"https://github.com/test/repo/issues/{number}",
        "state": "open",
        "title": "Test issue",
        "body": "Test body",
        "labels": [{"name": "bug"}],
        "created_at": "2026-09-05T10:00:00Z",
        "updated_at": "2026-09-05T10:00:00Z",
    }


def github_comment():
    return {
        "id": 123,
        "body": "Test comment",
        "user": {"login": "test-user"},
        "created_at": "2026-09-05T10:00:00Z",
        "html_url": "https://github.com/test/repo/issues/1#issuecomment-123",
    }


def test_healthz():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_request_id_is_preserved():
    response = client.get(
        "/healthz",
        headers={"X-Request-ID": "test-request-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_missing_title():
    response = client.post(
        "/issues",
        json={"body": "Missing title"},
    )

    assert response.status_code == 422


def test_invalid_state():
    response = client.get("/issues?state=invalid")

    assert response.status_code == 422


def test_invalid_page():
    response = client.get("/issues?page=0")

    assert response.status_code == 422


def test_invalid_per_page():
    response = client.get("/issues?per_page=101")

    assert response.status_code == 422


def test_create_issue():
    mock_response = Mock()
    mock_response.json.return_value = github_issue(42)

    with patch.object(
        app.state,
        "dummy",
        create=True,
    ):
        with patch(
            "app.main.client.create_issue",
            new=AsyncMock(return_value=mock_response),
        ) as mock_create:

            response = client.post(
                "/issues",
                json={
                    "title": "Test issue",
                    "body": "Test body",
                    "labels": ["bug"],
                },
            )

    assert response.status_code == 201
    assert response.json()["number"] == 42
    assert response.json()["title"] == "Test issue"
    assert response.headers["Location"] == "/issues/42"

    mock_create.assert_awaited_once()


def test_list_issues_with_pagination():
    mock_response = Mock()
    mock_response.json.return_value = [github_issue(1), github_issue(2)]
    mock_response.headers = {
        "link": '<https://api.github.com/repos/test/repo/issues?page=2>; rel="next"'
    }

    with patch(
        "app.main.client.list_issues",
        new=AsyncMock(return_value=mock_response),
    ) as mock_list:

        response = client.get(
            "/issues?state=all&labels=bug,feature&page=2&per_page=20"
        )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["Link"] == mock_response.headers["link"]

    mock_list.assert_awaited_once_with(
        {
            "state": "all",
            "page": 2,
            "per_page": 20,
            "labels": "bug,feature",
        }
    )


def test_list_issues_without_labels():
    mock_response = Mock()
    mock_response.json.return_value = [github_issue(1)]
    mock_response.headers = {}

    with patch(
        "app.main.client.list_issues",
        new=AsyncMock(return_value=mock_response),
    ) as mock_list:

        response = client.get("/issues")

    assert response.status_code == 200
    assert len(response.json()) == 1

    mock_list.assert_awaited_once_with(
        {
            "state": "open",
            "page": 1,
            "per_page": 30,
        }
    )


def test_get_issue():
    mock_response = Mock()
    mock_response.json.return_value = github_issue(7)

    with patch(
        "app.main.client.get_issue",
        new=AsyncMock(return_value=mock_response),
    ):

        response = client.get("/issues/7")

    assert response.status_code == 200
    assert response.json()["number"] == 7


def test_update_issue():
    mock_response = Mock()
    mock_response.json.return_value = {
        **github_issue(7),
        "title": "Updated title",
        "body": "Updated body",
        "state": "closed",
    }

    with patch(
        "app.main.client.update_issue",
        new=AsyncMock(return_value=mock_response),
    ) as mock_update:

        response = client.patch(
            "/issues/7",
            json={
                "title": "Updated title",
                "body": "Updated body",
                "state": "closed",
            },
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    assert response.json()["state"] == "closed"

    mock_update.assert_awaited_once()


def test_update_invalid_state():
    response = client.patch(
        "/issues/7",
        json={"state": "invalid"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "state must be open or closed"


def test_create_comment():
    mock_response = Mock()
    mock_response.json.return_value = github_comment()

    with patch(
        "app.main.client.create_comment",
        new=AsyncMock(return_value=mock_response),
    ) as mock_comment:

        response = client.post(
            "/issues/7/comments",
            json={"body": "Test comment"},
        )

    assert response.status_code == 201
    assert response.json()["id"] == 123
    assert response.json()["body"] == "Test comment"

    mock_comment.assert_awaited_once()


def test_github_401():
    error = GitHubError(401, "Bad credentials")

    with patch(
        "app.main.client.get_issue",
        new=AsyncMock(side_effect=error),
    ):
        response = client.get("/issues/1")

    assert response.status_code == 401
    assert response.json()["error"] == "GitHub authentication failed"


def test_github_403():
    error = GitHubError(403, "Forbidden")

    with patch(
        "app.main.client.get_issue",
        new=AsyncMock(side_effect=error),
    ):
        response = client.get("/issues/1")

    assert response.status_code == 403
    assert response.json()["error"] == "GitHub access/rate-limit error"


def test_github_rate_limit():
    error = GitHubError(
        403,
        "API rate limit exceeded",
        {"retry-after": "60"},
    )

    with patch(
        "app.main.client.get_issue",
        new=AsyncMock(side_effect=error),
    ):
        response = client.get("/issues/1")

    assert response.status_code == 429
    assert "Retry-After: 60" in response.json()["detail"]


def test_github_404():
    error = GitHubError(404, "Not Found")

    with patch(
        "app.main.client.get_issue",
        new=AsyncMock(side_effect=error),
    ):
        response = client.get("/issues/999")

    assert response.status_code == 404
    assert response.json()["error"] == "Issue or repository not found"


def test_github_500():
    error = GitHubError(500, "GitHub unavailable")

    with patch(
        "app.main.client.get_issue",
        new=AsyncMock(side_effect=error),
    ):
        response = client.get("/issues/1")

    assert response.status_code == 503
    assert response.json()["error"] == "GitHub service unavailable"


def test_webhook_invalid_signature():
    response = client.post(
        "/webhook",
        content=b'{"action":"opened"}',
        headers={
            "X-Hub-Signature-256": "sha256=invalid",
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-1",
        },
    )

    assert response.status_code == 401


def test_webhook_ping():
    with patch(
        "app.main.verify_signature",
        return_value=True,
    ):
        response = client.post(
            "/webhook",
            content=b'{"zen":"Keep it logically awesome."}',
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "ping",
                "X-GitHub-Delivery": "delivery-ping",
            },
        )

    assert response.status_code == 204


def test_webhook_unknown_event():
    with patch(
        "app.main.verify_signature",
        return_value=True,
    ):
        response = client.post(
            "/webhook",
            content=b'{"action":"opened"}',
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "delivery-2",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"] == "unknown GitHub event"


def test_webhook_invalid_json():
    with patch(
        "app.main.verify_signature",
        return_value=True,
    ):
        response = client.post(
            "/webhook",
            content=b"not-json",
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "delivery-3",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid webhook JSON"


def test_webhook_missing_action():
    with patch(
        "app.main.verify_signature",
        return_value=True,
    ):
        response = client.post(
            "/webhook",
            json={
                "issue": {
                    "number": 10
                }
            },
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "delivery-4",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"] == "missing webhook action"


def test_webhook_issues_event():
    with patch(
        "app.main.verify_signature",
        return_value=True,
    ), patch(
        "app.main.save_event"
    ) as mock_save:

        response = client.post(
            "/webhook",
            json={
                "action": "opened",
                "issue": {
                    "number": 42
                },
            },
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issues",
                "X-GitHub-Delivery": "delivery-5",
            },
        )

    assert response.status_code == 204

    mock_save.assert_called_once_with(
        "delivery-5",
        "issues",
        "opened",
        42,
    )


def test_webhook_issue_comment_event():
    with patch(
        "app.main.verify_signature",
        return_value=True,
    ), patch(
        "app.main.save_event"
    ) as mock_save:

        response = client.post(
            "/webhook",
            json={
                "action": "created",
                "issue": {
                    "number": 43
                },
                "comment": {
                    "id": 123
                },
            },
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issue_comment",
                "X-GitHub-Delivery": "delivery-6",
            },
        )

    assert response.status_code == 204

    mock_save.assert_called_once_with(
        "delivery-6",
        "issue_comment",
        "created",
        43,
    )


def test_events_endpoint():
    mock_events = [
        {
            "id": "delivery-10",
            "event": "issues",
            "action": "opened",
            "issue_number": 10,
            "timestamp": "2026-09-05T10:00:00+00:00",
        }
    ]

    with patch(
        "app.main.list_events",
        return_value=mock_events,
    ) as mock_list:

        response = client.get("/events?limit=10")

    assert response.status_code == 200
    assert response.json() == mock_events

    mock_list.assert_called_once_with(10)


def test_generic_github_client_error():
    error = GitHubError(422, "Validation failed")

    with patch(
        "app.main.client.get_issue",
        new=AsyncMock(side_effect=error),
    ):
        response = client.get("/issues/1")

    assert response.status_code == 400
    assert response.json()["error"] == "GitHub validation error"