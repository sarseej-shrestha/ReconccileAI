/** Exercise the real production frontend and FastAPI backend against an isolated database. */
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import assert from "node:assert/strict";
import { chromium } from "../frontend/node_modules/playwright/index.mjs";

const root = resolve(import.meta.dirname, "..");
const output = process.env.REVIEW_OUTPUT || await mkdtemp(join(tmpdir(), "reconcileai-review-"));
await mkdir(output, { recursive: true });
const database = join(output, "browser.db");
const children = [];
let browser;
const errors = [];
function start(command, args, cwd, env = {}) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, stdio: ["ignore", "pipe", "pipe"] });
  let logs = "";
  child.stdout.on("data", b => { logs = (logs + b).slice(-15000); });
  child.stderr.on("data", b => { logs = (logs + b).slice(-15000); });
  child.on("error", e => errors.push(e.message));
  children.push({ child, logs: () => logs });
  return child;
}
async function ready(url) {
  for (let n = 0; n < 100; n++) {
    try { const r = await fetch(url); if (r.ok) return; } catch { /* wait for startup */ }
    if (children.some(c => c.child.exitCode !== null)) throw new Error(children.map(c => c.logs()).join("\n"));
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error(`Server not ready: ${url}`);
}
try {
  start(process.env.PYTHON || join(root, ".venv/bin/python"), ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], root, { DATABASE_URL: `sqlite:///${database}`, LLM_API_KEY: "" });
  await ready("http://127.0.0.1:8000/api/health");
  start(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"], join(root, "frontend"));
  await ready("http://127.0.0.1:3000");
  const browserPath = process.argv.includes("--browser") ? process.argv[process.argv.indexOf("--browser") + 1] : process.env.CHROMIUM_PATH;
  browser = await chromium.launch({ headless: true, ...(browserPath ? { executablePath: browserPath } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("http://127.0.0.1:3000");
  await page.getByRole("button", { name: "Load sample data" }).click();
  await page.getByRole("status").filter({ hasText: "Imported 24 invoices" }).waitFor();
  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await page.getByRole("status").filter({ hasText: "11 new proposals" }).waitFor();
  await page.locator(".recharts-bar-rectangle path").first().waitFor({ state: "visible" });
  await page.screenshot({ path: join(output, "overview.png"), fullPage: true });
  await page.getByRole("button", { name: "Reconciliation", exact: true }).click();
  await page.getByRole("button", { name: "Review INV-010", exact: true }).click();
  await page.getByRole("button", { name: "Investigate evidence" }).click();
  await page.getByText("3 read-only tool calls").waitFor();
  await page.getByRole("button", { name: "Approve proposal" }).click();
  await page.getByLabel("Review reason").fill("Verified USD 750.00 + USD 500.00 = USD 1,250.00 with matching references.");
  await page.getByRole("button", { name: "Confirm approval" }).click();
  await page.getByRole("button", { name: "Apply to simulated ledger" }).click();
  await page.getByRole("heading", { name: "Applied successfully" }).waitFor();
  await page.getByRole("button", { name: "Retry same writeback" }).click();
  await page.getByRole("heading", { name: "Existing result returned" }).waitFor();
  const ledger = await (await fetch("http://127.0.0.1:8000/api/ledger")).json();
  assert.equal(ledger.length, 2);
  assert.equal(ledger.reduce((sum, e) => sum + e.amount_cents, 0), 125000);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: join(output, "replay-safety.png"), fullPage: true });
  await page.getByRole("button", { name: "Review INV-002", exact: true }).click();
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await page.getByLabel("Review reason").fill("Requesting independent finance review.");
  await page.getByRole("button", { name: "Confirm rejection" }).click();
  await page.getByRole("status").filter({ hasText: "Proposal rejected." }).waitFor();
  const proposals = await (await fetch("http://127.0.0.1:8000/api/proposals")).json();
  const rejected = proposals.find(p => p.invoice_ids.includes("INV-002"));
  const response = await fetch(`http://127.0.0.1:8000/api/proposals/${rejected.id}/apply`, { method: "POST", headers: { "Content-Type": "application/json", "X-Reviewer-Token": "local-demo-reviewer", "Idempotency-Key": "browser-rejected-operation" }, body: JSON.stringify({ version: 2 }) });
  assert.equal(response.status, 409);
  await page.getByLabel("Upload financial CSV").setInputFiles({ name: "invoice.csv", mimeType: "text/csv", buffer: Buffer.from("id,invoice_number,counterparty,amount_cents,currency,issue_date,due_date\nINV-BROWSER,INV-BROWSER,Fable Browser Company,10001,USD,2026-09-01,2026-09-30\n") });
  await page.getByRole("status").filter({ hasText: "Imported 1 invoices" }).waitFor();
  await page.getByRole("button", { name: "Audit explorer", exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloadPromise;
  const audit = JSON.parse(await readFile(await download.path(), "utf8"));
  assert(audit.some(e => e.action === "idempotent_retry"));
  assert(audit.some(e => e.action === "ledger_writeback_failed"));
  await page.getByLabel("Filter audit action").selectOption("idempotent_retry");
  await page.screenshot({ path: join(output, "audit.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: join(output, "mobile.png"), fullPage: true });
  assert.deepEqual(errors, []);
  const report = { passed: true, checks: ["real sample import", "11 deterministic proposals", "read-only investigation", "human approval", "atomic split settlement", "zero-effect replay", "rejected posting blocked", "CSV upload", "audit export and filter", "mobile layout", "no uncaught browser errors"], ledger_entries: ledger.length, retry_additional_entries: 0, output };
  await writeFile(join(output, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser?.close();
  for (const c of children.reverse()) c.child.kill("SIGTERM");
}
