"use client";

import {
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  ChartBarIcon,
  CheckCircleIcon,
  CircleStackIcon,
  GlobeAltIcon,
  InformationCircleIcon,
  MagnifyingGlassIcon,
  RectangleGroupIcon,
  ServerStackIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import React, { useMemo, useState } from "react";

import { PageHeader, StatusBadge } from "@/components/ui";
import { type SystemOverview, type TableStat } from "@/lib/product-api";

interface OverviewDashboardProps {
  overviewData?: SystemOverview | null;
  healthData?: any;
  facetsData?: any;
}

// Fallback snapshot database table statistics directly from verified PostgreSQL query
const DEFAULT_TABLE_STATS: TableStat[] = [
  { table_name: "commits", row_estimate: 776367, total_size: "217 MB", total_bytes: 227540992 },
  { table_name: "pull_requests", row_estimate: 713410, total_size: "187 MB", total_bytes: 196083712 },
  { table_name: "issues", row_estimate: 370511, total_size: "125 MB", total_bytes: 131072000 },
  { table_name: "catalog_repositories", row_estimate: 36851, total_size: "55 MB", total_bytes: 57671680 },
  { table_name: "repository_candidates", row_estimate: 43478, total_size: "31 MB", total_bytes: 32505856 },
  { table_name: "contributors", row_estimate: 5461, total_size: "16 MB", total_bytes: 16777216 },
  { table_name: "releases", row_estimate: 49333, total_size: "11 MB", total_bytes: 11534336 },
  { table_name: "repository_search_documents", row_estimate: 36851, total_size: "11 MB", total_bytes: 11534336 },
  { table_name: "metric_snapshots", row_estimate: 4635, total_size: "9840 kB", total_bytes: 10076160 },
  { table_name: "external_repository_activity", row_estimate: 75000, total_size: "9416 kB", total_bytes: 9641984 },
  { table_name: "repository_contributors", row_estimate: 78731, total_size: "6056 kB", total_bytes: 6201344 },
  { table_name: "collection_memberships", row_estimate: 43478, total_size: "5000 kB", total_bytes: 5120000 },
  { table_name: "external_evidence_items", row_estimate: 7601, total_size: "3840 kB", total_bytes: 3932160 },
  { table_name: "ingestion_jobs", row_estimate: 8704, total_size: "3496 kB", total_bytes: 3579904 },
  { table_name: "repository_change_events", row_estimate: 5696, total_size: "2768 kB", total_bytes: 2834432 },
  { table_name: "repository_embeddings", row_estimate: 200, total_size: "1744 kB", total_bytes: 1785856 },
  { table_name: "repository_sync_states", row_estimate: 5116, total_size: "744 kB", total_bytes: 761856 },
  { table_name: "repository_snapshots", row_estimate: 3555, total_size: "728 kB", total_bytes: 745472 },
  { table_name: "repository_source_snapshots", row_estimate: 1663, total_size: "720 kB", total_bytes: 737280 },
  { table_name: "ai_usage", row_estimate: 101, total_size: "632 kB", total_bytes: 647168 },
  { table_name: "repository_topics", row_estimate: 6917, total_size: "616 kB", total_bytes: 630784 },
  { table_name: "scout_assessments", row_estimate: 300, total_size: "616 kB", total_bytes: 630784 },
  { table_name: "repositories", row_estimate: 854, total_size: "608 kB", total_bytes: 622592 },
  { table_name: "repository_source_states", row_estimate: 1512, total_size: "584 kB", total_bytes: 598016 },
  { table_name: "repository_languages", row_estimate: 5880, total_size: "544 kB", total_bytes: 557056 },
  { table_name: "repository_external_links", row_estimate: 69, total_size: "104 kB", total_bytes: 106496 },
  { table_name: "collections", row_estimate: 1, total_size: "80 kB", total_bytes: 81920 },
  { table_name: "gh_archive_files", row_estimate: 47, total_size: "64 kB", total_bytes: 65536 },
  { table_name: "collector_state", row_estimate: 1, total_size: "56 kB", total_bytes: 57344 },
  { table_name: "query_embedding_cache", row_estimate: 2, total_size: "32 kB", total_bytes: 32768 },
];

const PAGES_DATA = [
  {
    id: "home",
    name: "Discover / Home",
    route: "/",
    category: "Discovery & Browse",
    purpose: "Main entrance and discovery portal for exploring trending, top-starred, and categorized open-source repositories.",
    contains: [
      "Hero search bar with fast keyword and phrase routing directly to /repositories",
      "Interactive Topic Picker with badges for curated ecosystem domains (AI, Rust, Web, Tools)",
      "Popular Repositories Grid showcasing 12 featured repositories with live star counts and badges",
      "Quick-access callout to personal Watchlist",
    ],
    dataSource: [
      "GET /api/v2/repositories?limit=12&sort=stars",
      "GET /api/v2/topics",
      "PostgreSQL tables: catalog_repositories, scout_assessments",
    ],
    volume: "Fetches top 12 featured repositories out of 36,851 catalog entries; ~25 curated topics.",
    extracted: [
      "Repository name, owner, stars count, primary language, license, brief description",
      "Computed selection score and Scout AI reason ('Why it surfaced') if available",
    ],
    sampleLink: "/",
  },
  {
    id: "topics",
    name: "Topics Directory",
    route: "/topics",
    category: "Discovery & Browse",
    purpose: "Taxonomy index categorizing repositories into technology domains, functional patterns, and language ecosystems.",
    contains: [
      "Curated topic category badges (AI & Agents, Web Frameworks, CLI Tools, Systems, Databases, Security)",
      "Real-time search & filter over topic slugs and keywords",
      "Repository count badges showing total projects matched per topic",
      "Direct jump links to individual topic deep-dives",
    ],
    dataSource: [
      "GET /api/v2/topics",
      "PostgreSQL tables: catalog_repositories (topics JSONB arrays and term matching)",
    ],
    volume: "~30 canonical topics categorizing over 10,000 repositories.",
    extracted: [
      "Topic slug, title, description, keywords array, and total aggregated repository count",
    ],
    sampleLink: "/topics",
  },
  {
    id: "topic-detail",
    name: "Topic Deep-Dive",
    route: "/topics/[slug]",
    category: "Discovery & Browse",
    purpose: "Filtered domain view showing all catalog repositories matching a specific topic pattern with language facet distributions.",
    contains: [
      "Domain title, description, and keywords tag list",
      "Language Facet Distribution Bar (e.g., Python 42%, TypeScript 31%, Rust 14%)",
      "Sorting controls (Relevance / Selection Score, Stars, Recently Updated)",
      "Project cards with matched keyword badges highlighted",
      "Cursor-based pagination controls",
    ],
    dataSource: [
      "GET /api/v2/topics/{slug}?sort=...&lang=...&cursor=...",
      "PostgreSQL tables: catalog_repositories, scout_assessments",
    ],
    volume: "20 to 50 repositories per page; aggregate counts across hundreds to thousands of matching repos.",
    extracted: [
      "Matched terms (highlighting which description or topic term caused the match), star count, pushed_at, primary_language",
    ],
    sampleLink: "/topics/artificial-intelligence",
  },
  {
    id: "repositories",
    name: "Repositories Catalog & Search",
    route: "/repositories",
    category: "Discovery & Browse",
    purpose: "The core search engine and multi-lens exploration catalog for finding and filtering open-source repositories.",
    contains: [
      "Hybrid Search input supporting trigram lexical match and 1536-dim vector semantic retrieval",
      "Multi-Lens Switcher: Developer Lens, Maintainer Lens, Investor Lens",
      "Faceted filter sidebar: Programming languages, Software licenses, Directory tier, Star count ranges",
      "Multi-dimensional sorting: Selection, Stars, Pushed recency, Promise, Activity, Growth, Health, Name",
      "Cursor pagination with total match counts",
    ],
    dataSource: [
      "GET /api/v2/repositories with search query parameters",
      "GET /api/v2/facets (aggregates language, license, tier distributions)",
      "POST /api/v2/search (hybrid RRF fusion search)",
      "PostgreSQL tables: catalog_repositories, repository_search_documents, repository_embeddings, scout_assessments",
    ],
    volume: "Indexes all 36,851 catalog repositories; returns pages of 50 items.",
    extracted: [
      "Developer lens: languages, license, topics, default branch, stars, forks",
      "Maintainer lens: maintenance score, open issues count, pushed date, hydration depth, risk flags",
      "Investor lens: popularity score, activity score, selection score, promise score, confidence rating",
    ],
    sampleLink: "/repositories",
  },
  {
    id: "repository-detail",
    name: "Repository Profile & Brief",
    route: "/repositories/[owner]/[name]",
    category: "Deep Intelligence",
    purpose: "Comprehensive forensic intelligence dossier and predictive trajectory brief for an individual repository.",
    contains: [
      "Header telemetry: stars, forks, watchers, open issues, license, language, default branch, archived badge",
      "Four Core Trajectory Scores (0-100): Health Score, Momentum Score, Delivery Score, Contributor Risk / Bus Factor",
      "180-day activity histogram (commits, merged PRs, closed issues, releases)",
      "Star history timeline and acceleration rate",
      "Top human contributors leaderboard with commit shares (excluding automated bots)",
      "External Evidence section: Hacker News threads, Reddit discussions, package downloads",
      "External Sources links: PyPI, npm, Crates.io, Go proxy, documentation",
      "Changelog & Repository Change Events chronological stream",
    ],
    dataSource: [
      "GET /api/v2/repositories/{owner}/{name}/brief",
      "GET /api/v2/repositories/{owner}/{name}/evidence",
      "GET /api/v2/repositories/{owner}/{name}/external-sources",
      "GET /api/v2/repositories/by-id/{id}/changes",
      "GET /api/v1/repositories/{owner}/{name}/metrics, /activity, /history, /contributors",
      "PostgreSQL tables: repositories, repository_snapshots, metric_snapshots, commits, pull_requests, issues, releases, contributors, external_evidence_items, repository_external_links, repository_change_events",
    ],
    volume: "Deeply hydrates up to 5,000 commits, 3,000 PRs, 3,000 issues, 500 releases, 200 contributors per repository.",
    extracted: [
      "Over 60 discrete metrics: median PR merge hours, issue closure cycle time, HHI / Gini contributor concentration, star velocity differential, commit cadence standard deviation, release interval regularity",
    ],
    sampleLink: "/repositories/torvalds/linux",
  },
  {
    id: "scout",
    name: "Scout Radar",
    route: "/scout",
    category: "Deep Intelligence",
    purpose: "AI-curated discovery feed surfacing breakout, high-velocity emerging open-source repositories before mainstream adoption.",
    contains: [
      "Scout Radar header highlighting 70% quantitative signals + 30% AI evaluation methodology",
      "Ecosystem / Language filter pills (TypeScript, Python, Rust, Go, etc.)",
      "Scout Cards detailing: AI 'Why It Surfaced' thesis, Promise Score (0-100), AI Confidence score (0.00-1.00), Risk Flags",
      "Traction metrics strip: commit cadence, recent releases count, star acceleration",
      "Pagination controls for continuous discovery",
    ],
    dataSource: [
      "GET /api/v2/scout?cursor=...&lang=...&min_score=...",
      "PostgreSQL tables: scout_assessments, catalog_repositories, repository_signal_snapshots",
      "AI Evaluation Engine: Google Gemini 3.8 Flash / OpenAI-compatible API running structured evaluation prompts",
    ],
    volume: "300 evaluated scout assessments active in database; rolling queue continuously scans promising candidates.",
    extracted: [
      "Promise score, confidence score, qualitative summary, why_it_surfaced explanation, identified risk flags, target personas, innovation flags",
    ],
    sampleLink: "/scout",
  },
  {
    id: "compare",
    name: "Comparative Analysis",
    route: "/compare",
    category: "Deep Intelligence",
    purpose: "Side-by-side benchmarking and comparative analysis between 2 to 3 competing open-source projects.",
    contains: [
      "Interactive multi-repository autocomplete picker",
      "Side-by-side metric comparison matrix: Health, Momentum, Delivery, Bus Factor",
      "Velocity & Activity benchmark: Commits, PR merge turnaround, Issue resolution time, Release intervals",
      "Community size & star history differential",
      "Advantage highlights indicating which tool leads in each category",
    ],
    dataSource: [
      "POST /api/v2/compare with repo list payload",
      "PostgreSQL tables: catalog_repositories, metric_snapshots, scout_assessments",
    ],
    volume: "Aggregates 2-3 repositories simultaneously on demand with full metric vectors.",
    extracted: [
      "Relative metric differentials, percentage variances, winning indicators per engineering dimension",
    ],
    sampleLink: "/compare",
  },
  {
    id: "watchlist",
    name: "Watchlist",
    route: "/watchlist",
    category: "Deep Intelligence",
    purpose: "Personal portfolio tracker for monitoring repositories of interest with alerts for momentum and version shifts.",
    contains: [
      "Pinned repository cards with real-time metrics",
      "Momentum status indicators (Accelerating, Steady, Decelerating)",
      "New release alerts and version change badges",
      "One-click pin/unpin and export/import watchlist capabilities",
    ],
    dataSource: [
      "Browser localStorage (client-side repository IDs)",
      "Hydrated via GET /api/v2/repositories batch query",
      "PostgreSQL tables: catalog_repositories, repository_change_events",
    ],
    volume: "Client collection (typically 5 to 50 repositories); instant offline cache with live background revalidation.",
    extracted: [
      "Current vs pinned baseline metrics, change events since bookmark date, recent release tags",
    ],
    sampleLink: "/watchlist",
  },
  {
    id: "rankings",
    name: "Rankings & Leaderboards",
    route: "/rankings",
    category: "Discovery & Browse",
    purpose: "Ranked leaderboards highlighting top-performing repositories across specific health and momentum dimensions.",
    contains: [
      "Leaderboard tables ranked by Health Score, Momentum Score, Delivery Speed, or Star Growth",
      "Language and ecosystem filter tabs",
      "Rank badges (#1, #2, #3, ...) with trend trajectory vectors",
      "Quick view of key contributing metric components",
    ],
    dataSource: [
      "GET /api/v2/repositories?sort=...&limit=50",
      "PostgreSQL tables: catalog_repositories",
    ],
    volume: "Top 50 to 100 repositories per category.",
    extracted: [
      "Rank ordinal, composite score breakdown, star trajectory, velocity delta",
    ],
    sampleLink: "/rankings",
  },
  {
    id: "collection",
    name: "Collection Ingestion",
    route: "/collection",
    category: "System & Operations",
    purpose: "Seed collection manager for tracking curated batches and repository candidate memberships.",
    contains: [
      "Seed collection title, description, and created timestamp",
      "Enrolled repositories listing with sync status badges",
      "Candidate priority tier and hydration state indicators",
      "Rejection reasons and triage status for disqualified candidates",
    ],
    dataSource: [
      "GET /api/v1/collections",
      "PostgreSQL tables: collections, collection_memberships, repository_candidates",
    ],
    volume: "1 primary collection tracking 43,478 member repositories.",
    extracted: [
      "Membership status, tier, sync timestamp, candidate rejection rationale",
    ],
    sampleLink: "/collection",
  },
  {
    id: "methodology",
    name: "Methodology & Governance",
    route: "/methodology",
    category: "System & Operations",
    purpose: "Public technical specification, mathematical formulas, and algorithmic transparency documentation.",
    contains: [
      "Core Governance FAQ: How 10,000 directory is selected (25% language diversity cap), RRF hybrid search (k=60), bus factor",
      "Mathematical scoring weights and formulas for Health, Momentum, Delivery, and Bus Factor",
      "Factual guardrails against AI hallucinations and bot-polluted activity",
    ],
    dataSource: [
      "Static documentation coupled with system configuration parameters",
    ],
    volume: "Comprehensive specification covering the entire 36,851 repository catalog.",
    extracted: [
      "Formula coefficients, normalization weights, window durations (30d/90d/180d/730d), and anti-gaming rules",
    ],
    sampleLink: "/methodology",
  },
  {
    id: "admin",
    name: "Admin Console",
    route: "/admin",
    category: "System & Operations",
    purpose: "Internal operational dashboard for controlling ingestion workers, scheduling jobs, and inspecting database telemetry.",
    contains: [
      "Secure authentication session controls (PBKDF2 SHA-256 hashed password, signed cookies, CSRF tokens)",
      "Collector job queue manager: Active, Queued, Failed, Completed, Cancelled jobs",
      "Operational commands: Trigger Scheduler Tick, Reconcile Collection, Reclassify Candidates, Maintenance",
      "Database row counts and collector configuration viewer",
      "Audit trail log recording all administrative actions, IP addresses, and timestamps",
    ],
    dataSource: [
      "GET /api/v1/admin/summary, /audit",
      "POST /api/v1/admin/commands/{command}, /jobs/{id}/cancel",
      "PostgreSQL tables: admin_audit_log, ingestion_jobs, collector_state, all core model tables",
    ],
    volume: "Manages 8,704 ingestion jobs and tracks 10+ core database model row counts in real time.",
    extracted: [
      "Worker lease state, attempt counts, execution latencies, error stack traces, administrative audit entries",
    ],
    sampleLink: "/admin",
  },
];

const DATA_SOURCES = [
  {
    name: "GitHub REST & GraphQL API",
    tag: "Primary Code & Social Graph",
    provider: "api.github.com",
    role: "Fetches repository metadata, commit histories, pull requests, issues, releases, and contributors.",
    details: [
      "Bounded hydration limits: Up to 5,000 commits, 3,000 pull requests, 3,000 issues, 500 releases, 200 contributors per repository",
      "Rate-limit safety reserve: Preserves at least 100 requests to avoid hard lockouts",
      "Paced requests: Configured with 0.15s interval between calls to avoid secondary rate limits",
      "Active refresh cycle: Ingested repositories refreshed every 24 hours; candidate pool probed every 168 hours (7 days)",
    ],
    metrics: "Stores ~776k commits, ~713k pull requests, ~370k issues, ~49k releases, ~5.4k contributors.",
  },
  {
    name: "GH Archive (data.gharchive.org)",
    tag: "Streaming Global Activity",
    provider: "data.gharchive.org",
    role: "Streams hourly compressed (.json.gz) archives of global GitHub events to detect early breakout repositories and star acceleration.",
    details: [
      "Processes WatchEvent (stars), ForkEvent, PushEvent, IssuesEvent, and PullRequestEvent",
      "Raw event payloads are streamed and compacted; never permanently stored to preserve disk space and privacy",
      "Aggregates hourly activity counters across thousands of repositories into external_repository_activity",
      "Configured for 6 hours back with 3 hours lag time; retention policy of 90 days",
    ],
    metrics: "47 archive hours processed; 75,000 external activity records compacted.",
  },
  {
    name: "External Package & Web Harvesters",
    tag: "Ecosystem Footprint",
    provider: "PyPI, npm, Crates.io, Go Proxy, Hacker News, Reddit",
    role: "Collects real-world developer discussions, package release updates, and cross-platform mentions.",
    details: [
      "Discovers package links and downloads across npm, PyPI, Crates.io, and Go modules",
      "Hacker News Algolia search API monitors launch threads (Show HN, Ask HN) and discussion sentiment",
      "Reddit programming subreddits monitor developer sentiment and adoption reports",
      "Captures license changes, release notes diffs, and homepage updates into repository_change_events",
    ],
    metrics: "7,601 external evidence items, 69 external registry links, 5,696 change events.",
  },
  {
    name: "AI & Vector Search Pipeline",
    tag: "Semantic Retrieval & Qualitative Evaluation",
    provider: "Google Gemini 3.8 Flash & OpenAI-Compatible Embeddings",
    role: "Generates semantic vector embeddings and structured evaluations with factual guardrails.",
    details: [
      "text-embedding-3-small generates 1536-dimensional vectors stored in pgvector for hybrid RRF search (k=60)",
      "Gemini 3.8 Flash generates qualitative Scout assessments: Problem tractability, innovation signals, risk detection",
      "Strict factual guardrails: Zero-tolerance for hallucinations; low confidence directly lowers Promise Score",
      "Budget-gated execution with daily request limits and concurrency throttles",
    ],
    metrics: "200 vector embeddings generated; 300 qualitative scout assessments; 101 AI usage logs.",
  },
  {
    name: "Autonomous Collector Daemon",
    tag: "Background Orchestration",
    provider: "Internal Worker (python -m app.cli collector)",
    role: "Coordinates automated scheduling, reconciliation, candidate discovery, and deep hydration.",
    details: [
      "Polls every 10 seconds for priority ingestion jobs (reconcile=250, deep=200, maintenance=150, candidate=100)",
      "Worker leasing with 30-minute lease timeouts prevents duplicate task processing",
      "Maintains candidate pool up to 50,000 repositories with 25% max language diversity cap",
      "Reclassifies candidates dynamically based on new activity and star thresholds",
    ],
    metrics: "8,704 ingestion jobs completed; 1 collector state record active.",
  },
];

const EXTRACTED_METRICS = [
  {
    category: "Repository Core Identity & Metadata",
    items: [
      { name: "full_name / owner / name", type: "string", desc: "Canonical GitHub path and repository naming." },
      { name: "description", type: "string | null", desc: "Repository headline purpose, sanitized and indexed for trigram search." },
      { name: "stars / forks / watchers", type: "integer", desc: "Community adoption and bookmark counts." },
      { name: "open_issues", type: "integer", desc: "Current open issue backlog." },
      { name: "primary_language", type: "string | null", desc: "Dominant programming language identified by Linguist." },
      { name: "license", type: "string | null", desc: "SPDX license identifier (e.g., MIT, Apache-2.0, GPL-3.0)." },
      { name: "topics", type: "string[]", desc: "Repository topic tags assigned on GitHub or extracted via discovery." },
      { name: "created_at / pushed_at / updated_at", type: "timestamp", desc: "Lifecycle timestamps tracking origin and latest code commit." },
    ],
  },
  {
    category: "Calculated Intelligence Scores (0 - 100)",
    items: [
      {
        name: "Community Health Score",
        type: "score (0-100)",
        desc: "Measures sustainability and community responsiveness. Formula: Active human contributors (20%), Issue resolution cycle (15%), Median PR merge hours (15%), PR acceptance rate (20%), Release cadence (10%), Human commit regularity (20%).",
      },
      {
        name: "Momentum Score",
        type: "score (0-100)",
        desc: "Detects accelerating software development and adoption. Formula: Star growth velocity (25%), Contributor expansion (20%), Commit acceleration (25%), PR velocity (20%), Release cadence (10%). Requires multi-point baseline snapshots.",
      },
      {
        name: "Delivery Velocity Score",
        type: "score (0-100)",
        desc: "Evaluates shipping discipline and production readiness. Combines release interval regularity (low standard deviation between versions) with rapid PR turnaround.",
      },
      {
        name: "Bus Factor & Contributor Risk",
        type: "risk metric (0 - 1)",
        desc: "Herfindahl-Hirschman Index (HHI) and Gini coefficient of human commit share across top 1 and top 3 authors. Highlights vulnerability to single-maintainer burnout. Automated bot accounts are filtered out.",
      },
      {
        name: "AI Scout Promise Score",
        type: "score (0-100)",
        desc: "Composite discovery metric for early-stage breakout tools. Combines 70% quantitative signals (freshness, commit cadence, release frequency) with 30% structured AI evaluation.",
      },
      {
        name: "Multi-Lens Projections",
        type: "projections",
        desc: "Developer Lens (code stack, license, topics, branch); Maintainer Lens (maintenance score, open issues, hydration depth, risk flags); Investor Lens (popularity, activity, selection, promise score, confidence).",
      },
    ],
  },
  {
    category: "Granular Git & Community Artifacts",
    items: [
      { name: "Commits", type: "entity", desc: "Commit SHA, author/committer login, human vs bot classification, message, timestamp, lines added/deleted." },
      { name: "Pull Requests", type: "entity", desc: "PR number, title, author, state, created_at, merged_at, closed_at, comments count, review turnaround." },
      { name: "Issues", type: "entity", desc: "Issue number, title, author, state, labels array, comments count, resolution cycle time in hours." },
      { name: "Releases", type: "entity", desc: "Tag name, published_at timestamp, release title, body length, prerelease and draft flags." },
      { name: "Contributors", type: "entity", desc: "Login, avatar URL, total commit count, first contribution date, latest contribution date." },
      { name: "External Activity", type: "compacted events", desc: "Hourly counts of WatchEvent, ForkEvent, PushEvent, IssuesEvent, PullRequestEvent from GH Archive." },
      { name: "External Evidence", type: "signals", desc: "Hacker News threads, Reddit posts, package registry downloads, and external documentation URLs." },
    ],
  },
];

export function OverviewDashboard({ overviewData, healthData, facetsData }: OverviewDashboardProps) {
  const [activeTab, setActiveTab] = useState<"pages" | "sources" | "database" | "metrics">("pages");
  const [pageCategoryFilter, setPageCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const tableStats = useMemo(() => {
    if (overviewData?.tables && overviewData.tables.length > 0) {
      return overviewData.tables;
    }
    return DEFAULT_TABLE_STATS;
  }, [overviewData]);

  const dbSizeFormatted = overviewData?.db_size || "709 MB";

  const totalRowCount = useMemo(() => {
    return tableStats.reduce((acc, row) => acc + (row.row_estimate || 0), 0);
  }, [tableStats]);

  const filteredPages = useMemo(() => {
    return PAGES_DATA.filter((p) => {
      const matchesCategory =
        pageCategoryFilter === "all" || p.category.toLowerCase().includes(pageCategoryFilter.toLowerCase());
      const query = searchQuery.trim().toLowerCase();
      const matchesQuery =
        !query ||
        p.name.toLowerCase().includes(query) ||
        p.route.toLowerCase().includes(query) ||
        p.purpose.toLowerCase().includes(query) ||
        p.contains.some((c) => c.toLowerCase().includes(query)) ||
        p.dataSource.some((s) => s.toLowerCase().includes(query));
      return matchesCategory && matchesQuery;
    });
  }, [pageCategoryFilter, searchQuery]);

  return (
    <main>
      <PageHeader
        eyebrow="INTERNAL / DEV DOSSIER"
        title="System Architecture & Data Overview"
        description="Comprehensive developer reference of all pages, data origins, ingestion pipelines, database storage volume (709 MB across 34 tables), and extracted telemetry metrics."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status="Internal Reference" tone="positive" />
            <span className="rounded border border-[#333333] bg-[#141414] px-2.5 py-1 font-mono text-[10px] text-[#9a9a9a]">
              PostgreSQL 16 + pgvector
            </span>
          </div>
        }
      />

      <div className="mx-auto max-w-[1600px] space-y-8 px-5 py-8 md:px-8 xl:px-10">
        {/* System Storage & Quantity KPI Strip */}
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div className="panel border border-[#222222] bg-[#0c0c0c] p-4">
            <div className="flex items-center justify-between text-[#646464]">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#9a9a9a]">Total DB Size</span>
              <CircleStackIcon className="size-4 text-[#ccf200]" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-[#ffffff]">{dbSizeFormatted}</div>
            <div className="mt-1 font-mono text-[10px] text-[#646464]">34 relational tables</div>
          </div>

          <div className="panel border border-[#222222] bg-[#0c0c0c] p-4">
            <div className="flex items-center justify-between text-[#646464]">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#9a9a9a]">Git Commits</span>
              <ChartBarIcon className="size-4 text-[#ccf200]" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-[#ffffff]">776,367</div>
            <div className="mt-1 font-mono text-[10px] text-[#646464]">217 MB storage footprint</div>
          </div>

          <div className="panel border border-[#222222] bg-[#0c0c0c] p-4">
            <div className="flex items-center justify-between text-[#646464]">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#9a9a9a]">Pull Requests</span>
              <ArrowPathIcon className="size-4 text-[#ccf200]" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-[#ffffff]">713,410</div>
            <div className="mt-1 font-mono text-[10px] text-[#646464]">187 MB turnaround telemetry</div>
          </div>

          <div className="panel border border-[#222222] bg-[#0c0c0c] p-4">
            <div className="flex items-center justify-between text-[#646464]">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#9a9a9a]">Catalog Repos</span>
              <RectangleGroupIcon className="size-4 text-[#ccf200]" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-[#ffffff]">36,851</div>
            <div className="mt-1 font-mono text-[10px] text-[#646464]">43.4k candidate pool</div>
          </div>

          <div className="panel border border-[#222222] bg-[#0c0c0c] p-4">
            <div className="flex items-center justify-between text-[#646464]">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#9a9a9a]">Directory Cohort</span>
              <CheckCircleIcon className="size-4 text-[#ccf200]" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-[#ffffff]">2,585</div>
            <div className="mt-1 font-mono text-[10px] text-[#646464]">525 deep hydrated</div>
          </div>

          <div className="panel border border-[#222222] bg-[#0c0c0c] p-4">
            <div className="flex items-center justify-between text-[#646464]">
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#9a9a9a]">GH Archive Events</span>
              <GlobeAltIcon className="size-4 text-[#ccf200]" />
            </div>
            <div className="mt-2 text-2xl font-bold font-mono text-[#ffffff]">75,000</div>
            <div className="mt-1 font-mono text-[10px] text-[#646464]">47 hours compacted</div>
          </div>
        </section>

        {/* Tab Selection Navigation */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#222222] pb-3">
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
            <button
              onClick={() => setActiveTab("pages")}
              className={`flex items-center gap-2 rounded-md px-3.5 py-2 font-semibold uppercase tracking-wider transition-colors ${
                activeTab === "pages"
                  ? "bg-[#ccf200] text-[#050505]"
                  : "border border-[#222222] bg-[#0c0c0c] text-[#9a9a9a] hover:bg-[#161616] hover:text-[#ffffff]"
              }`}
            >
              <RectangleGroupIcon className="size-4" />
              <span>Pages & Screens ({PAGES_DATA.length})</span>
            </button>

            <button
              onClick={() => setActiveTab("sources")}
              className={`flex items-center gap-2 rounded-md px-3.5 py-2 font-semibold uppercase tracking-wider transition-colors ${
                activeTab === "sources"
                  ? "bg-[#ccf200] text-[#050505]"
                  : "border border-[#222222] bg-[#0c0c0c] text-[#9a9a9a] hover:bg-[#161616] hover:text-[#ffffff]"
              }`}
            >
              <GlobeAltIcon className="size-4" />
              <span>Data Sources & Pipelines (5)</span>
            </button>

            <button
              onClick={() => setActiveTab("database")}
              className={`flex items-center gap-2 rounded-md px-3.5 py-2 font-semibold uppercase tracking-wider transition-colors ${
                activeTab === "database"
                  ? "bg-[#ccf200] text-[#050505]"
                  : "border border-[#222222] bg-[#0c0c0c] text-[#9a9a9a] hover:bg-[#161616] hover:text-[#ffffff]"
              }`}
            >
              <CircleStackIcon className="size-4" />
              <span>Database Storage ({tableStats.length} Tables)</span>
            </button>

            <button
              onClick={() => setActiveTab("metrics")}
              className={`flex items-center gap-2 rounded-md px-3.5 py-2 font-semibold uppercase tracking-wider transition-colors ${
                activeTab === "metrics"
                  ? "bg-[#ccf200] text-[#050505]"
                  : "border border-[#222222] bg-[#0c0c0c] text-[#9a9a9a] hover:bg-[#161616] hover:text-[#ffffff]"
              }`}
            >
              <SparklesIcon className="size-4" />
              <span>Extracted Metrics Dictionary</span>
            </button>
          </div>

          <div className="flex items-center gap-2 font-mono text-[11px] text-[#646464]">
            <span>Total Records:</span>
            <span className="font-bold text-[#e5e2e1]">{totalRowCount.toLocaleString()}</span>
          </div>
        </div>

        {/* TAB 1: ALL PAGES & SCREENS */}
        {activeTab === "pages" && (
          <div className="space-y-6">
            {/* Filter and Search Bar */}
            <div className="flex flex-col gap-3 rounded-lg border border-[#222222] bg-[#0c0c0c] p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1">
                <MagnifyingGlassIcon className="absolute left-3 top-2.5 size-4 text-[#646464]" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter pages by name, route, contents, or table..."
                  className="w-full rounded-md border border-[#222222] bg-[#050505] py-1.5 pl-9 pr-3 font-mono text-xs text-[#ffffff] placeholder:text-[#646464] focus:border-[#ccf200] focus:outline-none"
                />
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                {[
                  { id: "all", label: "All Pages" },
                  { id: "discovery", label: "Discovery" },
                  { id: "intelligence", label: "Intelligence" },
                  { id: "operations", label: "Operations" },
                ].map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setPageCategoryFilter(cat.id)}
                    className={`rounded px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider transition-colors ${
                      pageCategoryFilter === cat.id
                        ? "bg-[#ccf200] text-[#050505]"
                        : "border border-[#222222] bg-[#141414] text-[#9a9a9a] hover:text-[#ffffff]"
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Page Cards Grid */}
            <div className="grid gap-5 lg:grid-cols-2">
              {filteredPages.map((page, index) => (
                <div
                  key={page.id}
                  className="panel flex flex-col justify-between border border-[#222222] bg-[#0c0c0c] p-5 hover:border-[#333333]"
                >
                  <div className="space-y-4">
                    {/* Header */}
                    <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#1c1c1c] pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[11px] text-[#646464]">
                            #{String(index + 1).padStart(2, "0")}
                          </span>
                          <h3 className="text-lg font-bold text-[#ffffff]">{page.name}</h3>
                        </div>
                        <p className="mt-1 font-mono text-xs text-[#ccf200]">{page.route}</p>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="rounded border border-[#333333] bg-[#161616] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[#9a9a9a]">
                          {page.category}
                        </span>
                        <Link
                          href={page.sampleLink}
                          className="flex items-center gap-1 rounded border border-[#222222] bg-[#141414] px-2.5 py-1 font-mono text-[10px] font-semibold text-[#e5e2e1] transition-colors hover:border-[#ccf200] hover:text-[#ccf200]"
                        >
                          <span>Open</span>
                          <ArrowTopRightOnSquareIcon className="size-3" />
                        </Link>
                      </div>
                    </div>

                    {/* Purpose */}
                    <p className="text-xs leading-relaxed text-[#9a9a9a]">{page.purpose}</p>

                    {/* What it contains */}
                    <div className="space-y-1.5 rounded-md border border-[#1c1c1c] bg-[#080808] p-3">
                      <div className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[#ccf200]">
                        <InformationCircleIcon className="size-3.5" />
                        <span>What It Contains (UI & Flow)</span>
                      </div>
                      <ul className="space-y-1 pl-1">
                        {page.contains.map((item, i) => (
                          <li key={i} className="flex items-start gap-2 text-[11px] text-[#cccccc]">
                            <span className="text-[#646464]">•</span>
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Where data comes from */}
                    <div className="space-y-1.5 rounded-md border border-[#1c1c1c] bg-[#080808] p-3">
                      <div className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[#38bdf8]">
                        <ServerStackIcon className="size-3.5" />
                        <span>Where Data Comes From (Source APIs & Tables)</span>
                      </div>
                      <ul className="space-y-1 pl-1">
                        {page.dataSource.map((src, i) => (
                          <li key={i} className="font-mono text-[10px] text-[#9a9a9a]">
                            <code className="text-[#e5e2e1]">{src}</code>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* What we extract & Data volume */}
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-md border border-[#1c1c1c] bg-[#080808] p-2.5">
                        <span className="font-mono text-[9px] uppercase tracking-wider text-[#9a9a9a]">
                          Data Volume & Scale
                        </span>
                        <p className="mt-1 font-mono text-[10px] text-[#e5e2e1]">{page.volume}</p>
                      </div>

                      <div className="rounded-md border border-[#1c1c1c] bg-[#080808] p-2.5">
                        <span className="font-mono text-[9px] uppercase tracking-wider text-[#9a9a9a]">
                          Extracted Telemetry
                        </span>
                        <p className="mt-1 font-mono text-[10px] text-[#e5e2e1]">
                          {page.extracted.join(" • ")}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 2: DATA SOURCES & INGESTION PIPELINES */}
        {activeTab === "sources" && (
          <div className="space-y-6">
            <div className="rounded-lg border border-[#222222] bg-[#0c0c0c] p-5">
              <h2 className="text-xl font-bold text-[#ffffff]">Data Ingestion & Extraction Pipelines</h2>
              <p className="mt-1.5 text-xs text-[#9a9a9a]">
                RepoTrajectory combines structured GitHub API probing, continuous compressed event streaming from GH Archive,
                third-party ecosystem registries, and LLM semantic evaluation models.
              </p>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              {DATA_SOURCES.map((source, index) => (
                <div key={index} className="panel border border-[#222222] bg-[#0c0c0c] p-5">
                  <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#1c1c1c] pb-3">
                    <div>
                      <h3 className="text-base font-bold text-[#ffffff]">{source.name}</h3>
                      <p className="font-mono text-[11px] text-[#ccf200]">{source.provider}</p>
                    </div>
                    <span className="rounded border border-[#333333] bg-[#161616] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[#9a9a9a]">
                      {source.tag}
                    </span>
                  </div>

                  <p className="mt-3 text-xs text-[#9a9a9a]">{source.role}</p>

                  <div className="mt-4 space-y-2 rounded-md border border-[#1c1c1c] bg-[#080808] p-3">
                    <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[#ccf200]">
                      Pipeline Specifications & Guardrails
                    </span>
                    <ul className="space-y-1.5 pl-1">
                      {source.details.map((d, i) => (
                        <li key={i} className="flex items-start gap-2 text-[11px] text-[#cccccc]">
                          <span className="text-[#646464]">▸</span>
                          <span>{d}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="mt-3 flex items-center justify-between rounded border border-[#1c1c1c] bg-[#121212] px-3 py-2 font-mono text-[10px]">
                    <span className="text-[#646464]">Current Stored Volume:</span>
                    <span className="font-semibold text-[#ccf200]">{source.metrics}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: DATABASE & STORAGE INVENTORY */}
        {activeTab === "database" && (
          <div className="space-y-6">
            <div className="rounded-lg border border-[#222222] bg-[#0c0c0c] p-5">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                  <h2 className="text-xl font-bold text-[#ffffff]">PostgreSQL 16 Table Inventory</h2>
                  <p className="mt-1 text-xs text-[#9a9a9a]">
                    Total Database Footprint: <span className="font-bold text-[#ccf200]">{dbSizeFormatted}</span> across{" "}
                    <span className="font-bold text-[#ffffff]">{tableStats.length}</span> user tables with pgvector support.
                  </p>
                </div>
                <div className="rounded-md border border-[#222222] bg-[#141414] px-3 py-1.5 font-mono text-xs text-[#9a9a9a]">
                  Total Rows: <span className="font-bold text-[#ccf200]">{totalRowCount.toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* Storage Distribution Table */}
            <div className="overflow-hidden rounded-lg border border-[#222222] bg-[#0c0c0c]">
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-left font-mono text-xs">
                  <thead>
                    <tr className="border-b border-[#222222] bg-[#121212] text-[#9a9a9a]">
                      <th className="px-4 py-3 text-[10px] uppercase tracking-wider">#</th>
                      <th className="px-4 py-3 text-[10px] uppercase tracking-wider">Table Name</th>
                      <th className="px-4 py-3 text-[10px] uppercase tracking-wider">Live Row Count</th>
                      <th className="px-4 py-3 text-[10px] uppercase tracking-wider">Disk Size</th>
                      <th className="px-4 py-3 text-[10px] uppercase tracking-wider">Relative Share</th>
                      <th className="px-4 py-3 text-[10px] uppercase tracking-wider">Entity Type / Purpose</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1c1c1c]">
                    {tableStats.map((table, idx) => {
                      const maxBytes = tableStats[0]?.total_bytes || 227540992;
                      const pct = Math.max(2, Math.round(((table.total_bytes || 1000) / maxBytes) * 100));

                      let purpose = "Operational relation";
                      if (table.table_name === "commits") purpose = "Raw Git commit log (author, message, timestamps, lines added/deleted)";
                      else if (table.table_name === "pull_requests") purpose = "Pull request telemetry (merge latency, cycle times, review turnaround)";
                      else if (table.table_name === "issues") purpose = "Issue tracking (resolution turnaround, closed rates, label taxonomy)";
                      else if (table.table_name === "catalog_repositories") purpose = "Canonical and candidate repository directory with scores & metadata";
                      else if (table.table_name === "repository_candidates") purpose = "Rolling discovery candidate pool (50k limit) with qualification tiers";
                      else if (table.table_name === "contributors") purpose = "Global unique contributor profiles (login, avatar, bot classification)";
                      else if (table.table_name === "releases") purpose = "Software release version history (tags, dates, body length, cadence)";
                      else if (table.table_name === "repository_search_documents") purpose = "Trigram and full-text search indexes for fast lexical queries";
                      else if (table.table_name === "metric_snapshots") purpose = "Calculated point-in-time scores (Health, Momentum, Delivery, Bus factor)";
                      else if (table.table_name === "external_repository_activity") purpose = "Compacted hourly event counts streamed from GH Archive";
                      else if (table.table_name === "repository_contributors") purpose = "Per-repo contributor commit shares and bus-factor risk mapping";
                      else if (table.table_name === "external_evidence_items") purpose = "Third-party signals (Hacker News mentions, Reddit threads, packages)";
                      else if (table.table_name === "ingestion_jobs") purpose = "Background worker queue tasks and execution states";
                      else if (table.table_name === "repository_change_events") purpose = "Chronological audit stream of releases, license, and momentum shifts";
                      else if (table.table_name === "repository_embeddings") purpose = "1536-dimensional pgvector semantic embeddings for hybrid RRF search";
                      else if (table.table_name === "scout_assessments") purpose = "AI-evaluated Scout dossiers (Why surfaced, confidence, risk flags)";
                      else if (table.table_name === "ai_usage") purpose = "AI provider token usage and budget gate enforcement log";

                      return (
                        <tr key={table.table_name} className="transition-colors hover:bg-[#141414]">
                          <td className="px-4 py-2.5 text-[#646464]">{idx + 1}</td>
                          <td className="px-4 py-2.5 font-bold text-[#ffffff]">{table.table_name}</td>
                          <td className="px-4 py-2.5 text-[#e5e2e1]">
                            {table.row_estimate.toLocaleString()}
                          </td>
                          <td className="px-4 py-2.5 text-[#ccf200]">{table.total_size}</td>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-2">
                              <div className="h-1.5 w-24 rounded-full bg-[#1c1c1c]">
                                <div
                                  className="h-1.5 rounded-full bg-[#ccf200]"
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className="text-[10px] text-[#646464]">{pct}%</span>
                            </div>
                          </td>
                          <td className="px-4 py-2.5 font-sans text-xs text-[#9a9a9a]">{purpose}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: EXTRACTED FEATURES & METRICS DICTIONARY */}
        {activeTab === "metrics" && (
          <div className="space-y-6">
            <div className="rounded-lg border border-[#222222] bg-[#0c0c0c] p-5">
              <h2 className="text-xl font-bold text-[#ffffff]">Extracted Features & Analytics Dictionary</h2>
              <p className="mt-1.5 text-xs text-[#9a9a9a]">
                Formal schema definitions of what signals are extracted from raw sources versus computed via deterministic
                intelligence formulas and AI evaluation models.
              </p>
            </div>

            <div className="space-y-6">
              {EXTRACTED_METRICS.map((section, idx) => (
                <div key={idx} className="panel border border-[#222222] bg-[#0c0c0c] p-5">
                  <div className="border-b border-[#1c1c1c] pb-3">
                    <h3 className="text-base font-bold text-[#ffffff]">{section.category}</h3>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {section.items.map((item, itemIdx) => (
                      <div
                        key={itemIdx}
                        className="flex flex-col justify-between rounded-md border border-[#1c1c1c] bg-[#080808] p-3.5"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-xs font-bold text-[#ccf200]">{item.name}</span>
                            <span className="rounded bg-[#161616] px-1.5 py-0.5 font-mono text-[9px] text-[#646464]">
                              {item.type}
                            </span>
                          </div>
                          <p className="mt-2 text-xs leading-relaxed text-[#9a9a9a]">{item.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
