import json
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from issue_token import token

def request(credential, action, text=""):
    req = Request("http://localhost:8080/actions", data=json.dumps({"action": action, "text": text}).encode(), headers={"Authorization": "Bearer " + credential, "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=15) as res:
            return res.status, json.load(res), res.headers.get("X-KeyTrace-Event")
    except HTTPError as error:
        return error.code, error.read().decode(), error.headers.get("X-KeyTrace-Event")

for attempt in range(90):
    try:
        with urlopen("http://localhost:8080/health", timeout=2):
            break
    except (URLError, TimeoutError):
        time.sleep(2)
else:
    raise SystemExit("Proxy did not become ready")

ids = []
for credential, action, text, expected in [
    (token(), "notes.create", "Hello from KeyTrace", 200),
    (token(), "notes.list", "", 200),
    (token(["notes.list"]), "notes.create", "must not be saved", 403),
    (token(), "shell.execute", "", 403),
    (token(expires=1), "notes.list", "", 401),
    ("invalid", "notes.list", "", 401),
]:
    status, body, event = request(credential, action, text)
    assert status == expected, (status, body, expected)
    assert event
    ids.append(event)
    if action == "notes.list" and status == 200:
        assert any(row["text"] == "Hello from KeyTrace" for row in body)
    print(f"PASS {action}: {status}")
status, notes, _ = request(token(), "notes.list")
assert status == 200 and not any(row["text"] == "must not be saved" for row in notes)
sql = "SELECT count(DISTINCT event_id) AS verified_events FROM audit WHERE event_id IN (" + ",".join("'" + value + "'" for value in ids) + ")"
for attempt in range(30):
    result = subprocess.run(["docker", "compose", "exec", "-T", "audit", "python", "query.py", sql], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip().split()[-1] == str(len(ids)):
        print("PASS all six decisions persisted in Iceberg/Parquet and queried with SQL")
        break
    time.sleep(2)
else:
    raise AssertionError(f"Audit ingestion failed: {result.stdout} {result.stderr}")
