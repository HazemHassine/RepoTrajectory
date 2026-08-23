"use client";

import {
  ArrowPathIcon,
  ArrowRightIcon,
  BoltIcon,
  CheckIcon,
  CircleStackIcon,
  ClockIcon,
  CloudArrowDownIcon,
  FunnelIcon,
  LockClosedIcon,
  ServerStackIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";

import { PageHeader, ScoreBar, SectionHeader, StatusBadge } from "@/components/ui";
import {
  API,
  type Candidate,
  type CollectionRecord,
  type CollectorOverview,
} from "@/lib/api";
import { compact, relativeDate } from "@/lib/format";

type ConsoleData = {
  overview: CollectorOverview;
  collections: CollectionRecord[];
  trending: Candidate[];
};

type CohortView = "all" | "libraries" | "tools";

const number = new Intl.NumberFormat("en-US");

function bytes(value: number | null) {
  if (value == null) return "Unavailable";
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function CollectorConsole() {
  const [data, setData] = useState<ConsoleData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cohortView, setCohortView] = useState<CohortView>("all");

  const load = useCallback(async () => {
    try {
      const [overview, collections, trending] = await Promise.all([
        fetch(`${API}/api/v1/collector/overview`, { cache: "no-store" }).then(assertJson),
        fetch(`${API}/api/v1/collections`, { cache: "no-store" }).then(assertJson),
        fetch(`${API}/api/v1/trending?limit=100`, { cache: "no-store" }).then(assertJson),
      ]);
      setData({ overview, collections, trending });
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Collector API unavailable");
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!data) {
    return <main><PageHeader eyebrow="Data operations" title="Collection control" description="Loading collector state…" /><div className="mx-auto max-w-[1440px] px-5 py-10 md:px-8 xl:px-10"><div className="panel p-10 text-sm text-[#9ba399]">{error ?? "Connecting to the collection service."}</div></div></main>;
  }

  const { overview, collections, trending } = data;
  const collection = collections[0];
  const totalCandidates = Object.values(overview.tiers).reduce((sum, value) => sum + value, 0);
  const queueDepth = (overview.jobs.queued ?? 0) + (overview.jobs.running ?? 0);
  const rateRemaining = overview.github_rate.remaining;
  const visibleTrending = trending.filter((candidate) => {
    if (cohortView === "libraries") return ["library", "framework"].includes(candidate.classification);
    if (cohortView === "tools") return candidate.classification === "developer_tool";
    return true;
  });

  return <main>
    <PageHeader
      eyebrow="Data operations"
      title="Collection control"
      description="A durable intake pipeline for discovering, qualifying, and refreshing the open-source universe without storing the public event firehose."
      action={<div className="flex items-center gap-2"><button onClick={() => void load()} className="button-secondary"><ArrowPathIcon className="size-4" />Refresh</button><Link href="/admin" className="button-primary"><LockClosedIcon className="size-4" />Administration</Link></div>}
    />
    <div className="mx-auto max-w-[1440px] space-y-6 px-5 py-6 md:px-8 xl:px-10">
      {error && <div className="flex items-center justify-between border border-[#f1f4ec] bg-[#171b17] px-4 py-3 text-sm text-[#f1f4ec]"><span>{error}</span><button onClick={() => setError(null)} className="font-mono text-[10px] font-bold uppercase">Dismiss</button></div>}

      <section className="grid gap-px overflow-hidden rounded-lg border border-[#343a34] bg-[#343a34] sm:grid-cols-2 xl:grid-cols-6">
        <Kpi label="Candidate universe" value={number.format(totalCandidates)} detail={`${number.format(overview.classifications.unclassified ?? 0)} awaiting metadata`} />
        <Kpi label="Active cohort" value={number.format(overview.tiers.active ?? 0)} detail={`Target ${collection?.active_limit ?? "—"}`} />
        <Kpi label="Fully hydrated" value={number.format(overview.hydrated_repositories)} detail="Historical entities stored" />
        <Kpi label="Queue depth" value={number.format(queueDepth)} detail={overview.oldest_queued_at ? `Oldest ${relativeDate(overview.oldest_queued_at)}` : "Queue clear"} />
        <Kpi label="Public events scanned" value={compact(overview.archive_events_processed)} detail={`${overview.archive_hours_processed} archive hours`} />
        <Kpi label="Database footprint" value={bytes(overview.database_size_bytes)} detail={`${number.format(overview.external_activity_rows)} compact event rows`} />
      </section>

      <section className="panel overflow-hidden">
        <SectionHeader title="Collection runway" description="The inexpensive filters run before REST hydration; arrows show the direction of evidence, not a batch dependency." action={<StatusBadge status={queueDepth ? `${queueDepth} work items` : "Queue clear"} tone={queueDepth ? "warning" : "positive"} />} />
        <div className="signal-grid p-5 md:p-7">
          <div className="grid items-stretch gap-3 lg:grid-cols-[1fr_28px_1fr_28px_1fr_28px_1fr]">
            <Stage index="01" icon={<CloudArrowDownIcon className="size-5" />} title="Discover" value={compact(overview.archive_events_processed)} detail="GH Archive events streamed and folded; GitHub Search adds established software." />
            <PipelineArrow />
            <Stage index="02" icon={<FunnelIcon className="size-5" />} title="Qualify" value={number.format((overview.classifications.library ?? 0) + (overview.classifications.framework ?? 0) + (overview.classifications.developer_tool ?? 0) + (overview.classifications.software ?? 0))} detail={`${number.format((overview.classifications.learning_resource ?? 0) + (overview.classifications.template ?? 0))} resources and templates withheld.`} />
            <PipelineArrow />
            <Stage index="03" icon={<BoltIcon className="size-5" />} title="Rank" value={number.format(overview.tiers.active ?? 0)} detail="Seven-day adoption and collaboration percentiles define the active cohort." />
            <PipelineArrow />
            <Stage index="04" icon={<CircleStackIcon className="size-5" />} title="Hydrate" value={number.format(overview.hydrated_repositories)} detail="Bounded history, daily snapshots, and incremental refreshes enter PostgreSQL." />
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(330px,.8fr)]">
        <section className="panel overflow-hidden">
          <SectionHeader title="Active discovery cohort" description="Current promotion order. A provisional label means the seven-day GH Archive baseline is still accumulating." action={<div className="flex items-center gap-3"><div className="inline-flex rounded-md border border-[#343a34] bg-[#101310] p-0.5">{([['all','All software'],['libraries','Libraries'],['tools','Dev tools']] as [CohortView,string][]).map(([value,title]) => <button key={value} onClick={() => setCohortView(value)} className={`rounded px-2.5 py-1 text-[11px] font-semibold ${cohortView === value ? "bg-[#080a08] text-[#f1f4ec]" : "text-[#9ba399]"}`}>{title}</button>)}</div><Link href="/repositories" className="text-xs font-semibold text-[#c7ff00]">Hydrated →</Link></div>} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px]">
              <thead><tr className="border-b border-[#343a34] bg-[#101310]"><th className="table-head px-5 py-3">Repository</th><th className="table-head px-4 py-3">Class</th><th className="table-head px-4 py-3">7d signals</th><th className="table-head px-4 py-3">Discovery score</th><th className="table-head px-4 py-3">State</th></tr></thead>
              <tbody>{visibleTrending.slice(0, 15).map((candidate) => {
                const signals = candidate.trend_components;
                const signalCount = (signals.star_events ?? 0) + (signals.fork_events ?? 0) + (signals.pull_request_events ?? 0) + (signals.release_events ?? 0);
                return <tr key={candidate.id} className="border-b border-[#343a34] last:border-0 hover:bg-[#101310]"><td className="max-w-[330px] px-5 py-3.5"><p className="font-mono text-[13px] font-semibold">{candidate.full_name}</p><p className="mt-1 truncate text-xs text-[#9ba399]">{candidate.description ?? "Metadata pending"}</p></td><td className="px-4"><span className="rounded bg-[#171b17] px-2 py-1 text-[11px] font-semibold text-[#9ba399]">{label(candidate.classification)}</span></td><td className="px-4"><b className="font-mono text-xs">{number.format(signalCount)}</b><span className="block text-[10px] text-[#70776f]">adoption + collaboration</span></td><td className="px-4"><ScoreBar value={candidate.trend_score} compact /></td><td className="px-4"><StatusBadge status={signals.provisional ? "Baseline pending" : candidate.repository_id ? "Hydrated" : "Queued"} tone={signals.provisional ? "neutral" : candidate.repository_id ? "positive" : "warning"} /></td></tr>;
              })}</tbody>
            </table>
            {visibleTrending.length === 0 && <div className="p-10 text-center text-sm text-[#9ba399]">No active repositories match this cohort view yet.</div>}
          </div>
        </section>

        <div className="space-y-6">
          <section className="panel overflow-hidden">
            <SectionHeader title="Policy envelope" description="Configured limits make collection cost predictable." />
            <dl className="divide-y divide-[#343a34] px-5">
              <Policy label="Active set" value={number.format(collection?.active_limit ?? 0)} />
              <Policy label="Candidate ceiling" value={number.format(collection?.candidate_limit ?? 0)} />
              <Policy label="Refresh cadence" value={`${collection?.refresh_hours ?? 0} hours`} />
              <Policy label="Archive projection" value={`${overview.archive_hours_processed} hours · ${bytes(overview.archive_compressed_bytes)} read`} />
              <Policy label="GitHub core budget" value={rateRemaining == null ? "Awaiting request" : `${number.format(rateRemaining)} remaining`} />
              <Policy label="Last completed work" value={relativeDate(overview.last_completed_at)} />
            </dl>
          </section>

          <section className="overflow-hidden rounded-lg border border-[#343a34] bg-[#101310]">
            <div className="p-5"><div className="grid size-9 place-items-center rounded-md bg-[#101310] text-[#c7ff00] shadow-sm"><LockClosedIcon className="size-4" /></div><h3 className="mt-4 text-sm font-semibold">Controls are access-restricted</h3><p className="mt-2 text-xs leading-5 text-[#9ba399]">Queue management, manual ingestion, retries, maintenance, and policy commands have moved behind the authenticated administration boundary.</p><Link href="/admin" className="mt-4 inline-flex text-xs font-semibold text-[#c7ff00]">Open administration →</Link></div>
          </section>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <TrustNote icon={<ServerStackIcon className="size-5" />} title="Compact by construction" detail="GH Archive JSON is streamed, folded into hourly repository counters, and discarded. Raw public event payloads never enter PostgreSQL." />
        <TrustNote icon={<ClockIcon className="size-5" />} title="Bounded historical cost" detail="Initial hydration has fixed commit, release, and contributor horizons. Later runs advance from per-resource watermarks." />
        <TrustNote icon={<CheckIcon className="size-5" />} title="Evidence before score" detail="Zero signals remain zero and missing history remains provisional. Popularity cannot impersonate observed growth." />
      </section>
    </div>
  </main>;
}

async function assertJson(response: Response) {
  if (!response.ok) throw new Error(`Collector API returned ${response.status}`);
  return response.json();
}

function Kpi({ label: title, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="bg-[#101310] px-5 py-4"><p className="data-label">{title}</p><p className="mt-2 font-mono text-2xl font-semibold tracking-[-0.04em]">{value}</p><p className="mt-1 text-[11px] text-[#70776f]">{detail}</p></div>;
}

function Stage({ index, icon, title, value, detail }: { index: string; icon: React.ReactNode; title: string; value: string; detail: string }) {
  return <motion.article whileHover={{ y: -5, borderColor: "#c7ff00" }} className="data-scan relative min-h-[178px] border border-[#697168] bg-[#101310] p-5"><span className="absolute right-4 top-4 font-mono text-[10px] font-bold tracking-[.15em] text-[#9ba399]">{index}</span><div className="grid size-9 place-items-center border border-[#343a34] bg-[#171b17] text-[#c7ff00]">{icon}</div><div className="mt-5 flex items-end justify-between gap-3"><h3 className="text-sm font-black uppercase">{title}</h3><strong className="font-mono text-xl tracking-[-0.04em]">{value}</strong></div><p className="mt-3 text-xs leading-5 text-[#9ba399]">{detail}</p></motion.article>;
}

function PipelineArrow() {
  return <div className="hidden items-center justify-center text-[#70776f] lg:flex"><ArrowRightIcon className="size-4" /></div>;
}

function Policy({ label: title, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-4 py-3.5"><dt className="text-xs text-[#9ba399]">{title}</dt><dd className="text-right font-mono text-xs font-semibold">{value}</dd></div>;
}

function TrustNote({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) {
  return <motion.article whileHover={{ x: 4 }} className="panel flex gap-4 p-5"><div className="grid size-9 shrink-0 place-items-center border border-[#343a34] bg-[#171b17] text-[#c7ff00]">{icon}</div><div><h3 className="text-sm font-black uppercase">{title}</h3><p className="mt-1.5 text-xs leading-5 text-[#9ba399]">{detail}</p></div></motion.article>;
}
