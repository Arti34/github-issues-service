import os
import httpx

class GitHubError(Exception):
    def __init__(self, status_code: int, message: str, headers=None):
        self.status_code = status_code
        self.message = message
        self.headers = headers or {}
        super().__init__(message)

class GitHubClient:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.owner = os.getenv("GITHUB_OWNER", "")
        self.repo = os.getenv("GITHUB_REPO", "")
        self.base_url = "https://api.github.com"

    def _headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def request(self, method, path, **kwargs):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method, self.base_url + path,
                headers=self._headers(), **kwargs
            )
        if response.status_code >= 400:
            try:
                message = response.json().get("message", response.text)
            except Exception:
                message = response.text
            raise GitHubError(response.status_code, message, dict(response.headers))
        return response

    async def create_issue(self, data):
        return await self.request(
            "POST", f"/repos/{self.owner}/{self.repo}/issues", json=data
        )

    async def list_issues(self, params):
        return await self.request(
            "GET", f"/repos/{self.owner}/{self.repo}/issues", params=params
        )

    async def get_issue(self, number):
        return await self.request(
            "GET", f"/repos/{self.owner}/{self.repo}/issues/{number}"
        )

    async def update_issue(self, number, data):
        return await self.request(
            "PATCH", f"/repos/{self.owner}/{self.repo}/issues/{number}", json=data
        )

    async def create_comment(self, number, data):
        return await self.request(
            "POST", f"/repos/{self.owner}/{self.repo}/issues/{number}/comments",
            json=data
        )

    async def list_comments(self, number, params=None):
        return await self.request(
            "GET", f"/repos/{self.owner}/{self.repo}/issues/{number}/comments",
            params=params or {}
        )
