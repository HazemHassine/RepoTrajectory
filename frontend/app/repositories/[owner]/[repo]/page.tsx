import {
  ArrowLeftIcon,
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import { ProjectBrief } from "@/components/project-brief";
import { productApi, type Brief } from "@/lib/product-api";

import { ActivityChart, StarChart } from "@/components/charts";
import {
  ChangeBadge,
  EmptyState,
  ScoreBar,
  SectionHeader,
  StatusBadge,
  WindowControl,
} from "@/components/ui";
import {
  api,
  type Activity,
  type History,
  type Metric,
  type Repo,
  type UnifiedProfile,
} from "@/lib/api";
import { compact, duration, getNumber, percent, relativeDate } from "@/lib/format";

export default async function RepositoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ owner: string; repo: string }>;
  searchParams: Promise<{ window?: string }>;
}) {
  const { owner, repo } = await params;
  const requested = Number((await searchParams).window ?? 30);
  const window = [30, 90, 365].includes(requested) ? requested : 30;

  let profile: UnifiedProfile | null = null;
  let brief: Brief | null = null;
  try { brief = await productApi.brief(owner, repo); } catch { /* Visible degraded state below. */ }
  let activity: Activity[] = [];
  let history: History[] = [];
  let v1Repo: Repo | null = null;
  let v1Metric: Metric | null = null;

  try {
    profile = await api.v2.repository(owner, repo);
  } catch {
    // Fallback to v1 if v2 profile not yet in catalog
  }

  // Also try fetching v1 deep metrics if available
  try {
    const [r, m, a, h] = await Promise.all([
      api.repo(owner, repo),
      api.metrics(owner, repo, window),
      api.activity(owner, repo, window === 365 ? 52 : window === 90 ? 24 : 12),
      api.history(owner, repo),
    ]);
    v1Repo = r;
    v1Metric = m;
    activity = a;
    history = h;
  } catch {
    // Deep telemetry may not be ingested yet
  }

  if (!profile && !v1Repo) {
    return (
      <main>
        <div className="mx-auto max-w-[1100px] px-5 py-16">
          <EmptyState
            title={`No analysis found for ${owner}/${repo}`}
            description="Ensure the repository exists in GitHub and has been indexed in the catalog or ingested via the CLI."
          />
        </div>
      </main>
    );
  }

  // Synthesize catalog details from v2 profile or v1 repo
  const repoName = profile?.catalog.name ?? v1Repo!.name;
  const repoOwner = profile?.catalog.owner ?? v1Repo!.owner;
  const fullName = profile?.catalog.full_name ?? v1Repo!.full_name;
  const description = profile?.catalog.description ?? v1Repo?.description;
  const stars = profile?.catalog.stars ?? v1Repo!.stars;
  const forks = profile?.catalog.forks ?? v1Repo!.forks;
  const openIssues = profile?.catalog.open_issues ?? v1Repo?.open_issues ?? 0;
  const language = profile?.catalog.primary_language ?? v1Repo?.primary_language;
  const license = profile?.catalog.license ?? v1Repo?.license;
  const defaultBranch = profile?.catalog.default_branch ?? v1Repo?.default_branch ?? "main";
  const pushedDate = profile?.catalog.pushed_at ?? v1Repo?.pushed_at;
  const isDeep = profile?.catalog.is_deep || !!v1Repo;
  const topics: string[] = profile?.catalog.topics ?? [];
  const classification = profile?.catalog.classification ?? "General Software";
  const classificationConfidence = profile?.catalog.classification_confidence;

  const scout = profile?.scout;
  const deepEvidence = profile?.deep_evidence;
  const metric: Metric | undefined = (deepEvidence?.metric ?? v1Metric) || undefined;

  // Metric derivations
  const momentumScore = metric?.momentum_score ?? null;
  const healthScore = metric?.health_score ?? null;
  const busFactorRisk = metric?.bus_factor_risk ?? null;
  const confidenceScore = getNumber(metric, "data_quality", "confidence_score");
  const commitCount = getNumber(metric, "velocity", "commits");
  const commitChange = getNumber(metric, "velocity", "commit_change");
  const automationShare = getNumber(metric, "velocity", "automation_share");
  const topContributorShare = getNumber(metric, "concentration", "top_1_share");
  const medianPrMergeHours = getNumber(metric, "responsiveness", "median_pr_merge_hours");

  return (
    <main>
      {/* Profile Header */}
      <header className="border-b border-[#222222] bg-[#0c0c0c]">
        <div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 xl:px-10">
          <div className="flex items-center justify-between gap-4">
            <Link
              href="/repositories"
              className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-[#9a9a9a] hover:text-[#ffffff]"
            >
              <ArrowLeftIcon className="size-3.5" /> Back to Repositories
            </Link>
            <WindowControl active={window} />
          </div>

          <div className="mt-6 flex flex-wrap items-start justify-between gap-6">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-bold tracking-tight text-[#ffffff] sm:text-4xl md:text-5xl">
                  {fullName}
                </h1>
                <StatusBadge
                  status={isDeep ? "Deep Analysis" : "Standard Index"}
                  tone={isDeep ? "positive" : "neutral"}
                />
                {scout?.promise_score != null && (
                  <span className="inline-flex items-center gap-1.5 rounded border border-[#ccf200]/40 bg-[#ccf200]/10 px-2.5 py-1 font-mono text-[10px] font-bold text-[#ccf200]">
                    <SparklesIcon className="size-3" /> Scout Promise: {scout.promise_score}/100
                  </span>
                )}
              </div>

              <p className="mt-3 text-sm leading-6 text-[#9a9a9a]">
                {description || "No repository description provided."}
              </p>

              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 font-mono text-xs text-[#9a9a9a]">
                <span className="text-[#ccf200] font-semibold">{language ?? "Language unknown"}</span>
                <span>{license ?? "No license detected"}</span>
                <span>Default: {defaultBranch}</span>
                <a
                  href={`https://github.com/${fullName}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-semibold text-[#ccf200] hover:underline"
                >
                  GitHub <ArrowTopRightOnSquareIcon className="size-3" />
                </a>
              </div>
            </div>

            {/* Quick Stat Counter Boxes */}
            <div className="grid grid-cols-3 gap-6 font-mono">
              <div className="border border-[#222222] bg-[#090909] p-3 text-center">
                <span className="data-label block text-[8px]">Stars</span>
                <b className="mt-1 block text-lg text-[#ffffff]">{compact(stars)}</b>
              </div>
              <div className="border border-[#222222] bg-[#090909] p-3 text-center">
                <span className="data-label block text-[8px]">Forks</span>
                <b className="mt-1 block text-lg text-[#ffffff]">{compact(forks)}</b>
              </div>
              <div className="border border-[#222222] bg-[#090909] p-3 text-center">
                <span className="data-label block text-[8px]">Open Items</span>
                <b className="mt-1 block text-lg text-[#ffffff]">{compact(openIssues)}</b>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* 5-Section Layout */}
      <div className="mx-auto max-w-[1440px] space-y-8 px-5 py-8 md:px-8 xl:px-10">
        {brief ? <ProjectBrief brief={brief} /> : <p role="alert" className="panel p-5">Project brief unavailable. Collected analytics are available below; reload to retry.</p>}
        <details className="space-y-8">
          <summary className="cursor-pointer text-xl font-semibold">Advanced repository analytics & methodology</summary>
        {/* ============================================================ */}
        {/* SECTION 1: OVERVIEW & PROJECT PURPOSE */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            title="1. Overview & Project Purpose"
            description="Project taxonomy, domain classification, and verified purpose excerpt."
          />
          <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
            {/* README Excerpt / Summary */}
            <div className="panel p-6">
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-[#ccf200]">
                Project Purpose &amp; Documentation Summary
              </h3>
              <div className="mt-3 rounded border border-[#222222] bg-[#050505] p-4 text-xs leading-relaxed text-[#9a9a9a]">
                {profile?.readme_excerpt ? (
                  <p className="whitespace-pre-wrap line-clamp-6">{profile.readme_excerpt}</p>
                ) : (
                  <p className="italic text-[#646464]">
                    {description || "No detailed readme excerpt captured. Standard catalog metadata applies."}
                  </p>
                )}
              </div>

              {/* Topics & Classification */}
              <div className="mt-5 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[9px] uppercase tracking-wider text-[#646464]">
                    Classification:
                  </span>
                  <span className="border border-[#ccf200]/40 bg-[#161616] px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-[#ccf200]">
                    {classification}
                  </span>
                  <span className="font-mono text-[9px] text-[#646464]">
                    ({classificationConfidence == null ? "Unknown" : `${Math.round(classificationConfidence * 100)}% heuristic confidence`})
                  </span>
                </div>

                {topics.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {topics.map((t) => (
                      <span
                        key={t}
                        className="border border-[#222222] bg-[#111111] px-2 py-0.5 font-mono text-[9px] text-[#9a9a9a]"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Scale & Metadata Specs */}
            <div className="panel divide-y divide-[#222222]">
              <div className="p-4">
                <p className="data-label">Telemetry Coverage</p>
                <p className="mt-1 font-mono text-sm font-bold text-[#ffffff]">
                  {isDeep ? "Deep Analysis" : "Standard Index"}
                </p>
                <p className="mt-1 text-[11px] text-[#9a9a9a]">
                  {isDeep
                    ? "Full telemetry: commits, pull requests, cycle times, issue flows, and contributor distributions."
                    : "Tracked in catalog with periodic signal snapshots."}
                </p>
              </div>
              <div className="p-4">
                <p className="data-label">Last Push / Freshness</p>
                <p className="mt-1 font-mono text-sm text-[#ccf200]">
                  {relativeDate(pushedDate)}
                </p>
              </div>
              <div className="p-4">
                <p className="data-label">License &amp; Branch</p>
                <p className="mt-1 font-mono text-xs text-[#ffffff]">
                  {license || "None specified"} · Default branch: {defaultBranch}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/* SECTION 2: ACTIVITY & ADOPTION */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            title="2. Activity & Adoption"
            description="Development velocity, commit cadence, star trajectory, and fork-to-star ratio."
          />
          <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
            {/* Weekly Activity or Telemetry Chart */}
            <div className="panel overflow-hidden p-4">
              <p className="font-mono text-xs font-bold text-[#ffffff]">
                Development Activity Over Time ({window}-Day Window)
              </p>
              <div className="mt-4">
                {activity.length > 0 ? (
                  <ActivityChart data={activity} />
                ) : (
                  <div className="flex h-52 items-center justify-center border border-dashed border-[#222222] text-center font-mono text-xs text-[#646464]">
                    Weekly commit bars require deep-cohort ingestion.
                  </div>
                )}
              </div>
            </div>

            {/* Observed Growth & Trajectory */}
            <div className="panel overflow-hidden p-4">
              <p className="font-mono text-xs font-bold text-[#ffffff]">
                Observed Star Growth Trajectory
              </p>
              <div className="mt-4">
                {history.length > 1 ? (
                  <StarChart data={history} />
                ) : (
                  <div className="flex h-52 flex-col items-center justify-center border border-dashed border-[#222222] p-4 text-center font-mono text-xs text-[#9a9a9a]">
                    <span className="font-bold text-[#ffffff]">Snapshot baseline established</span>
                    <p className="mt-2 text-[11px] text-[#646464]">
                      Current count: {compact(stars)} stars. Next scheduled snapshot will render trajectory line.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Activity Metrics Grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="panel p-4">
              <p className="data-label">Human Commits</p>
              <p className="mt-2 font-mono text-2xl font-bold text-[#ffffff]">
                {compact(commitCount)}
              </p>
              <div className="mt-2">
                <ChangeBadge value={commitChange} />
              </div>
            </div>
            <div className="panel p-4">
              <p className="data-label">Automation Share</p>
              <p className="mt-2 font-mono text-2xl font-bold text-[#ffffff]">
                {automationShare != null ? `${Math.round(automationShare * 100)}%` : "—"}
              </p>
              <p className="mt-1 font-mono text-[10px] text-[#646464]">Bot accounts isolated</p>
            </div>
            <div className="panel p-4">
              <p className="data-label">Fork Adoption Ratio</p>
              <p className="mt-2 font-mono text-2xl font-bold text-[#ccf200]">
                {stars > 0 ? `${((forks / stars) * 100).toFixed(1)}%` : "—"}
              </p>
              <p className="mt-1 font-mono text-[10px] text-[#646464]">Forks / Stars</p>
            </div>
            <div className="panel p-4">
              <p className="data-label">Commit Cadence</p>
              <p className="mt-2 font-mono text-sm font-bold text-[#ffffff]">
                {commitCount == null ? "Unknown" : commitCount > 20 ? "High Frequency" : commitCount > 0 ? "Moderate" : "No commits observed"}
              </p>
              <p className="mt-1 font-mono text-[10px] text-[#646464]">Within active observation window</p>
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/* SECTION 3: COMMUNITY & MAINTAINER HEALTH */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            title="3. Community & Maintainer Health"
            description="Contributor resilience, PR merge latency, issue resolution cycle, and delivery health."
          />
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Health Score */}
            <div className="panel p-5">
              <p className="data-label">Community Health Score</p>
              <div className="mt-4">
                <ScoreBar value={healthScore} tone="green" />
              </div>
              <p className="mt-3 text-xs leading-5 text-[#9a9a9a]">
                Aggregates active human contributors, cycle times, PR merge efficiency, and release cadences.
              </p>
            </div>

            {/* Bus Factor Concentration */}
            <div className="panel p-5">
              <p className="data-label">Bus Factor &amp; Concentration Risk</p>
              <div className="mt-4">
                <ScoreBar
                  value={busFactorRisk}
                  tone={busFactorRisk != null && busFactorRisk >= 70 ? "red" : busFactorRisk != null && busFactorRisk >= 40 ? "amber" : "blue"}
                />
              </div>
              <p className="mt-3 text-xs leading-5 text-[#9a9a9a]">
                {topContributorShare != null
                  ? `Top contributor authored ${(topContributorShare * 100).toFixed(0)}% of recent human commits.`
                  : "Assessed via commit author distribution; excludes bot and sync identities."}
              </p>
            </div>

            {/* Responsiveness */}
            <div className="panel p-5">
              <p className="data-label">PR Merge Cycle Latency</p>
              <p className="mt-3 font-mono text-2xl font-bold text-[#ccf200]">
                {medianPrMergeHours != null ? duration(medianPrMergeHours) : "—"}
              </p>
              <p className="mt-3 text-xs leading-5 text-[#9a9a9a]">
                Median turnaround time from pull request open to merge among recent non-automated PRs.
              </p>
            </div>
          </div>

          {/* Top Contributors Distribution if available */}
          {deepEvidence?.top_contributors && deepEvidence.top_contributors.length > 0 && (
            <div className="panel p-5">
              <p className="font-mono text-xs font-bold uppercase tracking-wider text-[#ffffff]">
                Core Contributor Distribution
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {deepEvidence.top_contributors.slice(0, 8).map((c, idx) => (
                  <div
                    key={c.login}
                    className="flex items-center gap-3 border border-[#222222] bg-[#0c0c0c] p-2.5"
                  >
                    <span className="font-mono text-[9px] text-[#646464]">
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-xs font-bold text-[#ffffff]">{c.login}</p>
                      <p className="font-mono text-[9px] text-[#9a9a9a]">
                        {compact(c.contributions)} commits
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* ============================================================ */}
        {/* SECTION 4: INVESTOR MOMENTUM & RISKS */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            title="4. Investor Momentum & Risks"
            description="Momentum acceleration, Scout AI promise evaluation, corporate backing signals, and risk flags."
          />
          <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
            {/* Momentum & Scout Card */}
            <div className="space-y-4">
              <div className="panel p-5">
                <p className="data-label">Momentum Score</p>
                <div className="mt-4">
                  <ScoreBar value={momentumScore} tone="blue" />
                </div>
                <p className="mt-3 text-xs text-[#9a9a9a]">
                  Evaluates velocity acceleration against the repo's historical baseline and portfolio cohort.
                </p>
              </div>

              {scout && (
                <div className="panel border border-[#ccf200]/40 bg-[#0c0c0c] p-5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] font-black uppercase tracking-wider text-[#ccf200]">
                      Scout Early Detection Assessment
                    </span>
                    <span className="font-mono text-xs font-bold text-[#ccf200]">
                      Promise: {scout.promise_score}/100
                    </span>
                  </div>
                  <div className="mt-3 text-xs leading-relaxed text-[#ffffff]">
                    <p className="font-semibold text-[#ccf200]">Reasoning:</p>
                    <p className="mt-1">{scout.why_it_surfaced}</p>
                  </div>
                  <div className="mt-3 flex gap-4 font-mono text-[10px] text-[#9a9a9a]">
                    <span>Quant: {scout.quantitative_score?.toFixed(1) ?? "—"}</span>
                    <span>AI: {scout.ai_score?.toFixed(1) ?? "—"}</span>
                    <span>Evidence coverage: {scout.confidence == null ? "Unknown" : `${Math.round(scout.confidence * 100)}%`}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Corporate Backing Signals & Risk Ledger */}
            <div className="panel p-5 space-y-4">
              <div>
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-[#ffffff]">
                  Corporate Backing &amp; Sponsorship Signals
                </h3>
                <div className="mt-2 text-xs leading-5 text-[#9a9a9a]">
                  {fullName.includes("/") && (
                    <div className="flex items-center gap-2">
                      <ShieldCheckIcon className="size-4 text-[#ccf200]" />
                      <span>
                        Organization Namespace:{" "}
                        <strong className="text-[#ffffff]">{fullName.split("/")[0]}</strong>
                      </span>
                    </div>
                  )}
                  <p className="mt-1">
                    Domain email commitments and sponsor links are cross-referenced during catalog synchronization.
                  </p>
                </div>
              </div>

              <div className="border-t border-[#222222] pt-4">
                <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-[#ffffff]">
                  Identified Risks &amp; Red Flags
                </h3>
                {scout?.risk_flags && scout.risk_flags.length > 0 ? (
                  <div className="mt-2 space-y-2">
                    {scout.risk_flags.map((risk, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2 border border-[#e5534b]/30 bg-[#1a0f0f] p-2.5 text-xs text-[#f87171]"
                      >
                        <ExclamationTriangleIcon className="size-4 shrink-0 text-[#e5534b] mt-0.5" />
                        <span>{risk}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 flex items-center gap-2 font-mono text-xs text-[#9a9a9a]">
                    <CheckCircleIcon className="size-4 text-[#ccf200]" />
                    No critical risk flags recorded in current evaluation.
                  </p>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================ */}
        {/* SECTION 5: EVIDENCE & PROVENANCE */}
        {/* ============================================================ */}
        <section className="space-y-4">
          <SectionHeader
            title="5. Evidence, Provenance & Methodology"
            description="Data ingestion freshness, event sampling bounds, AI evaluator model identity, and reproducibility."
          />
          <div className="panel divide-y divide-[#222222] overflow-hidden">
            {/* Provenance Details */}
            <div className="grid divide-y divide-[#222222] sm:grid-cols-4 sm:divide-x sm:divide-y-0 p-5 font-mono">
              <div>
                <span className="data-label block">Evidence coverage</span>
                <b className="mt-2 block text-xl text-[#ccf200]">{confidenceScore == null ? "Unknown" : `${confidenceScore}%`}</b>
              </div>
              <div className="sm:pl-5">
                <span className="data-label block">Ingestion Source</span>
                <b className="mt-2 block text-sm text-[#ffffff]">GitHub GraphQL + REST v3</b>
              </div>
              <div className="sm:pl-5">
                <span className="data-label block">Historical Snapshots</span>
                <b className="mt-2 block text-xl text-[#ffffff]">
                  {history.length || (deepEvidence?.snapshot_history?.length ?? "Unknown")}
                </b>
              </div>
              <div className="sm:pl-5">
                <span className="data-label block">Telemetry Tier</span>
                <b className="mt-2 block text-sm text-[#ffffff]">
                  {isDeep ? "Deep Ingestion" : "Catalog Tracked"}
                </b>
              </div>
            </div>

            {/* AI Model Identity & Provenance Metadata */}
            <div className="bg-[#090909] p-5 text-xs leading-relaxed text-[#9a9a9a]">
              <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[10px]">
                <span>
                  Evaluator Identity:{" "}
                  <strong className="text-[#ffffff]">
                    {scout?.model_identity || "RepoTrajectory-ScoutEvaluator-DeterministicFallback"}
                  </strong>
                </span>
                <span>
                  Search capability: <strong className="text-[#ffffff]">See search result retrieval status</strong>
                </span>
              </div>
              <p className="mt-3">
                Methodology disclosure: All scores are derived strictly from observed events and metadata.
                Historical growth rates require two or more point-in-time snapshots and are never backfilled or
                reconstructed from third-party approximations. Forks and archived repositories are excluded from Scout
                promise scoring.
              </p>
            </div>
          </div>
        </section>
        </details>
      </div>
    </main>
  );
}
