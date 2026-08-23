"use client";

import {
  ArrowPathIcon,
  ArrowRightStartOnRectangleIcon,
  BoltIcon,
  CheckCircleIcon,
  CircleStackIcon,
  ClockIcon,
  CommandLineIcon,
  ExclamationTriangleIcon,
  FunnelIcon,
  KeyIcon,
  LockClosedIcon,
  PlusIcon,
  ServerStackIcon,
  ShieldCheckIcon,
  TrashIcon,
} from "@heroicons/react/20/solid";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";

import { PageHeader, SectionHeader, StatusBadge } from "@/components/ui";
import { API, type CollectorJob, type CollectorOverview } from "@/lib/api";
import { compact, relativeDate } from "@/lib/format";

type AdminSession = {
  username: string;
  csrf_token: string;
  issued_at: string;
  expires_at: string;
};

type AdminSummary = {
  as_of: string;
  row_counts: Record<string, number>;
  collector: CollectorOverview;
  configuration: {
    github_token_configured: boolean;
    collector_enabled: boolean;
    collector_poll_seconds: number;
    candidate_limit: number;
    active_limit: number;
    active_refresh_hours: number;
    discovery_languages: string[];
    discovery_min_stars: number;
    gh_archive_enabled: boolean;
    gh_archive_hours_back: number;
    gh_archive_retention_days: number;
    github_rate_limit_reserve: number;
    admin_session_hours: number;
    secure_cookies: boolean;
  };
};

type AuditEntry = {
  id: number;
  occurred_at: string;
  actor: string;
  action: string;
  target: string | null;
  outcome: string;
  remote_address: string | null;
  details: Record<string, unknown>;
};

type AdminData = { summary: AdminSummary; jobs: CollectorJob[]; audit: AuditEntry[] };
type AuthState = "checking" | "signed-out" | "authenticated";

const number = new Intl.NumberFormat("en-US");

