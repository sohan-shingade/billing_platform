# Usage-Based Billing Platform (Demo)

A self-contained, end-to-end platform that simulates **usage-based billing** for a SaaS product (Metronome-style). It ingests usage events, aggregates them by customer/feature, rates them, and generates invoices you can view from a simple web dashboard.

---

## What it does

- **Ingests usage events** (e.g., `api_calls: 10`, `storage: 1`).
- **Aggregates usage** over a time window (by customer & feature).
- **Rates & invoices** usage for a billing period (e.g., `2025-09`) at a unit price.
- **Serves a dashboard** to:
  - Create a customer
  - Ingest events
  - View usage rollups
  - Run billing
  - List invoices

All data is stored in a local **SQLite** database file (no external services required).

---

## Tech at a glance

- **Python standard library:** `http.server`, `sqlite3`, `json`, `urllib`
- **Database:** SQLite (single file on disk)
- **Frontend:** TypeScript (compiled to plain JS), vanilla HTML/CSS
- **Build:** `tsc` compiles `frontend/main.ts` → `frontend/main.js`
- **OS/Runtime:** macOS/Linux, Python 3.9+ recommended

---

## Architecture (high level)

```
 Browser (Dashboard)
        │   fetch JSON
        ▼
  Python HTTP Server ───► SQLite DB file
  - Serves UI                 (customers, events,
  - API endpoints              usage rollups, invoices)
  - Billing logic
```

---

## Repository layout

```
billing_platform/
├── backend/
│   ├── server.py        # HTTP server, API routes, DB init, static file serving
│   ├── test_demo.py     # Scripted end-to-end demo (boots server, drives API)
│   └── data/            # Created at runtime; holds SQLite DB (billing.db)
└── frontend/
    ├── index.html       # Dashboard UI
    ├── main.ts          # TS source: form handlers + API calls
    ├── main.js          # Compiled JS (what the browser runs)
    └── tsconfig.json    # TS compiler options (browser-only)
```

> The exact SQLite path is defined by `DB_PATH` inside `backend/server.py`. Ensure the **parent folder exists** (SQLite won’t create directories for you).

---

## Quick start

1) **Open a terminal in the project root**
```bash
cd /path/to/billing_platform
```

2) **Ensure the DB parent folder exists**  
If your `DB_PATH` is `backend/data/billing.db`:
```bash
mkdir -p backend/data
```
If `DB_PATH` is something else (e.g., `billing_platform/backend/billing.db`), create that parent directory instead.

3) **Run the server** (blocks and prints a “listening” line)
```bash
python3 backend/server.py
```
You should see:
```
Billing server listening on 0.0.0.0:8000
```

4) **Open the dashboard**
```
http://127.0.0.1:8000
```

5) **Try the flow**
- Create a customer
- Ingest a few events
- Fetch usage for a date range
- Run billing for a month (e.g., `2025-09`, unit price `0.01`)
- List invoices

> Re-running with the **same email** will hit a `UNIQUE` constraint. Use a new email or reset the DB file (see below).

---

## API overview (MVP)

- `POST /v1/customers`  
  Create a customer. Body:
  ```json
  {"name": "Acme Corp", "email": "contact@acme.com"}
  ```

- `POST /v1/events/batch`  
  Ingest events. Body:
  ```json
  {
    "customer_id": 1,
    "events": [
      {"feature": "api_calls", "quantity": 10, "ts": "2025-09-16T21:05:00Z"},
      {"feature": "storage",   "quantity": 1,  "ts": "2025-09-16T21:05:00Z"}
    ]
  }
  ```

- `GET /v1/customers/{id}/usage?start=ISO&end=ISO`  
  Returns:
  ```json
  [
    {"feature":"api_calls","quantity":10.0},
    {"feature":"storage","quantity":1.0}
  ]
  ```

- `POST /v1/invoices/run?period=YYYY-MM&unit_price=0.01`  
  Generates invoices for that month for all customers. Returns:
  ```json
  {"invoices_generated": 1}
  ```

- `GET /v1/customers/{id}/invoices`  
  Returns invoice headers with line items.

---

## Data model (simplified)

- **customers:** `id`, `name`, `email (UNIQUE)`, `timezone`  
- **events:** `id`, `customer_id`, `feature`, `quantity`, `ts`  
- **invoices:** `id`, `customer_id`, `period_start`, `period_end`, `total`, `generated_at`  
- **invoice_line_items:** `id`, `invoice_id`, `feature`, `quantity`, `unit_price`, `amount`

---

## Scripted demo (no clicking)

Run the end-to-end demo:
```bash
python3 backend/test_demo.py
```
It:
- Starts the server in a thread
- Creates a customer
- Posts events
- Fetches usage
- Runs billing
- Lists invoices

If you’ve run it before and get `UNIQUE constraint failed: customers.email`, either change the email in the script or reset the DB (below).

---

## Resetting the database

Delete the SQLite file and start fresh:
```bash
rm backend/data/billing.db
```
(Adjust the path if your `DB_PATH` is different.)  
Restart the server and the tables will be recreated empty.

---

## Security (next steps)

- Bind to `127.0.0.1` locally; use a reverse proxy with TLS (Caddy/nginx) if exposed.
- Require an **API key** for all `/v1/*` endpoints.
- Map API keys → customer; derive `customer_id` server-side (avoid horizontal access).
- Add request size & batch limits, input validation, and basic rate limiting.
- Add security headers (CSP, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`).

---

## Product & scale (next steps)

- **Pricing engine:** tiered/volume/graduated, minimums, overage, credits/commits, proration.
- **Late events:** watermark + grace window + auto-adjustments.
- **Parallel billing:** shard by customer and fan-out (workers/queues).
- **Observability:** request/worker metrics, traces, structured logs, alerts.
- **Persistence:** migrate to Postgres; add migrations & read replicas.
- **Production stack:** FastAPI + Uvicorn, background workers (Celery/Arq), S3 for raw events/PDFs.
- **UX:** “what-if” estimator, plan ladders, invoice PDFs.

---

## Why this project exists

A compact, interview-ready demo of usage-based billing that you can run anywhere and extend to production patterns when ready—showing the full flow from event ingestion to rated invoices with minimal moving parts.
