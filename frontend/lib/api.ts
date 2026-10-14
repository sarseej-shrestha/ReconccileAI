export interface Invoice {
  id: string;
  counterparty: string;
  amount_cents: number;
  currency: string;
  issue_date: string;
  due_date: string;
  kind: string;
  status: string;
}
export interface Transaction {
  id: string;
  external_reference: string;
  counterparty: string;
  amount_cents: number;
  currency: string;
  date: string;
  description: string;
  status: string;
}
export interface Evidence {
  invoice_ids: string[];
  transaction_ids: string[];
  difference_cents?: number;
  candidate_amount_cents?: number;
  invoice_amount_cents?: number;
  currency?: string;
  classification: string;
  explanation: string;
  verified?: boolean;
  transactions?: Transaction[];
}
export interface Proposal {
  id: string;
  invoice_ids: string[];
  transaction_ids: string[];
  matching_method: string;
  proposed_amount_cents: number;
  status: string;
  version: number;
  evidence: Evidence;
  verification: { valid: boolean; error: string | null };
}
export interface ExceptionCase {
  id: string;
  invoice_id: string | null;
  transaction_id: string | null;
  classification: string;
  evidence: Evidence;
  status: string;
}
export interface LedgerEntry {
  id: string;
  invoice_id: string;
  transaction_id: string;
  amount_cents: number;
  currency: string;
  entry_type: string;
  operation_id: string;
}
export interface AuditEvent {
  id: number;
  timestamp: string;
  actor: string;
  action: string;
  entity_id: string;
  entity_type: string;
  reason: string;
  correlation_id: string;
  previous_state: unknown;
  new_state: unknown;
}
export interface Overview {
  total_invoices: number;
  total_transactions: number;
  payment_volume: Record<string, number>;
  reconciled_amount: Record<string, number>;
  pending_approvals: number;
  unresolved_exceptions: number;
  matching_rate: number;
  status_counts: { name: string; count: number }[];
}
export interface Investigation {
  source: string;
  fallback_reason: string | null;
  recommendation: {
    summary: string;
    classification: string;
    uncertainty: string;
    recommended_action: string;
    supporting_invoice_ids: string[];
    supporting_transaction_ids: string[];
    difference_cents: number | null;
    requires_human_approval: boolean;
  };
  tool_trace: {
    tool: string;
    arguments: unknown;
    result?: unknown;
    error?: string;
  }[];
  verification: { valid: boolean; summary: string };
}
export interface Posting {
  operation_id: string;
  proposal_id: string;
  ledger_entries: LedgerEntry[];
  replayed: boolean;
  additional_entries: number;
}
export interface Data {
  overview: Overview;
  invoices: Invoice[];
  transactions: Transaction[];
  proposals: Proposal[];
  exceptions: ExceptionCase[];
  ledger: LedgerEntry[];
  audit: AuditEvent[];
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}). Check the submitted fields.`,
    );
  }
  return response.json();
}
export async function loadData(): Promise<Data> {
  const [
    overview,
    invoices,
    transactions,
    proposals,
    exceptions,
    ledger,
    audit,
  ] = await Promise.all([
    api<Overview>("/overview"),
    api<Invoice[]>("/invoices"),
    api<Transaction[]>("/transactions"),
    api<Proposal[]>("/proposals"),
    api<ExceptionCase[]>("/exceptions"),
    api<LedgerEntry[]>("/ledger"),
    api<AuditEvent[]>("/audit?limit=1000"),
  ]);
  return {
    overview,
    invoices,
    transactions,
    proposals,
    exceptions,
    ledger,
    audit,
  };
}
