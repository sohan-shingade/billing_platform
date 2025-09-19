"""Demonstration script for the usage-based billing server.

This script starts the billing server in a background thread, creates a
sample customer, ingests a few usage events, queries aggregated usage and
generates an invoice. It uses `urllib` from the standard library to make
HTTP requests to the server. Run this script directly to see the API in
action. Make sure to run from the `billing_platform/backend` directory so
that relative paths resolve correctly.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from urllib import request, parse

from server import start_background_server, create_customer


def http_post(url: str, data: dict):
    data_bytes = json.dumps(data).encode("utf-8")
    req = request.Request(url, data=data_bytes, method="POST")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def http_get(url: str):
    with request.urlopen(url) as resp:
        return json.loads(resp.read().decode())


def run_demo(base_url: str = "http://localhost:8000"):
    # Create a customer
    customer = create_customer("Acme Corp", "contact@acme.com")
    cid = customer["id"]
    print("Created customer", customer)

    # Ingest some events
    now = datetime.utcnow()
    events = [
        {
            "customer_id": cid,
            "feature": "api_calls",
            "quantity": 10,
            "ts_event": (now - timedelta(minutes=5)).isoformat(),
        },
        {
            "customer_id": cid,
            "feature": "api_calls",
            "quantity": 5,
            "ts_event": (now - timedelta(minutes=2)).isoformat(),
        },
        {
            "customer_id": cid,
            "feature": "storage",
            "quantity": 1,
            "ts_event": (now - timedelta(minutes=1)).isoformat(),
        },
    ]
    print("Ingesting events...")
    resp = http_post(f"{base_url}/v1/events/batch", events)
    print("Insert response", resp)

    # Query usage for last 10 minutes
    start = (now - timedelta(minutes=10)).isoformat()
    end = now.isoformat()
    usage = http_get(f"{base_url}/v1/customers/{cid}/usage?start={parse.quote(start)}&end={parse.quote(end)}")
    print("Usage:", usage)

    # Generate invoice for the current month
    period = now.strftime("%Y-%m")
    invoice_resp = http_post(f"{base_url}/v1/invoices/run?period={period}&unit_price=0.01", {})
    print("Generated invoices:", invoice_resp)

    # List invoices
    invoices = http_get(f"{base_url}/v1/customers/{cid}/invoices")
    print("Invoices:", json.dumps(invoices, indent=2))


if __name__ == "__main__":
    # Start server in background
    start_background_server()
    # Give the server a moment to start
    time.sleep(1)
    run_demo()