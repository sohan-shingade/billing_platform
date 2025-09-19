/**
 * Front‑end logic for the usage‑based billing dashboard.
 *
 * This script attaches event handlers to forms in index.html and calls
 * the billing API implemented by the Python server. It is written in
 * TypeScript and compiled to JavaScript using `tsc`. The API base URL
 * defaults to the same origin so that the HTML file can be served from
 * a static file server or directly opened in the browser.
 */
const apiBase = ""; // Same origin
function $(id) {
    return document.getElementById(id);
}
function safeJson(obj) {
    return JSON.stringify(obj, null, 2);
}
async function postJson(url, body) {
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
async function getJson(url) {
    const resp = await fetch(apiBase + url);
    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text);
    }
    return resp.json();
}
function attachHandlers() {
    // Create customer
    $("create-customer-btn").addEventListener("click", async () => {
        try {
            const name = $("customer-name").value;
            const email = $("customer-email").value;
            const tz = $("customer-tz").value;
            const out = $("create-customer-output");
            const customer = await postJson("/v1/customers", { name, email, timezone: tz });
            out.textContent = safeJson(customer);
        }
        catch (err) {
            $("create-customer-output").textContent = err.message;
        }
    });
    // Ingest event
    $("ingest-event-btn").addEventListener("click", async () => {
        try {
            const cid = parseInt($("ingest-cid").value);
            const feature = $("ingest-feature").value;
            const quantity = parseFloat($("ingest-quantity").value);
            const ts = $("ingest-timestamp").value;
            const events = [{ customer_id: cid, feature, quantity, ts_event: ts }];
            const result = await postJson("/v1/events/batch", events);
            $("ingest-event-output").textContent = safeJson(result);
        }
        catch (err) {
            $("ingest-event-output").textContent = err.message;
        }
    });
    // Get usage
    $("get-usage-btn").addEventListener("click", async () => {
        try {
            const cid = parseInt($("usage-cid").value);
            const start = $("usage-start").value;
            const end = $("usage-end").value;
            const url = `/v1/customers/${cid}/usage?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
            const usage = await getJson(url);
            $("usage-output").textContent = safeJson(usage);
        }
        catch (err) {
            $("usage-output").textContent = err.message;
        }
    });
    // Run invoicing
    $("run-invoicing-btn").addEventListener("click", async () => {
        try {
            const period = $("invoice-period").value;
            const unitPrice = $("invoice-unitprice").value;
            const url = `/v1/invoices/run?period=${encodeURIComponent(period)}&unit_price=${encodeURIComponent(unitPrice)}`;
            const result = await postJson(url, {});
            $("invoice-run-output").textContent = safeJson(result);
        }
        catch (err) {
            $("invoice-run-output").textContent = err.message;
        }
    });
    // List invoices
    $("list-invoices-btn").addEventListener("click", async () => {
        try {
            const cid = parseInt($("invoice-list-cid").value);
            const invoices = await getJson(`/v1/customers/${cid}/invoices`);
            $("invoice-list-output").textContent = safeJson(invoices);
        }
        catch (err) {
            $("invoice-list-output").textContent = err.message;
        }
    });
}
// Attach handlers once DOM is loaded
document.addEventListener("DOMContentLoaded", attachHandlers);
