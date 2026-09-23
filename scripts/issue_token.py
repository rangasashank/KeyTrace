"""Local admin utility to issue HS256 tokens. No third-party packages needed."""
import base64
import hashlib
import hmac
import json
import time
import sys
from pathlib import Path

def token(actions=None, expires=None):
    env = dict(line.split("=", 1) for line in (Path(__file__).resolve().parents[1] / ".env").read_text().splitlines() if "=" in line)
    def b64(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=")
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"sub": "agent-1", "iss": "keytrace", "aud": "keytrace-proxy", "exp": int(time.time()) + 3600 if expires is None else expires, "actions": ["notes.create", "notes.list"] if actions is None else actions}).encode())
    body = header + b"." + payload
    return (body + b"." + b64(hmac.new(env["TOKEN_SECRET"].encode(), body, hashlib.sha256).digest())).decode()

if __name__ == "__main__":
    print(token(sys.argv[1:] or None))
