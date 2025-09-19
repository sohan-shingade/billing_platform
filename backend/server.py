"""A minimal HTTP server implementing a usage‑based billing API.

This server is built entirely with Python's standard library so it can run
without any third‑party dependencies. It stores data in a SQLite database and
exposes endpoints for ingesting usage events, retrieving aggregated usage,
listing invoices and generating invoices. The API adheres to a simple JSON
contract similar to the one described in the project overview.

Endpoints
---------
POST /v1/customers
    Create a new customer. Body should contain JSON with `name` and `email`.
    Returns the created customer with ID.

POST /v1/events/batch
    Ingest a batch of usage events. Body should be a JSON array of event
    objects with fields: `customer_id`, `feature`, `quantity` (optional) and
    `ts_event` (ISO 8601 string). Returns the number of events inserted.

GET /v1/customers/<id>/usage?start=<iso>&end=<iso>
    Retrieve usage aggregated by feature for a customer over a time interval.

GET /v1/customers/<id>/invoices
    List all invoices for a customer, including line items.

POST /v1/invoices/run?period=YYYY-MM&unit_price=0.01
    Generate invoices for all customers for the given period. The period is
    inclusive of the month specified and exclusive of the next month. Returns
    the number of invoices generated.

The server stores timestamps as ISO 8601 strings in the database. Incoming
timestamps are parsed using `datetime.fromisoformat`. Error handling is
rudimentary; malformed requests result in a 400 response with a simple
message.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

DEFAULT_DB = BASE_DIR / "data" / "billing.db"
DB_PATH = os.getenv("BILLING_DB", str(DEFAULT_DB))
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def init_db():
    """Initialize the SQLite database with the required tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Enable foreign key support
    c.execute("PRAGMA foreign_keys=ON;")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            timezone TEXT
        );
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            feature TEXT NOT NULL,
            quantity REAL NOT NULL,
            ts_event TEXT NOT NULL,
            ts_ingested TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            total REAL NOT NULL,
            generated_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS invoice_line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            feature TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id)
        );
        """
    )
    conn.commit()
    conn.close()


def create_customer(name: str, email: str, timezone: str = "UTC") -> dict:
    """Insert a new customer into the database and return its record."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO customers (name, email, timezone) VALUES (?, ?, ?)",
            (name, email, timezone),
        )
        conn.commit()
        customer_id = c.lastrowid
    finally:
        conn.close()
    return {"id": customer_id, "name": name, "email": email, "timezone": timezone}


def insert_events(events: list[dict]) -> int:
    """Insert a batch of events and return the number inserted."""
    now_iso = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys=ON;")
    count = 0
    try:
        for event in events:
            # Validate required fields
            if not all(k in event for k in ("customer_id", "feature", "ts_event")):
                raise ValueError("Each event must include customer_id, feature and ts_event")
            quantity = float(event.get("quantity", 1.0))
            # Parse ts_event; allow fractional seconds
            ts_event = datetime.fromisoformat(event["ts_event"]).isoformat()
            c.execute(
                "INSERT INTO events (customer_id, feature, quantity, ts_event, ts_ingested) VALUES (?, ?, ?, ?, ?)",
                (event["customer_id"], event["feature"], quantity, ts_event, now_iso),
            )
            count += 1
        conn.commit()
    finally:
        conn.close()
    return count


def get_usage(customer_id: int, start: str, end: str) -> list[dict]:
    """Return usage aggregated by feature for a customer within a time interval."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT feature, SUM(quantity) as quantity
        FROM events
        WHERE customer_id = ? AND ts_event >= ? AND ts_event < ?
        GROUP BY feature
        """,
        (customer_id, start, end),
    )
    rows = c.fetchall()
    conn.close()
    return [
        {"feature": row[0], "quantity": row[1]}
        for row in rows
    ]


