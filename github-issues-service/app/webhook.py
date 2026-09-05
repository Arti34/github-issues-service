import hashlib
import hmac
import json

def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def parse_event(body: bytes):
    payload = json.loads(body)
    issue = payload.get("issue") or {}
    return payload.get("action"), issue.get("number")
