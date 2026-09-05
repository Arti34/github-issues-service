import hashlib, hmac, json
from app.webhook import verify_signature, parse_event

def test_valid_signature():
    secret = "secret"
    body = b'{"action":"opened"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, body, sig)

def test_invalid_signature():
    assert not verify_signature("secret", b"body", "sha256=bad")

def test_tampered_body():
    secret = "secret"
    body = b"original"
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert not verify_signature(secret, b"tampered", sig)

def test_parse_event():
    action, number = parse_event(json.dumps({
        "action":"opened", "issue":{"number":123}
    }).encode())
    assert action == "opened"
    assert number == 123
