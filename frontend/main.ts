/**
 * Front‑end logic for the usage‑based billing dashboard.
 *
 * This script attaches event handlers to forms in index.html and calls
 * the billing API implemented by the Python server. It is written in
 * TypeScript and compiled to JavaScript using `tsc`. The API base URL
 * defaults to the same origin so that the HTML file can be served from
 * a static file server or directly opened in the browser.
 */

interface Customer {
    id: number;
    name: string;
    email: string;
    timezone: string;
}

interface InvoiceLineItem {
    feature: string;
    quantity: number;
    unit_price: number;
    amount: number;
}

interface Invoice {
    id: number;
    period_start: string;
    period_end: string;
    total: number;
    generated_at: string;
    line_items: InvoiceLineItem[];
}

const apiBase = ""; // Same origin

function $(id: string): HTMLInputElement | HTMLPreElement | HTMLButtonElement | null {
    return document.getElementById(id) as any;
}

function safeJson(obj: any): string {
    return JSON.stringify(obj, null, 2);
}

async function postJson(url: string, body: any): Promise<any> {
    const resp = await fetch(apiBase + url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text);
    }
    return resp.json();
}

async function getJson(url: string): Promise<any> {
    const resp = await fetch(apiBase + url);
    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text);
    }
    return resp.json();
}

function attachHandlers() {
    // Create customer
    $("create-customer-btn")!.addEventListener("click", async () => {
        try {
            const name = ($("customer-name") as HTMLInputElement).value;
            const email = ($("customer-email") as HTMLInputElement).value;
            const tz = ($("customer-tz") as HTMLInputElement).value;
            const out = $("create-customer-output") as HTMLPreElement;
            const customer = await postJson("/v1/customers", { name, email, timezone: tz });
            out.textContent = safeJson(customer);
        } catch (err) {
            ( $("create-customer-output") as HTMLPreElement ).textContent = (err as Error).message;
        }
    });

    // Ingest event
    $("ingest-event-btn")!.addEventListener("click", async () => {
        try {
            const cid = parseInt(( $("ingest-cid") as HTMLInputElement ).value);
            const feature = ( $("ingest-feature") as HTMLInputElement ).value;
            const quantity = parseFloat(( $("ingest-quantity") as HTMLInputElement ).value);
            const ts = ( $("ingest-timestamp") as HTMLInputElement ).value;
            const events = [ { customer_id: cid, feature, quantity, ts_event: ts } ];
            const result = await postJson("/v1/events/batch", events);
            ( $("ingest-event-output") as HTMLPreElement ).textContent = safeJson(result);
        } catch (err) {
            ( $("ingest-event-output") as HTMLPreElement ).textContent = (err as Error).message;
        }
    });

    // Get usage
    $("get-usage-btn")!.addEventListener("click", async () => {
        try {
            const cid = parseInt(( $("usage-cid") as HTMLInputElement ).value);
            const start = ( $("usage-start") as HTMLInputElement ).value;
            const end = ( $("usage-end") as HTMLInputElement ).value;
            const url = `/v1/customers/${cid}/usage?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
            const usage = await getJson(url);
            ( $("usage-output") as HTMLPreElement ).textContent = safeJson(usage);
        } catch (err) {
            ( $("usage-output") as HTMLPreElement ).textContent = (err as Error).message;
        }
    });

    // Run invoicing
    $("run-invoicing-btn")!.addEventListener("click", async () => {
        try {
            const period = ( $("invoice-period") as HTMLInputElement ).value;
            const unitPrice = ( $("invoice-unitprice") as HTMLInputElement ).value;
            const url = `/v1/invoices/run?period=${encodeURIComponent(period)}&unit_price=${encodeURIComponent(unitPrice)}`;
            const result = await postJson(url, {});
            ( $("invoice-run-output") as HTMLPreElement ).textContent = safeJson(result);
        } catch (err) {
            ( $("invoice-run-output") as HTMLPreElement ).textContent = (err as Error).message;
        }
    });

    // List invoices
    $("list-invoices-btn")!.addEventListener("click", async () => {
        try {
            const cid = parseInt(( $("invoice-list-cid") as HTMLInputElement ).value);
            const invoices: Invoice[] = await getJson(`/v1/customers/${cid}/invoices`);
            ( $("invoice-list-output") as HTMLPreElement ).textContent = safeJson(invoices);
        } catch (err) {
            ( $("invoice-list-output") as HTMLPreElement ).textContent = (err as Error).message;
        }
    });
}

// Attach handlers once DOM is loaded
document.addEventListener("DOMContentLoaded", attachHandlers);