function label(value: string) {
  return value.replaceAll("_", " ").replaceAll(".", " · ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function bytes(value: number | null) {
  if (value == null) return "Unavailable";
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function jobTone(status: string) {
  if (status === "completed") return "positive";
  if (status === "failed") return "critical";
  if (status === "running") return "warning";
  return "neutral";
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.detail ?? `Request failed with status ${response.status}`);
  return payload as T;
}

export function AdminConsole() {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [session, setSession] = useState<AdminSession | null>(null);
  const [data, setData] = useState<AdminData | null>(null);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [repository, setRepository] = useState("");
  const [jobFilter, setJobFilter] = useState("all");

  const loadAdminData = useCallback(async () => {
    try {
      const [summary, jobs, audit] = await Promise.all([
        fetch(`${API}/api/v1/admin/summary`, { cache: "no-store" }).then(parseResponse<AdminSummary>),
        fetch(`${API}/api/v1/collector/jobs?limit=100`, { cache: "no-store" }).then(parseResponse<CollectorJob[]>),
        fetch(`${API}/api/v1/admin/audit?limit=100`, { cache: "no-store" }).then(parseResponse<AuditEntry[]>),
      ]);
      setData({ summary, jobs, audit });
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Administrative data is unavailable");
    }
  }, []);

  useEffect(() => {
    void fetch(`${API}/api/v1/admin/auth/session`, { cache: "no-store" })
      .then(async (response) => {
        if (response.status === 401 || response.status === 503) {
          setAuthState("signed-out");
          return;
        }
        const current = await parseResponse<AdminSession>(response);
        setSession(current);
        setAuthState("authenticated");
      })
      .catch(() => setAuthState("signed-out"));
  }, []);

  useEffect(() => {
    if (authState !== "authenticated") return;
    void loadAdminData();
    const timer = window.setInterval(() => void loadAdminData(), 30_000);
    return () => window.clearInterval(timer);
  }, [authState, loadAdminData]);

  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy("login");
    setError(null);
    try {
      const response = await fetch(`${API}/api/v1/admin/auth/login`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const current = await parseResponse<AdminSession>(response);
      setPassword("");
      setSession(current);
      setAuthState("authenticated");
    } catch (caught) {
      setPassword("");
      setError(caught instanceof Error ? caught.message : "Could not sign in");
    } finally {
      setBusy(null);
    }
  }

  async function mutate<T>(path: string, body?: unknown): Promise<T> {
    if (!session) throw new Error("Admin session is unavailable");
    const response = await fetch(`${API}/api/v1${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 401) {
      setSession(null);
      setData(null);
      setAuthState("signed-out");
    }
    return parseResponse<T>(response);
  }

  async function logout() {
    setBusy("logout");
    try {
      await mutate("/admin/auth/logout");
    } catch {
      // The local session is cleared even if the server is unavailable.
    } finally {
      setSession(null);
      setData(null);
      setAuthState("signed-out");
      setBusy(null);
    }
  }

  async function executeCommand(command: string) {
    if (["maintenance", "reclassify"].includes(command) && !window.confirm(`Run ${label(command)} now?`)) return;
    setBusy(`command-${command}`);
    setNotice(null);
    try {
      const result = await mutate<Record<string, unknown>>(`/admin/commands/${command}`);
      setNotice(`${label(command)} accepted · ${Object.entries(result).map(([key, value]) => `${label(key)} ${String(value)}`).join(" · ")}`);
      await loadAdminData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Could not run ${command}`);
    } finally {
      setBusy(null);
    }
  }

  async function queueRepository(event: FormEvent) {
    event.preventDefault();
    setBusy("queue");
    setNotice(null);
    try {
      const result = await mutate<{ job_id: number }>("/collector/repositories", { full_name: repository.trim() });
      setRepository("");
      setNotice(`Repository accepted as job #${result.job_id}.`);
      await loadAdminData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not queue repository");
    } finally {
      setBusy(null);
    }
  }

  async function jobAction(job: CollectorJob, action: "retry" | "cancel") {
    if (action === "cancel" && !window.confirm(`Cancel job #${job.id}?`)) return;
    setBusy(`${action}-${job.id}`);
    try {
      const path = action === "retry" ? `/collector/jobs/${job.id}/retry` : `/admin/jobs/${job.id}/cancel`;
      await mutate(path);
      setNotice(`Job #${job.id} ${action === "retry" ? "returned to the queue" : "cancelled"}.`);
      await loadAdminData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Could not ${action} job`);
    } finally {
      setBusy(null);
    }
  }

  const visibleJobs = useMemo(
    () => data?.jobs.filter((job) => jobFilter === "all" || job.status === jobFilter) ?? [],
    [data?.jobs, jobFilter],
  );

  if (authState === "checking") return <AdminLoading />;
  if (authState === "signed-out") return <AdminLogin username={username} password={password} busy={busy === "login"} error={error} onUsername={setUsername} onPassword={setPassword} onSubmit={login} />;
  if (!data || !session) return <AdminLoading error={error} />;

  const { summary, jobs, audit } = data;
  const queueDepth = (summary.collector.jobs.queued ?? 0) + (summary.collector.jobs.running ?? 0);
  const failedJobs = summary.collector.jobs.failed ?? 0;
  const rateRemaining = summary.collector.github_rate.remaining as number | undefined;

  return <main>
    <PageHeader eyebrow="Restricted operations" title="Administration" description="Authenticated control plane for collection, ingestion, queue recovery, storage, and policy operations." action={<div className="flex items-center gap-2"><button onClick={() => void loadAdminData()} className="button-secondary"><ArrowPathIcon className="size-4" />Refresh</button><button disabled={busy === "logout"} onClick={() => void logout()} className="button-primary"><ArrowRightStartOnRectangleIcon className="size-4" />Sign out</button></div>} />
    <div className="mx-auto max-w-[1440px] space-y-6 px-5 py-6 md:px-8 xl:px-10">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#697168] bg-[#101310] px-4 py-3"><div className="flex items-center gap-3"><div className="grid size-8 place-items-center rounded-full bg-[#101310] text-[#c7ff00]"><ShieldCheckIcon className="size-4" /></div><div><p className="text-xs font-semibold">Signed in as {session.username}</p><p className="mt-0.5 text-[11px] text-[#9ba399]">HttpOnly session · expires {relativeDate(session.expires_at)}</p></div></div><span className="font-mono text-[10px] uppercase tracking-[.1em] text-[#9ba399]">Privileged actions are audited</span></div>

      {(notice || error) && <div className={`flex items-start justify-between gap-4 rounded-md border px-4 py-3 text-sm ${error ? "border-[#f1f4ec] bg-[#171b17] text-[#f1f4ec]" : "border-[#c7ff00] bg-[#171b17] text-[#c7ff00]"}`}><span>{error ?? notice}</span><button onClick={() => { setNotice(null); setError(null); }} className="text-xs font-semibold">Dismiss</button></div>}

      <section className="grid gap-px overflow-hidden rounded-lg border border-[#343a34] bg-[#343a34] sm:grid-cols-2 xl:grid-cols-6">
        <Kpi label="Repositories" value={number.format(summary.row_counts.repositories ?? 0)} detail={`${number.format(summary.row_counts.metrics ?? 0)} metric snapshots`} />
        <Kpi label="Candidate universe" value={number.format(summary.row_counts.candidates ?? 0)} detail={`${summary.configuration.active_limit} active target`} />
        <Kpi label="Queue depth" value={number.format(queueDepth)} detail={`${summary.collector.jobs.running ?? 0} currently running`} />
        <Kpi label="Failed jobs" value={number.format(failedJobs)} detail={failedJobs ? "Operator review required" : "No terminal failures"} alert={failedJobs > 0} />
        <Kpi label="GitHub budget" value={rateRemaining == null ? "Pending" : number.format(rateRemaining)} detail={`${summary.configuration.github_rate_limit_reserve} request reserve`} />
        <Kpi label="Database" value={bytes(summary.collector.database_size_bytes)} detail={`${compact(summary.row_counts.external_activity ?? 0)} compact signal rows`} />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,.75fr)]">
        <section className="panel overflow-hidden"><SectionHeader title="Approved operations" description="Fixed server-side commands only. Arbitrary shell execution is intentionally unavailable." /><div className="grid gap-px bg-[#343a34] sm:grid-cols-2">
          <CommandCard icon={<BoltIcon className="size-5" />} title="Run scheduler" detail="Enqueue due Search, GH Archive, reconciliation, refresh, and maintenance work." command="schedule" busy={busy} onRun={executeCommand} />
          <CommandCard icon={<FunnelIcon className="size-5" />} title="Reconcile cohort" detail="Re-rank candidates and promote the strongest eligible software signals." command="reconcile" busy={busy} onRun={executeCommand} />
          <CommandCard icon={<CircleStackIcon className="size-5" />} title="Reclassify candidates" detail="Reapply the current transparent software eligibility rules to stored candidates." command="reclassify" busy={busy} onRun={executeCommand} />
          <CommandCard icon={<TrashIcon className="size-5" />} title="Run maintenance" detail="Apply configured retention to compact GH Archive projections and file records." command="maintenance" busy={busy} onRun={executeCommand} />
        </div></section>

        <section className="panel overflow-hidden"><SectionHeader title="Queue a repository" description="Pin an explicit GitHub repository for bounded full ingestion." /><form onSubmit={queueRepository} className="p-5"><label htmlFor="admin-repository" className="data-label">Owner/repository</label><input id="admin-repository" required autoComplete="off" pattern="[^/\s]+/[^/\s]+" value={repository} onChange={(event) => setRepository(event.target.value)} placeholder="fastapi/fastapi" className="mt-2 h-10 w-full rounded-md border border-[#697168] px-3 font-mono text-sm focus:border-[#c7ff00] focus:outline-none" /><button disabled={busy === "queue"} className="button-primary mt-3 w-full"><PlusIcon className="size-4" />{busy === "queue" ? "Queuing…" : "Queue ingestion"}</button><p className="mt-3 text-[11px] leading-4 text-[#70776f]">The request enters the durable worker queue. It does not execute inside the web request or grant write access to GitHub.</p></form></section>
      </div>

      <section className="panel overflow-hidden"><SectionHeader title="Work ledger" description={`${jobs.length} recent jobs with controlled retry and cancellation.`} action={<select value={jobFilter} onChange={(event) => setJobFilter(event.target.value)} className="h-8 rounded-md border border-[#343a34] bg-[#101310] px-2 text-xs font-medium"><option value="all">All states</option><option value="queued">Queued</option><option value="running">Running</option><option value="failed">Failed</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select>} /><div className="overflow-x-auto"><table className="w-full min-w-[980px]"><thead><tr className="border-b border-[#343a34] bg-[#101310]"><th className="table-head px-5 py-3">Job</th><th className="table-head px-4 py-3">State</th><th className="table-head px-4 py-3">Target</th><th className="table-head px-4 py-3">Attempts</th><th className="table-head px-4 py-3">Timing / error</th><th className="table-head px-4 py-3">Control</th></tr></thead><tbody>{visibleJobs.map((job) => <tr key={job.id} className="border-b border-[#343a34] last:border-0"><td className="px-5 py-3"><p className="font-mono text-xs font-semibold">#{job.id}</p><p className="mt-1 text-[10px] text-[#9ba399]">{label(job.job_type)} · priority {job.priority}</p></td><td className="px-4"><StatusBadge status={label(job.status)} tone={jobTone(job.status)} /></td><td className="max-w-[250px] px-4 font-mono text-[11px] text-[#b9c0b7]"><span className="line-clamp-2">{String(job.payload.full_name ?? job.candidate_id ?? job.repository_id ?? "System")}</span></td><td className="px-4 font-mono text-xs">{job.attempts} / {job.max_attempts}</td><td className="max-w-[330px] px-4 text-xs text-[#9ba399]"><span className="line-clamp-2">{job.last_error ?? jobTiming(job)}</span></td><td className="px-4"><div className="flex gap-3">{["failed", "cancelled"].includes(job.status) && <button disabled={busy === `retry-${job.id}`} onClick={() => void jobAction(job, "retry")} className="text-xs font-semibold text-[#c7ff00]">Retry</button>}{["queued", "failed"].includes(job.status) && <button disabled={busy === `cancel-${job.id}`} onClick={() => void jobAction(job, "cancel")} className="text-xs font-semibold text-[#f1f4ec]">Cancel</button>}</div></td></tr>)}</tbody></table>{visibleJobs.length === 0 && <div className="p-10 text-center text-sm text-[#9ba399]">No jobs match this state.</div>}</div></section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(350px,.8fr)]">
        <section className="panel overflow-hidden"><SectionHeader title="Storage inventory" description="Normalized row counts as of the latest administrative refresh." /><div className="grid gap-px bg-[#343a34] sm:grid-cols-2 lg:grid-cols-3">{Object.entries(summary.row_counts).map(([name, value]) => <div key={name} className="bg-[#101310] px-5 py-4"><p className="data-label">{label(name)}</p><p className="mt-2 font-mono text-xl font-semibold">{number.format(value)}</p></div>)}</div></section>
        <section className="panel overflow-hidden"><SectionHeader title="Runtime policy" description="Effective non-secret configuration. Credentials are never returned by this API." /><dl className="divide-y divide-[#343a34] px-5"><Policy label="Collector" value={summary.configuration.collector_enabled ? "Enabled" : "Disabled"} /><Policy label="GitHub credential" value={summary.configuration.github_token_configured ? "Configured" : "Missing"} /><Policy label="Refresh cadence" value={`${summary.configuration.active_refresh_hours} hours`} /><Policy label="Discovery floor" value={`${number.format(summary.configuration.discovery_min_stars)} stars`} /><Policy label="Archive lookback" value={`${summary.configuration.gh_archive_hours_back} hours`} /><Policy label="Retention" value={`${summary.configuration.gh_archive_retention_days} days`} /><Policy label="Session lifetime" value={`${summary.configuration.admin_session_hours} hours`} /></dl></section>
      </div>

      <section className="panel overflow-hidden"><SectionHeader title="Administrative audit" description="Append-only record of sign-ins and accepted privileged operations." /><div className="overflow-x-auto"><table className="w-full min-w-[800px]"><thead><tr className="border-b border-[#343a34] bg-[#101310]"><th className="table-head px-5 py-3">Time</th><th className="table-head px-4 py-3">Actor</th><th className="table-head px-4 py-3">Action</th><th className="table-head px-4 py-3">Target</th><th className="table-head px-4 py-3">Outcome</th></tr></thead><tbody>{audit.map((entry) => <tr key={entry.id} className="border-b border-[#343a34] last:border-0"><td className="px-5 py-3 text-xs text-[#9ba399]">{new Date(entry.occurred_at).toLocaleString()}</td><td className="px-4 font-mono text-xs">{entry.actor}</td><td className="px-4 text-xs font-semibold">{label(entry.action)}</td><td className="px-4 font-mono text-[11px] text-[#9ba399]">{entry.target ?? "—"}</td><td className="px-4"><StatusBadge status={label(entry.outcome)} tone={entry.outcome === "rejected" || entry.outcome === "failed" ? "critical" : "positive"} /></td></tr>)}</tbody></table></div></section>
    </div>
  </main>;
}

function AdminLogin({ username, password, busy, error, onUsername, onPassword, onSubmit }: { username: string; password: string; busy: boolean; error: string | null; onUsername: (value: string) => void; onPassword: (value: string) => void; onSubmit: (event: FormEvent) => void }) {
  return <main><PageHeader eyebrow="Restricted operations" title="Administration" description="Collection controls require a local administrative session." /><div className="mx-auto grid max-w-[1100px] gap-6 px-5 py-12 md:px-8 lg:grid-cols-[minmax(0,.9fr)_minmax(360px,.65fr)] xl:px-10"><section className="hairline-grid border border-[#343a34] bg-[#080a08] p-7 text-[#f1f4ec]"><div className="grid size-11 place-items-center border border-[#343a34] bg-[#f1f4ec]/10 text-[#c7ff00]"><ShieldCheckIcon className="size-5" /></div><p className="mt-6 text-[11px] font-semibold uppercase tracking-[.12em] text-slate-400">Operator boundary</p><h2 className="mt-2 text-2xl font-semibold tracking-[-.03em]">Privileged actions stay separate from research views.</h2><div className="mt-6 space-y-4"><SecurityPoint icon={<LockClosedIcon className="size-4" />} title="HttpOnly session" detail="The browser cannot read the signed session cookie." /><SecurityPoint icon={<KeyIcon className="size-4" />} title="CSRF and origin enforcement" detail="Every state change requires the session-bound token and an approved local origin." /><SecurityPoint icon={<CommandLineIcon className="size-4" />} title="Allowlisted commands" detail="The API exposes defined operations, never an arbitrary shell." /></div></section><form onSubmit={onSubmit} className="panel self-start overflow-hidden"><div className="border-b border-[#343a34] p-5"><div className="grid size-9 place-items-center rounded-md bg-[#171b17] text-[#c7ff00]"><LockClosedIcon className="size-4" /></div><h2 className="mt-4 text-lg font-semibold">Operator sign-in</h2><p className="mt-1 text-xs leading-5 text-[#9ba399]">Credentials are checked by the private API and never stored in browser persistence.</p></div><div className="space-y-4 p-5">{error && <div className="flex gap-2 border border-[#f1f4ec] bg-[#171b17] p-3 text-xs text-[#f1f4ec]"><ExclamationTriangleIcon className="mt-0.5 size-4 shrink-0" />{error}</div>}<label className="block"><span className="data-label">Username</span><input autoComplete="username" value={username} onChange={(event) => onUsername(event.target.value)} className="mt-2 h-10 w-full rounded-md border border-[#697168] px-3 text-sm focus:border-[#c7ff00] focus:outline-none" /></label><label className="block"><span className="data-label">Password</span><input required type="password" autoComplete="current-password" value={password} onChange={(event) => onPassword(event.target.value)} className="mt-2 h-10 w-full rounded-md border border-[#697168] px-3 text-sm focus:border-[#c7ff00] focus:outline-none" /></label><button disabled={busy} className="button-primary w-full"><ShieldCheckIcon className="size-4" />{busy ? "Verifying…" : "Enter administration"}</button><p className="text-center text-[10px] leading-4 text-[#70776f]">Five rejected attempts trigger a temporary local lockout.</p></div></form></div></main>;
}

function AdminLoading({ error }: { error?: string | null }) {
  return <main><PageHeader eyebrow="Restricted operations" title="Administration" description="Verifying the local operator session…" /><div className="mx-auto max-w-[900px] px-5 py-12 md:px-8"><div className="panel flex items-center gap-3 p-6 text-sm text-[#9ba399]">{error ? <ExclamationTriangleIcon className="size-5 text-[#f1f4ec]" /> : <ArrowPathIcon className="size-5 animate-spin text-[#c7ff00]" />}{error ?? "Checking signed session and administrative service."}</div></div></main>;
}

function SecurityPoint({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) { return <div className="flex gap-3"><div className="mt-0.5 grid size-7 shrink-0 place-items-center border border-[#343a34] bg-[#f1f4ec]/10 text-[#c7ff00]">{icon}</div><div><p className="text-sm font-semibold">{title}</p><p className="mt-1 text-xs leading-5 text-slate-400">{detail}</p></div></div>; }
function Kpi({ label: title, value, detail, alert = false }: { label: string; value: string; detail: string; alert?: boolean }) { return <div className="bg-[#101310] px-5 py-4"><p className="data-label">{title}</p><p className={`mt-2 font-mono text-2xl font-semibold tracking-[-0.04em] ${alert ? "text-[#f1f4ec]" : ""}`}>{value}</p><p className="mt-1 text-[11px] text-[#70776f]">{detail}</p></div>; }
function CommandCard({ icon, title, detail, command, busy, onRun }: { icon: React.ReactNode; title: string; detail: string; command: string; busy: string | null; onRun: (command: string) => void }) { const running = busy === `command-${command}`; return <motion.article whileHover={{ x: 4 }} className="data-scan bg-[#101310] p-5"><div className="flex items-start justify-between gap-4"><div className="grid size-9 place-items-center border border-[#343a34] bg-[#171b17] text-[#c7ff00]">{icon}</div><button disabled={running} onClick={() => onRun(command)} className="button-secondary h-8 px-3 text-xs">{running ? "Running…" : "Execute"}</button></div><h3 className="mt-4 text-sm font-black uppercase">{title}</h3><p className="mt-1.5 text-xs leading-5 text-[#9ba399]">{detail}</p></motion.article>; }
function Policy({ label: title, value }: { label: string; value: string }) { return <div className="flex items-center justify-between gap-4 py-3.5"><dt className="text-xs text-[#9ba399]">{title}</dt><dd className="text-right font-mono text-xs font-semibold">{value}</dd></div>; }
function jobTiming(job: CollectorJob) { if (!job.started_at) return `Scheduled ${relativeDate(job.scheduled_for)}`; if (!job.finished_at) return job.status === "running" ? "In progress" : "Awaiting completion"; const seconds = Math.max(0, (new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000); return seconds < 60 ? `${seconds.toFixed(1)} seconds` : `${(seconds / 60).toFixed(1)} minutes`; }
