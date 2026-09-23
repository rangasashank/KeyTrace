"""A tiny private upstream with SQLite-backed notes; only the proxy is exposed."""
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer

DB = "/notes/notes.db"
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            with sqlite3.connect(DB) as db:
                if data["action"] == "notes.create":
                    text = data.get("text", "").strip()
                    if not text:
                        self.send_error(400, "text is required")
                        return
                    cursor = db.execute("INSERT INTO notes(text) VALUES (?)", (text,))
                    result = {"id": cursor.lastrowid, "text": text}
                elif data["action"] == "notes.list":
                    result = [{"id": row[0], "text": row[1]} for row in db.execute("SELECT id, text FROM notes ORDER BY id")]
                else:
                    self.send_error(400)
                    return
            body = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, KeyError):
            self.send_error(400)

if __name__ == "__main__":
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
    HTTPServer(("0.0.0.0", 8082), Handler).serve_forever()
