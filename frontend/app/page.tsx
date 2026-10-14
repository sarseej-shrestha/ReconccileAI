"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Check,
  CheckCheck,
  CircleAlert,
  FileText,
  GitCompareArrows,
  LayoutDashboard,
  ListFilter,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import {
  api,
  loadData,
  type Data,
  type Proposal,
  type Investigation,
  type Posting,
  type ExceptionCase,
} from "@/lib/api";
import { label, money } from "@/lib/utils";

type View = "overview" | "workspace" | "exceptions" | "audit";
const views = [
  { id: "overview", name: "Overview", icon: LayoutDashboard },
  { id: "workspace", name: "Reconciliation", icon: GitCompareArrows },
  { id: "exceptions", name: "Exceptions", icon: CircleAlert },
  { id: "audit", name: "Audit explorer", icon: Activity },
] as const;
function Badge({ value }: { value: string }) {
  return <span className={`badge ${value.toLowerCase()}`}>{label(value)}</span>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty">
      <FileText size={26} />
      <p>{children}</p>
    </div>
  );
}

export default function Dashboard() {
  const [view, setView] = useState<View>("overview");
  const [data, setData] = useState<Data | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [records, setRecords] = useState("invoices");
  const [selected, setSelected] = useState<string | null>(null);
  const [investigation, setInvestigation] = useState<Investigation | null>(
    null,
  );
  const [posting, setPosting] = useState<Posting | null>(null);
  const [auditFilter, setAuditFilter] = useState("");
  const [reviewerToken, setReviewerToken] = useState("local-demo-reviewer");
  const [confirmation, setConfirmation] = useState<{
    proposal: Proposal;
    decision: "APPROVED" | "REJECTED";
  } | null>(null);
  const [reason, setReason] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const importInput = useRef<HTMLInputElement>(null);
  const refresh = useCallback(async () => setData(await loadData()), []);
  useEffect(() => {
    let active = true;
    loadData()
      .then((value) => {
        if (active) setData(value);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (confirmation) dialog.current?.showModal();
    else dialog.current?.close();
  }, [confirmation]);

  async function run(name: string, action: () => Promise<void>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy("");
    }
  }
  function navigate(next: View) {
    setView(next);
    setSelected(null);
    setInvestigation(null);
    setFilter("ALL");
  }
  const proposal = data?.proposals.find(
    (p) => p.id === selected || p.invoice_ids.includes(selected || ""),
  );
  const exception = data?.exceptions.find(
    (e) =>
      e.id === selected ||
      e.invoice_id === selected ||
      (proposal && e.invoice_id === proposal.invoice_ids[0]),
  );
  const evidence = proposal?.evidence || exception?.evidence;
  const invoice = data?.invoices.find((i) => i.id === evidence?.invoice_ids[0]);
  function select(id: string) {
    setSelected(id);
    setInvestigation(null);
    setPosting(null);
  }

  async function investigate(item: ExceptionCase) {
    await run("investigate", async () => {
      setInvestigation(
        await api<Investigation>(`/exceptions/${item.id}/investigate`, {
          method: "POST",
        }),
      );
    });
  }
  async function applyProposal(item: Proposal) {
    await run("apply", async () => {
      const storageKey = `reconcileai-posting-${item.id}`;
      const stored = sessionStorage.getItem(storageKey);
      const request = stored
        ? (JSON.parse(stored) as { key: string; version: number })
        : { key: crypto.randomUUID(), version: item.version };
      sessionStorage.setItem(storageKey, JSON.stringify(request));
      const result = await api<Posting>(`/proposals/${item.id}/apply`, {
        method: "POST",
        headers: {
          "X-Reviewer-Token": reviewerToken,
          "Idempotency-Key": request.key,
        },
        body: JSON.stringify({ version: request.version }),
      });
      setPosting(result);
      setNotice(
        result.replayed
          ? `Existing result returned. Additional ledger entries: ${result.additional_entries}.`
          : `Applied successfully. Created ${result.additional_entries} ledger entries.`,
      );
    });
  }
  async function exportAudit() {
    await run("export", async () => {
      const events = await api<unknown[]>(
        `/audit?limit=10000${auditFilter ? `&action=${encodeURIComponent(auditFilter)}` : ""}`,
      );
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(events, null, 2)], {
          type: "application/json",
        }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "reconcileai-audit.json";
      a.click();
      URL.revokeObjectURL(url);
      setNotice(`Exported ${events.length} audit events.`);
    });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="ReconcileAI home">
          <span className="brand-mark">
            <CheckCheck size={22} />
          </span>
          Reconcile<span>AI</span>
        </Link>
        <div className="workspace-label">
          <span className="avatar">F</span>
          <div>
            Fable Finance<span>Fictional demo workspace</span>
          </div>
          <span className="live-dot" />
        </div>
        <p className="nav-label">OPERATIONS</p>
        <nav aria-label="Main navigation">
          {views.map((v) => (
            <button
              key={v.id}
              className={view === v.id ? "nav-item active" : "nav-item"}
              onClick={() => navigate(v.id)}
            >
              <v.icon size={18} />
              {v.name}
              {v.id === "exceptions" &&
                !!data?.overview.unresolved_exceptions && (
                  <span className="nav-count">
                    {data.overview.unresolved_exceptions}
                  </span>
                )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={20} />
          <strong>Every decision accounted for.</strong>
          <p>
            Rules verify. Humans approve.
            <br />
            Transactions execute.
          </p>
        </div>
        <div className="reviewer">
          <span className="avatar reviewer-avatar">DR</span>
          <div>
            Demo reviewer<span>Simulated authentication</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            Workspace <span>/</span>{" "}
            <strong>{views.find((v) => v.id === view)?.name}</strong>
          </div>
          <span className="environment">
            <span className="live-dot" /> Sandbox · Fictional data
          </span>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <p className="eyebrow">FINANCIAL OPERATIONS</p>
              <h1>
                {view === "overview"
                  ? "A clear view of your books."
                  : views.find((v) => v.id === view)?.name}
              </h1>
              <p>
                {view === "overview"
                  ? "Intelligent financial reconciliation, with every decision accounted for."
                  : view === "workspace"
                    ? "From bank activity to verified, human-approved settlements."
                    : view === "exceptions"
                      ? "Investigate discrepancies. Follow the evidence."
                      : "Trace the evidence, decisions, and effects behind every operation."}
              </p>
            </div>
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() => run("refresh", refresh)}
              aria-label="Refresh application data"
            >
              <RefreshCw size={15} />
              Refresh
            </Button>
          </div>
          {error && (
            <div className="alert error" role="alert">
              <CircleAlert size={18} />
              {error}
              <Button
                variant="ghost"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={15} />
              </Button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Check size={18} />
              {notice}
            </div>
          )}
          {busy && (
            <div className="working" role="status">
              <LoaderCircle size={15} className="spin" />
              Processing {busy}…
            </div>
          )}
          {!data ? (
            <Empty>
              {error
                ? "Start the backend and refresh to connect."
                : "Loading financial records…"}
            </Empty>
          ) : (
            <>
              {(view === "overview" || view === "workspace") && (
                <div className="action-strip">
                  <div>
                    <span className="step-dot">1</span>
                    <strong>Load records</strong>
                    <ArrowRight size={14} />
                    <span className="step-dot">2</span>
                    <strong>Find matches</strong>
                    <ArrowRight size={14} />
                    <span className="step-dot">3</span>
                    <strong>Review & apply</strong>
                  </div>
                  <div>
                    <Button
                      variant="outline"
                      disabled={!!busy}
                      onClick={() =>
                        run("import", async () => {
                          const r = await api<{
                            invoices: number;
                            transactions: number;
                            unchanged: number;
                          }>("/demo/load", { method: "POST" });
                          setNotice(
                            `Imported ${r.invoices} invoices and ${r.transactions} transactions; ${r.unchanged} unchanged.`,
                          );
                        })
                      }
                    >
                      <Upload size={15} />
                      Load sample data
                    </Button>
                    <Button
                      disabled={!!busy || !data.invoices.length}
                      onClick={() =>
                        run("reconciliation", async () => {
                          const r = await api<{
                            new_proposals: number;
                            new_exceptions: number;
                          }>("/reconcile", { method: "POST" });
                          setNotice(
                            `${r.new_proposals} new proposals and ${r.new_exceptions} new exceptions. Candidates require human approval.`,
                          );
                        })
                      }
                    >
                      <Play size={14} />
                      Run reconciliation
                    </Button>
                  </div>
                </div>
              )}
              {view === "overview" && (
                <>
                  <section className="metrics" aria-label="Financial metrics">
                    <div className="metric">
                      <span>
                        Total invoices
                        <FileText size={17} />
                      </span>
                      <strong>{data.overview.total_invoices}</strong>
                      <small>
                        {data.overview.total_transactions} bank transactions
                        imported
                      </small>
                    </div>
                    <div className="metric">
                      <span>
                        Payment volume
                        <Wallet size={17} />
                      </span>
                      {Object.entries(data.overview.payment_volume).map(
                        ([currency, amount]) => (
                          <strong className="money-stat" key={currency}>
                            {money(amount, currency)}
                          </strong>
                        ),
                      )}
                      {!data.transactions.length && <strong>—</strong>}
                      <small>
                        Gross absolute volume · currencies separated
                      </small>
                    </div>
                    <div className="metric">
                      <span>
                        Reconciled amount
                        <CheckCheck size={17} />
                      </span>
                      {Object.entries(data.overview.reconciled_amount).map(
                        ([currency, amount]) => (
                          <strong className="money-stat" key={currency}>
                            {money(amount, currency)}
                          </strong>
                        ),
                      )}
                      {!data.ledger.length && <strong>—</strong>}
                      <small>
                        {data.overview.matching_rate}% of invoices applied
                      </small>
                    </div>
                    <div className="metric">
                      <span>
                        Needs attention
                        <CircleAlert size={17} />
                      </span>
                      <strong>
                        {data.overview.pending_approvals}
                        <small className="inline-unit"> approvals</small>
                      </strong>
                      <small>
                        {data.overview.unresolved_exceptions} unresolved
                        exceptions
                      </small>
                    </div>
                  </section>
                  <div className="overview-grid">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Reconciliation pipeline</h2>
                          <p>Candidates and completed settlements</p>
                        </div>
                        <Badge value="LIVE_DATA" />
                      </div>
                      <div
                        className="chart"
                        role="img"
                        aria-label={data.overview.status_counts
                          .map((s) => `${s.name}: ${s.count}`)
                          .join(", ")}
                      >
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={data.overview.status_counts}
                            margin={{
                              left: -20,
                              right: 20,
                              top: 10,
                              bottom: 0,
                            }}
                          >
                            <CartesianGrid vertical={false} stroke="#e8edf3" />
                            <XAxis
                              dataKey="name"
                              axisLine={false}
                              tickLine={false}
                              fontSize={12}
                              dy={8}
                            />
                            <YAxis
                              allowDecimals={false}
                              axisLine={false}
                              tickLine={false}
                              fontSize={12}
                            />
                            <Tooltip cursor={{ fill: "#f1f5f9" }} />
                            <Bar
                              dataKey="count"
                        isAnimationActive={false}
                              name="Proposals"
                              fill="#2563eb"
                              radius={[5, 5, 0, 0]}
                              maxBarSize={52}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="panel-footer">
                        An identified match becomes reconciled only after
                        approval and posting.
                      </div>
                    </section>
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Review queue</h2>
                          <p>Keep the close moving</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate("workspace")}
                        >
                          View all
                          <ArrowRight size={14} />
                        </Button>
                      </div>
                      {data.proposals
                        .filter((p) => p.status === "PROPOSED")
                        .slice(0, 4)
                        .map((p) => (
                          <button
                            className="queue-row"
                            key={p.id}
                            onClick={() => {
                              setView("workspace");
                              select(p.id);
                            }}
                          >
                            <span className="queue-icon">
                              <GitCompareArrows size={18} />
                            </span>
                            <span>
                              <strong>{p.invoice_ids.join(", ")}</strong>
                              <small>{label(p.matching_method)}</small>
                            </span>
                            <span>
                              {money(
                                p.proposed_amount_cents,
                                p.evidence.currency,
                              )}
                              <small>Review required →</small>
                            </span>
                          </button>
                        ))}
                      {!data.proposals.some((p) => p.status === "PROPOSED") && (
                        <Empty>
                          Run reconciliation to generate reviewable proposals.
                        </Empty>
                      )}
                    </section>
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Recent activity</h2>
                        <p>A record of every meaningful step</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate("audit")}
                      >
                        Open audit explorer
                        <ArrowRight size={14} />
                      </Button>
                    </div>
                    {data.audit.slice(0, 5).map((e) => (
                      <div className="activity-row" key={e.id}>
                        <span className="activity-dot" />
                        <strong>{label(e.action)}</strong>
                        <span>{e.entity_type}</span>
                        <small>
                          {new Date(
                            e.timestamp +
                              (e.timestamp.endsWith("Z") ? "" : "Z"),
                          ).toLocaleTimeString()}
                        </small>
                      </div>
                    ))}
                    {!data.audit.length && (
                      <Empty>Load data to begin your audit history.</Empty>
                    )}
                  </section>
                </>
              )}
              {view === "workspace" && (
                <div className={selected ? "workspace-grid" : ""}>
                  <div>
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>
                            Match proposals{" "}
                            <span className="count">
                              {data.proposals.length}
                            </span>
                          </h2>
                          <p>
                            Identified candidates are never applied
                            automatically.
                          </p>
                        </div>
                        <label className="filter">
                          <ListFilter size={14} />
                          <select
                            aria-label="Filter proposal status"
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                          >
                            {[
                              "ALL",
                              "PROPOSED",
                              "APPROVED",
                              "APPLIED",
                              "REJECTED",
                            ].map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Invoice</th>
                              <th>Method</th>
                              <th>Amount</th>
                              <th>Status</th>
                              <th>
                                <span className="sr-only">Review</span>
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {data.proposals
                              .filter(
                                (p) => filter === "ALL" || p.status === filter,
                              )
                              .map((p) => (
                                <tr
                                  className={
                                    proposal?.id === p.id ? "selected-row" : ""
                                  }
                                  key={p.id}
                                >
                                  <td className="reference">
                                    {p.invoice_ids.join(", ")}
                                  </td>
                                  <td>
                                    {label(p.matching_method)}
                                    <small>
                                      {p.transaction_ids.length} payment
                                      {p.transaction_ids.length === 1
                                        ? ""
                                        : "s"}
                                    </small>
                                  </td>
                                  <td className="numeric">
                                    {money(
                                      p.proposed_amount_cents,
                                      p.evidence.currency,
                                    )}
                                  </td>
                                  <td>
                                    <Badge value={p.status} />
                                  </td>
                                  <td>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => select(p.id)}
                                      aria-label={`Review ${p.invoice_ids[0]}`}
                                    >
                                      Review
                                      <ArrowRight size={13} />
                                    </Button>
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                      {!data.proposals.length && (
                        <Empty>
                          Run reconciliation to identify candidates.
                        </Empty>
                      )}
                    </section>
                    <section className="panel records">
                      <div className="panel-heading">
                        <div className="tabs">
                          {["invoices", "transactions", "ledger"].map((t) => (
                            <button
                              key={t}
                              className={records === t ? "active" : ""}
                              onClick={() => setRecords(t)}
                            >
                              {t}
                            </button>
                          ))}
                        </div>
                        {records !== "ledger" && (
                          <>
                            <input
                              ref={importInput}
                              className="sr-only"
                              type="file"
                              accept=".csv,text/csv"
                              aria-label="Upload financial CSV"
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file)
                                  run("CSV import", async () => {
                                    const form = new FormData();
                                    form.append("file", file);
                                    const r = await api<{
                                      invoices: number;
                                      transactions: number;
                                    }>(`/import/csv?kind=${records}`, {
                                      method: "POST",
                                      body: form,
                                    });
                                    setNotice(
                                      `Imported ${r.invoices} invoices and ${r.transactions} transactions.`,
                                    );
                                  });
                                e.target.value = "";
                              }}
                            />
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!!busy}
                              onClick={() => importInput.current?.click()}
                            >
                              <Upload size={14} />
                              Import CSV
                            </Button>
                          </>
                        )}
                      </div>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Reference</th>
                              <th>
                                {records === "ledger"
                                  ? "Invoice / transaction"
                                  : "Counterparty"}
                              </th>
                              <th>Amount</th>
                              <th>
                                {records === "ledger" ? "Entry type" : "Status"}
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {records === "invoices"
                              ? data.invoices.map((i) => (
                                  <tr key={i.id}>
                                    <td className="reference">
                                      {i.id}
                                      <small>Due {i.due_date}</small>
                                    </td>
                                    <td>
                                      {i.counterparty}
                                      <small>{i.kind}</small>
                                    </td>
                                    <td className="numeric">
                                      {money(i.amount_cents, i.currency)}
                                    </td>
                                    <td>
                                      <Badge value={i.status} />
                                    </td>
                                  </tr>
                                ))
                              : records === "transactions"
                                ? data.transactions.map((t) => (
                                    <tr key={t.id}>
                                      <td className="reference">
                                        {t.id}
                                        <small>{t.date}</small>
                                      </td>
                                      <td>
                                        {t.counterparty}
                                        <small
                                          className="description"
                                          title={t.description}
                                        >
                                          {t.description}
                                        </small>
                                      </td>
                                      <td className="numeric">
                                        {money(t.amount_cents, t.currency)}
                                      </td>
                                      <td>
                                        <Badge value={t.status} />
                                      </td>
                                    </tr>
                                  ))
                                : data.ledger.map((l) => (
                                    <tr key={l.id}>
                                      <td
                                        className="reference"
                                        title={l.operation_id}
                                      >
                                        {l.id.slice(0, 8)}
                                      </td>
                                      <td>
                                        {l.invoice_id} / {l.transaction_id}
                                      </td>
                                      <td className="numeric">
                                        {money(l.amount_cents, l.currency)}
                                      </td>
                                      <td>
                                        <Badge value={l.entry_type} />
                                      </td>
                                    </tr>
                                  ))}
                          </tbody>
                        </table>
                      </div>
                      {records === "ledger" && !data.ledger.length && (
                        <Empty>
                          Approved proposals create entries when you apply them.
                        </Empty>
                      )}
                    </section>
                  </div>
                  {selected && renderDetail()}
                </div>
              )}
              {view === "exceptions" && (
                <div className={selected ? "workspace-grid" : ""}>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          Exception inbox{" "}
                          <span className="count">
                            {
                              data.exceptions.filter((e) => e.status === "OPEN")
                                .length
                            }
                          </span>
                        </h2>
                        <p>
                          Abstention keeps ambiguous records out of the ledger.
                        </p>
                      </div>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Reference</th>
                            <th>Exception</th>
                            <th>Status</th>
                            <th>
                              <span className="sr-only">Open</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.exceptions.map((e) => (
                            <tr key={e.id}>
                              <td className="reference">
                                {e.invoice_id || e.transaction_id}
                              </td>
                              <td>{label(e.classification)}</td>
                              <td>
                                <Badge value={e.status} />
                              </td>
                              <td>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => select(e.invoice_id || e.id)}
                                  aria-label={`Investigate ${e.invoice_id || e.transaction_id}`}
                                >
                                  Investigate
                                  <ArrowRight size={13} />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {!data.exceptions.length && (
                      <Empty>
                        Run reconciliation to identify unresolved discrepancies.
                      </Empty>
                    )}
                  </section>
                  {selected && renderDetail()}
                </div>
              )}
              {view === "audit" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Audit history</h2>
                      <p>
                        Append-only through the application · latest 1,000
                        events shown
                      </p>
                    </div>
                    <div className="toolbar">
                      <label className="filter">
                        <Search size={14} />
                        <select
                          aria-label="Filter audit action"
                          value={auditFilter}
                          onChange={(e) => setAuditFilter(e.target.value)}
                        >
                          <option value="">All actions</option>
                          {Array.from(
                            new Set(data.audit.map((e) => e.action)),
                          ).map((a) => (
                            <option value={a} key={a}>
                              {label(a)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <Button
                        variant="outline"
                        disabled={!!busy}
                        onClick={exportAudit}
                      >
                        <ArrowDownToLine size={15} />
                        Export JSON
                      </Button>
                    </div>
                  </div>
                  <div className="audit-list">
                    {data.audit
                      .filter((e) => !auditFilter || e.action === auditFilter)
                      .map((e) => (
                        <details key={e.id}>
                          <summary>
                            <span className="audit-icon">
                              <Activity size={16} />
                            </span>
                            <span>
                              <strong>{label(e.action)}</strong>
                              <small>
                                {e.entity_type} · {e.entity_id}
                              </small>
                            </span>
                            <span className="audit-actor">{e.actor}</span>
                            <time>
                              {new Date(
                                e.timestamp +
                                  (e.timestamp.endsWith("Z") ? "" : "Z"),
                              ).toLocaleString()}
                            </time>
                          </summary>
                          <div className="audit-details">
                            <p>{e.reason || "System event recorded."}</p>
                            <small>Correlation: {e.correlation_id}</small>
                            <pre>
                              {JSON.stringify(
                                {
                                  previous: e.previous_state,
                                  next: e.new_state,
                                },
                                null,
                                2,
                              )}
                            </pre>
                          </div>
                        </details>
                      ))}
                  </div>
                  {!data.audit.length && (
                    <Empty>No events yet. Load sample data to begin.</Empty>
                  )}
                </section>
              )}
            </>
          )}
          <footer>
            ReconcileAI{" "}
            <span>
              Simulated ledger · No real bank connections · Amounts stored in
              integer cents
            </span>
          </footer>
        </main>
      </div>
      <dialog
        ref={dialog}
        className="confirmation"
        onCancel={() => setConfirmation(null)}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!confirmation) return;
            const c = confirmation;
            run("review", async () => {
              await api(`/proposals/${c.proposal.id}/review`, {
                method: "POST",
                headers: { "X-Reviewer-Token": reviewerToken },
                body: JSON.stringify({
                  decision: c.decision,
                  version: c.proposal.version,
                  reason,
                }),
              });
              setConfirmation(null);
              setReason("");
              setNotice(`Proposal ${c.decision.toLowerCase()}.`);
            });
          }}
        >
          <ShieldCheck size={28} />
          <h2>
            {confirmation?.decision === "APPROVED"
              ? "Approve this reconciliation?"
              : "Reject this proposal?"}
          </h2>
          <p>
            {confirmation?.decision === "APPROVED"
              ? "The backend will independently verify the evidence. Posting is a separate action."
              : "The proposal will be closed and cannot be posted."}
          </p>
          <label>
            Review reason
            <textarea
              required
              minLength={3}
              maxLength={1000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain the evidence behind your decision"
            />
          </label>
          <label>
            Demo reviewer token
            <input
              type="password"
              value={reviewerToken}
              onChange={(e) => setReviewerToken(e.target.value)}
              autoComplete="off"
            />
          </label>
          <small>
            Prototype identity only. This is not production authentication.
          </small>
          <div className="dialog-actions">
            <Button
              type="button"
              variant="outline"
              disabled={!!busy}
              onClick={() => setConfirmation(null)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!!busy || reason.trim().length < 3}>
              Confirm{" "}
              {confirmation?.decision === "APPROVED" ? "approval" : "rejection"}
            </Button>
          </div>
          {error && (
            <p role="alert" className="dialog-error">
              {error}
            </p>
          )}
        </form>
      </dialog>
    </div>
  );

  function renderDetail() {
    return (
      <aside className="panel detail" aria-label="Reconciliation details">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">EVIDENCE & REVIEW</p>
            <h2>{invoice?.id || exception?.transaction_id || "Case detail"}</h2>
          </div>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Close details"
            onClick={() => setSelected(null)}
          >
            <X size={18} />
          </Button>
        </div>
        <div className="detail-body">
          <h3>{invoice?.counterparty || "Unallocated receipt"}</h3>
          {invoice && (
            <p className="detail-amount">
              {money(invoice.amount_cents, invoice.currency)}
            </p>
          )}
          <Badge
            value={proposal?.status || exception?.classification || "OPEN"}
          />
          <div className="evidence-box">
            <h4>Deterministic evidence</h4>
            <p>{evidence?.explanation}</p>
            {evidence?.difference_cents !== undefined && (
              <div className="difference">
                <span>Eligible amount difference</span>
                <strong>
                  {money(evidence.difference_cents, evidence.currency)}
                </strong>
              </div>
            )}
            <ul className="candidate-list">
              {evidence?.transaction_ids.map((id) => {
                const t = data?.transactions.find((t) => t.id === id);
                return (
                  <li key={id}>
                    <span>
                      {id}
                      <small>
                        {t?.date} · {t?.counterparty}
                      </small>
                    </span>
                    <strong>{t && money(t.amount_cents, t.currency)}</strong>
                  </li>
                );
              })}
            </ul>
            <div
              className={
                proposal?.verification.valid
                  ? "verification valid"
                  : "verification"
              }
            >
              <ShieldCheck size={16} />
              {proposal?.verification.valid
                ? "Verified · full allocation matches"
                : proposal?.status === "APPLIED"
                  ? "Applied with verified provenance"
                  : proposal?.verification.error ||
                    "Abstained · further evidence required"}
            </div>
          </div>
          {exception && (
            <div className="investigator">
              <div className="section-title">
                <h4>
                  <Sparkles size={15} />
                  Investigation
                </h4>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!!busy}
                  onClick={() => investigate(exception)}
                >
                  Investigate evidence
                </Button>
              </div>
              {investigation ? (
                <>
                  <Badge value={investigation.source} />
                  <p>{investigation.recommendation.summary}</p>
                  <dl>
                    <dt>Uncertainty</dt>
                    <dd>{investigation.recommendation.uncertainty}</dd>
                    <dt>Next action</dt>
                    <dd>
                      {label(investigation.recommendation.recommended_action)}
                    </dd>
                  </dl>
                  {investigation.fallback_reason && (
                    <p>{investigation.fallback_reason}</p>
                  )}
                  <details>
                    <summary>
                      {investigation.tool_trace.length} read-only tool calls
                    </summary>
                    {investigation.tool_trace.map((t, n) => (
                      <div className="tool-call" key={n}>
                        <strong>{t.tool}</strong>
                        <pre>
                          {JSON.stringify(t.result || t.error, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </details>
                  <small>
                    Explanations use verified facts. Model confidence is not a
                    probability.
                  </small>
                </>
              ) : (
                <p>
                  Gather candidate payments, ledger evidence, and a structured
                  recommendation. No API key is required.
                </p>
              )}
            </div>
          )}
          {proposal && (
            <div className="review-actions">
              {proposal.status === "PROPOSED" && (
                <>
                  <Button
                    disabled={!!busy || !proposal.verification.valid}
                    onClick={() =>
                      setConfirmation({ proposal, decision: "APPROVED" })
                    }
                  >
                    <Check size={15} />
                    Approve proposal
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!!busy}
                    onClick={() =>
                      setConfirmation({ proposal, decision: "REJECTED" })
                    }
                  >
                    Reject
                  </Button>
                </>
              )}
              {(proposal.status === "APPROVED" ||
                proposal.status === "APPLIED") && (
                <Button
                  disabled={
                    !!busy ||
                    (proposal.status === "APPROVED" &&
                      !proposal.verification.valid)
                  }
                  onClick={() => applyProposal(proposal)}
                >
                  <Wallet size={15} />
                  {proposal.status === "APPLIED"
                    ? "Retry same writeback"
                    : "Apply to simulated ledger"}
                </Button>
              )}
              <small>
                Version {proposal.version} · Human approval required
              </small>
            </div>
          )}
          {posting && (
            <div className="posting-result" role="status">
              <h4>
                {posting.replayed
                  ? "Existing result returned"
                  : "Applied successfully"}
              </h4>
              <strong>
                Additional ledger entries: {posting.additional_entries}
              </strong>
              <p>Operation {posting.operation_id.slice(0, 8)}</p>
              {posting.ledger_entries.map((l) => (
                <div key={l.id}>
                  {l.transaction_id} · {money(l.amount_cents, l.currency)}
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    );
  }
}
