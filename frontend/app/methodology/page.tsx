import {
  BoltIcon,
  CheckCircleIcon,
  CircleStackIcon,
  ClockIcon,
  CpuChipIcon,
  ExclamationTriangleIcon,
  FunnelIcon,
  SparklesIcon,
} from "@heroicons/react/20/solid";

import { PageHeader, SectionHeader } from "@/components/ui";

const coreQuestions = [
  [
    "How is the canonical 10,000 repository directory selected?",
    "Available",
    "Selected from a rolling candidate pool of up to 50,000 repositories using composite activity, star growth, release recency, and an enforced 25% maximum language diversity cap to ensure representation across all ecosystems.",
  ],
  [
    "How does the AI Scout discover under-the-radar projects?",
    "Available",
    "Autonomous discovery engine combining 70% quantitative signals (velocity, commit cadence, release frequency, issue resolution) with 30% structured AI evaluation. Supports low-star projects (e.g., 6 stars) while strictly filtering out forks, archived repos, and mirrors.",
  ],
  [
    "How is hybrid search performed across 10,000 repositories?",
    "Available",
    "Queries execute in parallel across PostgreSQL trigram/fulltext indices and 1536-dimensional pgvector cosine embeddings. Results are merged via Reciprocal-Rank Fusion (RRF, k=60) with automatic deterministic fallback if the vector engine is offline.",
  ],
  [
    "Which projects are gaining momentum?",
    "Available with baseline",
    "Evaluates star and contributor growth plus human commit, PR, and release acceleration. Growth remains provisional until snapshots span the window.",
  ],
  [
    "Which communities are healthy and active?",
    "Available",
    "Combines active human contributors, delivery cadence, PR merge latency, resolved-item cycle times, and stable release cadence.",
  ],
  [
    "Which projects depend on very few contributors?",
    "Available as proxy",
    "Reports top-one and top-three human commit share and Herfindahl-Hirschman Index (HHI). Known bot accounts and automated synchronizers are excluded.",
  ],
  [
    "How do the Developer, Maintainer, and Investor lenses differ?",
    "Available",
    "Developer lens prioritizes activity, dependencies, and documentation; Maintainer lens highlights response latencies, PR backlogs, and bus-factor risk; Investor lens tracks growth velocity, momentum, and corporate backing signals.",
  ],
  [
    "How are low-star, high-velocity repos treated?",
    "Available",
    "RepoTrajectory does not enforce arbitrary minimum star thresholds for Scout discovery. A repository with 6 stars and consistent commits and releases can achieve high promise scores.",
  ],
];

const scoringWeights = [
  {
    name: "AI Scout Promise Score",
    target: "Which emerging repositories show early breakout potential?",
    formula: "70% Quantitative Signals + 30% Hosted AI Evaluator",
    breakdown:
      "Quantitative: Freshness (20%), Commit Cadence (20%), Adoption/Stars (15%), Topic Breadth (15%), Release Recency (10%), Maintenance (10%), Evidence Quality (10%). AI Evaluator: Code structure, problem tractability, innovation signals, risk detection.",
    guardrails:
      "Zero-tolerance hallucination rules. Low confidence down-ranks promise score. Forks, archived repos, and inactive mirrors are strictly disqualified.",
  },
  {
    name: "Momentum Score",
    target: "Is repository activity accelerating over time?",
    formula: "Star velocity + Contributor growth + Human commit acceleration",
    breakdown:
      "Star growth rate (25%), contributor expansion (20%), commit acceleration (25%), PR velocity (20%), release cadence (10%).",
    guardrails:
      "Growth metrics are marked provisional until multiple point-in-time snapshots span the requested window.",
  },
  {
    name: "Community Health Score",
    target: "Can the community sustainably respond and ship software?",
    formula: "Human contributors + Cycle times + Merge efficiency",
    breakdown:
      "Active human contributors (20%), issue resolution cycle (15%), median PR merge hours (15%), PR acceptance rate (20%), releases (10%), human commits (20%).",
    guardrails:
      "Cycle times measure actual issue/PR completion, not simple bot automated triage or first acknowledgment.",
  },
];