def list_invoices(customer_id: int) -> list[dict]:
    """Retrieve invoices and their line items for a customer."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, period_start, period_end, total, generated_at FROM invoices WHERE customer_id = ? ORDER BY generated_at DESC",
        (customer_id,),
    )
    invoices = []
    for inv_row in c.fetchall():
        invoice_id, p_start, p_end, total, generated_at = inv_row
        c.execute(
            "SELECT feature, quantity, unit_price, amount FROM invoice_line_items WHERE invoice_id = ?",
            (invoice_id,),
        )
        items = [
            {
                "feature": it[0],
                "quantity": it[1],
                "unit_price": it[2],
                "amount": it[3],
            }
            for it in c.fetchall()
        ]
        invoices.append(
            {
                "id": invoice_id,
                "period_start": p_start,
                "period_end": p_end,
                "total": total,
                "generated_at": generated_at,
                "line_items": items,
            }
        )
    conn.close()
    return invoices


def generate_invoices(period: str, unit_price: float = 0.01) -> int:
    """Generate invoices for all customers for the given month.

    Parameters
    ----------
    period : str
        The billing period in 'YYYY-MM' format.
    unit_price : float
        The price per unit of usage.

    Returns
    -------
    int
        The number of invoices generated.
    """
    # Compute period start and end
    try:
        period_start_dt = datetime.strptime(period, "%Y-%m")
    except ValueError:
        raise ValueError("period must be in YYYY-MM format")
    if period_start_dt.month == 12:
        period_end_dt = period_start_dt.replace(year=period_start_dt.year + 1, month=1)
    else:
        period_end_dt = period_start_dt.replace(month=period_start_dt.month + 1)
    period_start = period_start_dt.isoformat()
    period_end = period_end_dt.isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys=ON;")
    # Find customers with events in the period
    c.execute(
        "SELECT DISTINCT customer_id FROM events WHERE ts_event >= ? AND ts_event < ?",
        (period_start, period_end),
    )
    customers = [row[0] for row in c.fetchall()]
    now_iso = datetime.utcnow().isoformat()
    invoice_count = 0
    try:
        for cid in customers:
            # Compute usage per feature
            usage = get_usage(cid, period_start, period_end)
            if not usage:
                continue
            # Remove existing invoice for this period if exists
            c.execute(
                "DELETE FROM invoices WHERE customer_id = ? AND period_start = ?",
                (cid, period_start),
            )
            conn.commit()
            # Insert invoice
            c.execute(
                "INSERT INTO invoices (customer_id, period_start, period_end, total, generated_at) VALUES (?, ?, ?, 0.0, ?)",
                (cid, period_start, period_end, now_iso),
            )
            invoice_id = c.lastrowid
            total = 0.0
            # Insert line items
            for item in usage:
                qty = float(item["quantity"])
                amount = qty * unit_price
                c.execute(
                    "INSERT INTO invoice_line_items (invoice_id, feature, quantity, unit_price, amount) VALUES (?, ?, ?, ?, ?)",
                    (invoice_id, item["feature"], qty, unit_price, amount),
                )
                total += amount
            # Update invoice total
            c.execute(
                "UPDATE invoices SET total = ? WHERE id = ?",
                (total, invoice_id),
            )
            conn.commit()
            invoice_count += 1
    finally:
        conn.close()
    return invoice_count


class BillingRequestHandler(BaseHTTPRequestHandler):
    """Request handler implementing the billing API and serving static assets."""

    def _send_json(self, obj: dict, status: int = 200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body")

    def do_POST(self):
        parsed = urlparse(self.path)
        path_parts = parsed.path.rstrip("/").split("/")

        try:
            if parsed.path == "/v1/customers":
                # Create customer
                data = self._read_json_body() or {}
                name = data.get("name")
                email = data.get("email")
                timezone = data.get("timezone", "UTC")
                if not name or not email:
                    raise ValueError("name and email are required")
                customer = create_customer(name, email, timezone)
                self._send_json(customer, status=201)
            elif parsed.path == "/v1/events/batch":
                events = self._read_json_body() or []
                if not isinstance(events, list):
                    raise ValueError("Request body must be an array of events")
                inserted = insert_events(events)
                self._send_json({"inserted": inserted}, status=201)
            elif parsed.path == "/v1/invoices/run":
                query = parse_qs(parsed.query)
                period_list = query.get("period")
                unit_price_list = query.get("unit_price")
                if not period_list:
                    raise ValueError("period parameter is required")
                period = period_list[0]
                unit_price = float(unit_price_list[0]) if unit_price_list else 0.01
                count = generate_invoices(period, unit_price)
                self._send_json({"invoices_generated": count}, status=201)
            else:
                self.send_error(404, "Not Found")
        except ValueError as err:
            self._send_json({"error": str(err)}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def do_GET(self):
        parsed = urlparse(self.path)
        path_parts = parsed.path.rstrip("/").split("/")
        # Expect path_parts like ['', 'v1', 'customers', '{id}', 'usage']
        try:
            # Serve static files when the path doesn't match the API prefix
            if not parsed.path.startswith("/v1/"):
                self.serve_static(parsed.path)
                return

            if len(path_parts) >= 5 and path_parts[1] == "v1" and path_parts[2] == "customers":
                customer_id = int(path_parts[3])
                if path_parts[4] == "usage":
                    # Query parameters start, end
                    query = parse_qs(parsed.query)
                    start = query.get("start", [None])[0]
                    end = query.get("end", [None])[0]
                    if not start or not end:
                        raise ValueError("start and end query parameters are required")
                    # Validate ISO format
                    datetime.fromisoformat(start)
                    datetime.fromisoformat(end)
                    usage = get_usage(customer_id, start, end)
                    self._send_json(usage)
                    return
                elif path_parts[4] == "invoices":
                    invoices = list_invoices(customer_id)
                    self._send_json(invoices)
                    return
            # If we reach here, the path was not recognized
            self.send_error(404, "Not Found")
        except ValueError as err:
            self._send_json({"error": str(err)}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def serve_static(self, path: str):
        """Serve files from the frontend directory. Defaults to index.html."""
        from pathlib import Path

        # Determine file to serve
        if path in ("", "/", "/index.html"):
            filename = "index.html"
        else:
            # Remove leading slash
            filename = path.lstrip("/")
        # Only allow serving specific files
        allowed = {"index.html", "main.js"}
        if filename not in allowed:
            self.send_error(404, "Not Found")
            return
        base_dir = Path(__file__).resolve().parent.parent / "frontend"
        file_path = base_dir / filename
        if not file_path.exists():
            self.send_error(404, "Not Found")
            return
        # Determine content type
        if filename.endswith(".html"):
            content_type = "text/html"
        elif filename.endswith(".js"):
            content_type = "application/javascript"
        else:
            content_type = "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_server(host=None, port=None):
    """
    Start the HTTP server in the current thread.
    Blocks indefinitely (use a separate thread if you need concurrency).
    Honors HOST/PORT env vars (PORT is required on most PaaS).
    """
    import os, signal, sys
    from http.server import HTTPServer
    from pathlib import Path

    # Defaults + PaaS overrides
    host = host or os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", port or 8000))

    # Make sure the DB directory exists (SQLite won't create parent dirs)
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Init schema and start server
    init_db()
    server = HTTPServer((host, port), BillingRequestHandler)

    # Graceful shutdown for Docker/Render/etc.
    def _graceful_shutdown(signum, frame):
        try:
            server.shutdown()
        finally:
            server.server_close()
            sys.exit(0)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    print(f"Billing server listening on {host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def start_background_server(host: str = "0.0.0.0", port: int = 8000) -> threading.Thread:
    """Start the server in a background thread and return the thread object."""
    thread = threading.Thread(target=run_server, args=(host, port), daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    run_server()