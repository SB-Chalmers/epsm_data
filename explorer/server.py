"""Local HTTP app with a read-only catalogue and a separate SQLite remarks store."""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .catalogue import load_data

ROOT = Path(__file__).resolve().parent
DEFAULT_NOTES = ROOT.parent / "data" / "local" / "explorer-notes.sqlite"
MAX_BODY = 100_000


class Conflict(ValueError):
    """The submitted revision is older than the saved remark."""


class NotesStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY, cell_id TEXT NOT NULL, body TEXT NOT NULL,
                author TEXT NOT NULL, kind TEXT NOT NULL, package_id TEXT NOT NULL,
                revision TEXT NOT NULL, release_id TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def all(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM notes ORDER BY created_at, id")]

    def save(self, payload, note_id=None):
        now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        fields = ("cell_id", "body", "author", "kind", "package_id", "revision", "release_id")
        with self.connect() as db:
            if note_id:
                original = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
                if original is None:
                    raise KeyError("Remark not found")
                if any(
                    payload[key] != original[key]
                    for key in ("cell_id", "package_id", "revision", "release_id")
                ):
                    raise ValueError("A remark cannot be moved to a different review context")
                result = db.execute(
                    """UPDATE notes SET body=?,author=?,kind=?,updated_at=?
                       WHERE id=? AND updated_at=?""",
                    (
                        payload["body"],
                        payload["author"],
                        payload["kind"],
                        now,
                        note_id,
                        payload.get("updated_at"),
                    ),
                )
                if result.rowcount != 1:
                    raise Conflict(
                        "This remark changed in another window. Copy your draft, "
                        "then reload to see the latest version."
                    )
            else:
                note_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (note_id, *(payload[key] for key in fields), now, now),
                )
            return dict(db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone())

    def delete(self, note_id, version):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM notes WHERE id=?", (note_id,)).fetchone():
                raise KeyError("Remark not found")
            result = db.execute("DELETE FROM notes WHERE id=? AND updated_at=?", (note_id, version))
            if result.rowcount != 1:
                raise Conflict("This remark changed in another window. Reload before deleting.")


def validate_note(payload, catalogue, *, existing=False):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    for field, maximum in [
        ("body", 20_000),
        ("author", 100),
        ("kind", 20),
        ("cell_id", 300),
        ("package_id", 500),
        ("revision", 200),
        ("release_id", 200),
    ]:
        value = payload.get(field, "" if field == "author" else None)
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError(f"Invalid {field}; maximum {maximum} characters")
        payload[field] = value.strip()
    if not payload["body"]:
        raise ValueError("Write a remark before saving")
    if payload["kind"] not in {"remark", "question", "issue"}:
        raise ValueError("Unknown remark type")
    # Existing notes may refer to older releases. The store enforces immutable context.
    if existing:
        return payload
    cell = next((c for c in catalogue["cells"] if c["id"] == payload["cell_id"]), None)
    if cell is None:
        raise ValueError("Unknown archetype cell")
    candidates = [(cell["package_id"], cell["revision"])] + [
        (c["id"], c["revision"]) for c in cell["alternatives"]
    ]
    if (payload["package_id"], payload["revision"]) not in candidates:
        raise ValueError("Package is not assigned to this archetype cell")
    if payload["release_id"] != catalogue["manifest"]["release_id"]:
        raise ValueError("Catalogue release changed. Reload before saving")
    return payload


def make_server(*, port=8765, notes_path=DEFAULT_NOTES, catalogue_path=None):
    bundled = ROOT.parent / "src" / "epsm_data" / "datasets" / "parametric" / "catalogue.json"
    if Path(notes_path).resolve() == Path(catalogue_path or bundled).resolve():
        raise ValueError("The notes database must be separate from the catalogue")
    catalogue = load_data(catalogue_path)
    catalogue_bytes = json.dumps(catalogue, ensure_ascii=False, allow_nan=False).encode()
    catalogue_gzip = gzip.compress(catalogue_bytes, compresslevel=5)
    store = NotesStore(notes_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "EPSMExplorer/1"

        def send(
            self, status, body, content_type="application/json; charset=utf-8", *, compressed=False
        ):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if compressed:
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
                "form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(body)

        def trusted_request(self, *, write=False):
            expected = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            host = self.headers.get("Host", "")
            if host not in expected:
                self.send(403, {"error": "Use the localhost explorer address"})
                return False
            if write:
                origin = self.headers.get("Origin")
                if origin is not None and origin not in {f"http://{h}" for h in expected}:
                    self.send(403, {"error": "Cross-origin writes are not allowed"})
                    return False
                if self.headers.get("Sec-Fetch-Site") == "cross-site":
                    self.send(403, {"error": "Cross-origin writes are not allowed"})
                    return False
                if self.headers.get_content_type() != "application/json":
                    self.send(415, {"error": "Use application/json"})
                    return False
            return True

        def do_GET(self):
            if not self.trusted_request():
                return
            path = urlsplit(self.path).path
            try:
                if path == "/api/catalogue":
                    if "gzip" in self.headers.get("Accept-Encoding", ""):
                        return self.send(200, catalogue_gzip, compressed=True)
                    return self.send(200, catalogue_bytes)
                if path == "/api/notes":
                    return self.send(200, store.all())
                static = {
                    "/": ("index.html", "text/html; charset=utf-8"),
                    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                    "/style.css": ("style.css", "text/css; charset=utf-8"),
                }
                if path in static:
                    filename, mime = static[path]
                    return self.send(200, (ROOT / "static" / filename).read_bytes(), mime)
                self.send(404, {"error": "Not found"})
            except (OSError, sqlite3.Error):
                self.log_error("Failed to read explorer data")
                self.send(503, {"error": "Storage is unavailable. Please retry."})

        def mutate(self, method):
            if not self.trusted_request(write=True):
                return
            path = urlsplit(self.path).path
            note_id = path.removeprefix("/api/notes/")
            if (method == "POST" and path != "/api/notes") or (
                method != "POST"
                and (not path.startswith("/api/notes/") or "/" in note_id or not note_id)
            ):
                return self.send(404, {"error": "Not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    return self.send(413, {"error": "Invalid or oversized request"})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Expected a JSON object")
                if method == "DELETE":
                    store.delete(note_id, payload.get("updated_at"))
                    return self.send(200, {"deleted": note_id})
                payload = validate_note(payload, catalogue, existing=method == "PUT")
                note = store.save(payload, note_id if method == "PUT" else None)
                self.send(200 if method == "PUT" else 201, note)
            except Conflict as error:
                self.send(409, {"error": str(error)})
            except KeyError:
                self.send(404, {"error": "Remark not found"})
            except (ValueError, UnicodeError) as error:
                self.send(400, {"error": str(error)})
            except (OSError, sqlite3.Error):
                self.log_error("Failed to write explorer remarks")
                self.send(
                    503,
                    {"error": "Could not save the remark. Your draft is still here; please retry."},
                )

        def do_POST(self):
            self.mutate("POST")

        def do_PUT(self):
            self.mutate("PUT")

        def do_DELETE(self):
            self.mutate("DELETE")

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--notes", type=Path, default=DEFAULT_NOTES)
    parser.add_argument("--catalogue", type=Path, help="Optional parametric JSON catalogue")
    args = parser.parse_args()
    server = make_server(port=args.port, notes_path=args.notes, catalogue_path=args.catalogue)
    print(f"Explorer: http://127.0.0.1:{server.server_port}", flush=True)
    print(f"Remarks: {args.notes.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