export default function Methodology() {
  return (
    <main>
      <PageHeader
        title="Methodology & Governance"
        description="RepoTrajectory makes all metric definitions, formulas, and data boundaries explicit. Scores are deterministic heuristics, AI evaluations run under factual guardrails, and missing evidence is transparently reported."
      />

      <div className="mx-auto max-w-[1200px] space-y-8 px-5 py-8 md:px-8 xl:px-10">
        {/* Core Architecture Highlights */}
        <section className="grid gap-4 md:grid-cols-3">
          <div className="panel border border-[#222222] bg-[#0c0c0c] p-5">
            <div className="flex items-center gap-2 text-[#ccf200]">
              <CircleStackIcon className="size-5" />
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider">
                Repository Directory
              </h3>
            </div>
            <p className="mt-3 text-xs leading-5 text-[#9a9a9a]">
              Curated from a 50,000 rolling candidate pool. Max 25% language diversity cap prevents
              any single ecosystem from dominating the catalog. 500 repos receive deep weekly telemetry.
            </p>
          </div>

          <div className="panel p-5 border border-[#222222] bg-[#0c0c0c]">
            <div className="flex items-center gap-2 text-[#ccf200]">
              <SparklesIcon className="size-5" />
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider">
                AI Scout Engine
              </h3>
            </div>
            <p className="mt-3 text-xs leading-5 text-[#9a9a9a]">
              70% quantitative pre-ranking + 30% structured AI evaluation. Discovers high-promise projects
              regardless of star scale (low-star repos like 6-star projects supported).
            </p>
          </div>

          <div className="panel p-5 border border-[#222222] bg-[#0c0c0c]">
            <div className="flex items-center gap-2 text-[#ccf200]">
              <BoltIcon className="size-5" />
              <h3 className="font-mono text-xs font-bold uppercase tracking-wider">
                Hybrid Search (RRF k=60)
              </h3>
            </div>
            <p className="mt-3 text-xs leading-5 text-[#9a9a9a]">
              PostgreSQL trigram &amp; fulltext lexical search fused with 1536-dimensional pgvector cosine
              similarity via Reciprocal-Rank Fusion.
            </p>
          </div>
        </section>

        {/* Questions Answered */}
        <section className="panel overflow-hidden">
          <SectionHeader
            title="Core Questions & Capabilities"
            description="Operational coverage across repository intelligence, search, and early detection."
          />
          <div className="divide-y divide-[#222222]">
            {coreQuestions.map(([question, status, detail], index) => (
              <div
                key={question}
                className="grid gap-3 px-5 py-4 md:grid-cols-[36px_1fr_180px_1.4fr] md:items-start"
              >
                <span className="font-mono text-xs text-[#646464]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3 className="text-sm font-semibold text-[#ffffff]">{question}</h3>
                <Coverage status={status} />
                <p className="text-xs leading-5 text-[#9a9a9a]">{detail}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Scoring Frameworks */}
        <section className="space-y-4">
          <SectionHeader
            title="Composite Scoring Specifications"
            description="Weightings, mathematical formulas, and boundary conditions."
          />
          <div className="grid gap-6 lg:grid-cols-3">
            {scoringWeights.map((item) => (
              <article key={item.name} className="panel flex flex-col justify-between p-6">
                <div>
                  <p className="eyebrow">Scoring Model</p>
                  <h3 className="mt-2 text-base font-bold text-[#ffffff]">{item.name}</h3>
                  <p className="mt-1 text-xs text-[#9a9a9a]">{item.target}</p>

                  <div className="my-4 h-px bg-[#222222]" />

                  <p className="font-mono text-[10px] font-black uppercase text-[#ccf200]">
                    {item.formula}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-[#9a9a9a]">{item.breakdown}</p>
                </div>

                <div className="mt-6 rounded border border-[#222222] bg-[#090909] p-3 text-[11px] leading-4 text-[#ccf200]">
                  <p className="font-mono font-bold uppercase text-[9px] text-[#646464] mb-1">
                    Guardrails &amp; Constraints:
                  </p>
                  {item.guardrails}
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Data Integrity Principles */}
        <section className="panel p-6">
          <h2 className="section-title">Data Integrity Contract</h2>
          <div className="mt-4 grid gap-6 text-xs leading-5 text-[#9a9a9a] md:grid-cols-3">
            <div>
              <b className="block font-mono text-sm text-[#ffffff] mb-1">Raw Is Sacred</b>
              <p>
                GitHub REST and GraphQL entity payloads are recorded immutably. Derived scores and AI
                assessments reference stored provenance snapshots with SHA-256 verification hashes.
              </p>
            </div>
            <div>
              <b className="block font-mono text-sm text-[#ffffff] mb-1">Human vs Bot Isolation</b>
              <p>
                Automated release bots, synchronizers, and GitHub Actions identities are isolated from human
                commit velocity and author concentration metrics.
              </p>
            </div>
            <div>
              <b className="block font-mono text-sm text-[#ffffff] mb-1">No Hallucinated History</b>
              <p>
                Observed star curves require distinct chronological snapshots. RepoTrajectory never fabricates
                historical trends or interpolates missing data without explicit disclosure.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function Coverage({ status }: { status: string }) {
  const pending = status.includes("Collecting");
  const partial = status.includes("provisional") || status.includes("proxy") || status.includes("baseline");
  const Icon = pending ? ClockIcon : partial ? ExclamationTriangleIcon : CheckCircleIcon;
  return (
    <span
      className={`inline-flex w-fit items-center gap-1.5 font-mono text-[11px] font-semibold ${
        pending ? "text-[#9a9a9a]" : partial ? "text-[#ccf200]" : "text-[#ccf200]"
      }`}
    >
      <Icon className="size-3.5" />
      {status}
    </span>
  );
}
