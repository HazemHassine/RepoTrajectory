import {
  ArrowRightIcon,
  CheckCircleIcon,
  CodeBracketIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  FireIcon,
  MagnifyingGlassIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UserGroupIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";

import { EmptyState, PageHeader, SectionHeader } from "@/components/ui";
import { api, type CatalogRepo, type Facets, type ScoutFeedItem } from "@/lib/api";
import { compact, relativeDate } from "@/lib/format";

export default async function Home() {
  let directoryItems: CatalogRepo[] = [];
  let scoutPicks: ScoutFeedItem[] = [];
  let facets: Facets | null = null;
  let unavailable = false;

  try {
    const [repoRes, scoutRes, facetRes] = await Promise.all([
      api.v2.repositories({ limit: 6, sort: "selection" }),
      api.v2.scout({ limit: 4, min_promise: 55 }),
      api.v2.facets(),
    ]);
    directoryItems = repoRes.items;
    scoutPicks = scoutRes.items;
    facets = facetRes;
  } catch {
    unavailable = true;
  }

  return (
    <main className="min-h-screen pb-16">
      <PageHeader
        eyebrow="Open Source Intelligence"
        title="RepoTrajectory"
        description="Public software directory indexing 10,000 active projects, backed by a rolling candidate pool and an evidence-based AI Scout feed."
        action={
          <div className="flex flex-col gap-1.5 font-mono text-[10px]">
            <span className="text-[#9ba399]">DIRECTORY SIZE</span>
            <span className="text-xl font-bold text-[#c7ff00]">10,000 REPOS</span>
            <span className="text-[9px] text-[#70776f]">25% MAX PER LANGUAGE</span>
          </div>
        }
      />

      <div className="mx-auto max-w-[1600px] space-y-10 px-4 py-8 md:px-6 xl:px-8">
        {unavailable ? (
          <EmptyState
            title="Backend API Offline"
            description="Start the RepoTrajectory backend service on port 8000 to browse the 10K directory and Scout feed."
          />
        ) : (
          <>
            {/* Search Hero & Category Pills */}
            <section className="relative overflow-hidden border border-[#343a34] bg-[#101310] p-6 md:p-8">
              <div className="max-w-3xl space-y-4">
                <span className="inline-flex items-center gap-1.5 font-mono text-[9px] font-bold uppercase tracking-[.14em] text-[#c7ff00]">
                  <SparklesIcon className="size-3.5" />
                  Hybrid Semantic & Keyword Retrieval
                </span>
                <h2 className="text-2xl font-bold text-[#f1f4ec] md:text-3xl">
                  Discover software by purpose, not just star count
                </h2>
                <p className="font-mono text-xs leading-5 text-[#9ba399]">
                  Search using natural language or technical keywords. Our dual-branch engine combines
                  lexical full-text retrieval with pgvector semantic similarity.
                </p>

                <form action="/repositories" method="GET" className="mt-4 flex flex-col gap-2 sm:flex-row">
                  <div className="relative flex flex-1 items-center border border-[#343a34] bg-[#080a08] px-3 focus-within:border-[#c7ff00]">
                    <MagnifyingGlassIcon className="size-4 text-[#70776f]" />
                    <input
                      name="q"
                      placeholder="e.g. high-performance rust web framework or distributed consensus"
                      className="min-w-0 flex-1 bg-transparent px-2.5 py-3 font-mono text-xs text-[#f1f4ec] placeholder:text-[#565d56] focus:outline-none"
                    />
                  </div>
                  <button
                    type="submit"
                    className="flex items-center justify-center gap-2 border border-[#c7ff00] bg-[#c7ff00] px-6 py-3 font-mono text-xs font-bold text-[#080a08] transition hover:bg-[#b0e600]"
                  >
                    <span>Search Index</span>
                    <ArrowRightIcon className="size-4" />
                  </button>
                </form>

                {/* Trending tags */}
                <div className="flex flex-wrap items-center gap-2 pt-2">
                  <span className="font-mono text-[9px] uppercase tracking-wider text-[#565d56]">
                    Trending:
                  </span>
                  {[
                    "developer-tools",
                    "cli",
                    "web-framework",
                    "database",
                    "machine-learning",
                    "security",
                    "runtime",
                  ].map((tag) => (
                    <Link
                      key={tag}
                      href={`/repositories?q=${encodeURIComponent(tag)}`}
                      className="border border-[#343a34] bg-[#080a08] px-2.5 py-1 font-mono text-[9px] text-[#9ba399] transition hover:border-[#c7ff00] hover:text-[#c7ff00]"
                    >
                      #{tag}
                    </Link>
                  ))}
                </div>
              </div>
            </section>

            {/* Three Analytical Lenses */}
            <section className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#343a34] pb-2">
                <span className="font-mono text-[10px] font-bold uppercase tracking-[.14em] text-[#9ba399]">
                  01 // Analytical Perspectives
                </span>
                <span className="font-mono text-[9px] text-[#565d56]">CHOOSE YOUR WORKSPACE LENS</span>
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                <Link
                  href="/repositories?lens=developer"
                  className="group relative border border-[#343a34] bg-[#101310] p-5 transition hover:border-[#c7ff00]"
                >
                  <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase text-[#c7ff00]">
                    <CodeBracketIcon className="size-4" />
                    <span>Developer Lens</span>
                  </div>
                  <h3 className="mt-2 text-lg font-bold text-[#f1f4ec] group-hover:text-[#c7ff00]">
                    Architecture & APIs
                  </h3>
                  <p className="mt-2 text-xs leading-5 text-[#9ba399]">
                    Inspect technical classifications, primary language footprints, topics, open issue
                    burndown, and default branch health.
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-[#70776f] group-hover:text-[#c7ff00]">
                    Open developer directory →
                  </span>
                </Link>

                <Link
                  href="/repositories?lens=maintainer"
                  className="group relative border border-[#343a34] bg-[#101310] p-5 transition hover:border-[#c7ff00]"
                >
                  <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase text-[#c7ff00]">
                    <UserGroupIcon className="size-4" />
                    <span>Maintainer Lens</span>
                  </div>
                  <h3 className="mt-2 text-lg font-bold text-[#f1f4ec] group-hover:text-[#c7ff00]">
                    Sustainability & Risks
                  </h3>
                  <p className="mt-2 text-xs leading-5 text-[#9ba399]">
                    Examine bus factor concentration, PR merge latency, community responsiveness, and
                    prevent maintainer burnout.
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-[#70776f] group-hover:text-[#c7ff00]">
                    Open maintainer directory →
                  </span>
                </Link>

                <Link
                  href="/repositories?lens=investor"
                  className="group relative border border-[#343a34] bg-[#101310] p-5 transition hover:border-[#c7ff00]"
                >
                  <div className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase text-[#c7ff00]">
                    <FireIcon className="size-4" />
                    <span>Investor Lens</span>
                  </div>
                  <h3 className="mt-2 text-lg font-bold text-[#f1f4ec] group-hover:text-[#c7ff00]">
                    Growth & Trajectory
                  </h3>
                  <p className="mt-2 text-xs leading-5 text-[#9ba399]">
                    Identify breakout adoption acceleration, star momentum, under-the-radar promise scores,
                    and ecosystem inflection points.
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-[#70776f] group-hover:text-[#c7ff00]">
                    Open investor directory →
                  </span>
                </Link>
              </div>
            </section>

            {/* AI Scout Picks (Under-the-radar discoveries) */}
            <section className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#343a34] pb-2">
                <div className="flex items-center gap-2">
                  <SparklesIcon className="size-4 text-[#c7ff00]" />
                  <span className="font-mono text-[10px] font-bold uppercase tracking-[.14em] text-[#9ba399]">
                    02 // AI Scout Feed Picks
                  </span>
                </div>
                <Link
                  href="/scout"
                  className="font-mono text-[9px] font-bold uppercase tracking-wider text-[#c7ff00] hover:underline"
                >
                  View full Scout feed ({scoutPicks.length}+ picks) →
                </Link>
              </div>

              {scoutPicks.length === 0 ? (
                <div className="border border-[#343a34] bg-[#101310] p-6 text-center font-mono text-xs text-[#70776f]">
                  No Scout evaluations generated yet. Trigger daily scout batch in the background.
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {scoutPicks.map((item) => (
                    <div
                      key={item.full_name}
                      className="flex flex-col justify-between border border-[#343a34] bg-[#101310] p-5 transition hover:border-[#697168]"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <Link
                            href={`/repositories/${item.owner}/${item.name}`}
                            className="font-mono text-sm font-bold text-[#f1f4ec] hover:text-[#c7ff00]"
                          >
                            {item.full_name}
                          </Link>
                          <span className="inline-flex items-center gap-1 border border-[#c7ff00] bg-[#c7ff00]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[#c7ff00]">
                            ★ {item.promise_score} PROMISE
                          </span>
                        </div>

                        <div className="mt-2 flex items-center gap-3 font-mono text-[9px] text-[#70776f]">
                          <span>{item.primary_language || "General"}</span>
                          <span>·</span>
                          <span>{item.stars} stars</span>
                          <span>·</span>
                          <span>Updated {relativeDate(item.pushed_at)}</span>
                        </div>

                        <p className="mt-3 text-xs leading-5 text-[#b9c0b7]">
                          {item.description || "No description provided."}
                        </p>

                        <div className="mt-4 border-l-2 border-[#c7ff00] bg-[#080a08] p-3">
                          <p className="font-mono text-[10px] font-semibold text-[#c7ff00]">
                            WHY IT SURFACED:
                          </p>
                          <p className="mt-1 text-xs text-[#f1f4ec]">{item.why_it_surfaced}</p>
                        </div>

                        {item.supporting_facts.length > 0 && (
                          <div className="mt-3 space-y-1">
                            {item.supporting_facts.slice(0, 2).map((fact, idx) => (
                              <div key={idx} className="flex items-center gap-1.5 font-mono text-[10px] text-[#9ba399]">
                                <span className="size-1 bg-[#c7ff00]" />
                                <span>{fact}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {item.risk_flags.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {item.risk_flags.map((flag, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1 border border-[#343a34] bg-[#080a08] px-2 py-0.5 font-mono text-[8px] text-[#9ba399]"
                              >
                                <ExclamationTriangleIcon className="size-2.5 text-[#70776f]" />
                                {flag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="mt-4 pt-3 border-t border-[#343a34] flex items-center justify-between font-mono text-[9px] text-[#70776f]">
                        <span>Confidence: {Math.round(item.confidence * 100)}%</span>
                        <Link
                          href={`/repositories/${item.owner}/${item.name}`}
                          className="text-[#c7ff00] hover:underline"
                        >
                          View Repository Profile →
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* 10K Directory Spotlight Table */}
            <section className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#343a34] pb-2">
                <span className="font-mono text-[10px] font-bold uppercase tracking-[.14em] text-[#9ba399]">
                  03 // Directory Spotlight (10,000 Active Projects)
                </span>
                <Link
                  href="/repositories"
                  className="font-mono text-[9px] font-bold uppercase tracking-wider text-[#c7ff00] hover:underline"
                >
                  Browse all 10,000 repositories →
                </Link>
              </div>

              <div className="overflow-x-auto border border-[#343a34] bg-[#101310]">
                <table className="w-full min-w-[900px]">
                  <thead>
                    <tr className="border-b border-[#343a34] bg-[#080a08] text-left font-mono text-[9px] uppercase tracking-wider text-[#70776f]">
                      <th className="px-5 py-3">Repository</th>
                      <th className="px-4 py-3">Language</th>
                      <th className="px-4 py-3">Stars</th>
                      <th className="px-4 py-3">Selection Score</th>
                      <th className="px-4 py-3">Scout Promise</th>
                      <th className="px-4 py-3">Freshness</th>
                      <th className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#343a34]">
                    {directoryItems.map((repo) => (
                      <tr key={repo.full_name} className="transition hover:bg-[#080a08]/60">
                        <td className="px-5 py-3.5">
                          <Link
                            href={`/repositories/${repo.owner}/${repo.name}`}
                            className="font-mono text-xs font-bold text-[#f1f4ec] hover:text-[#c7ff00]"
                          >
                            {repo.full_name}
                          </Link>
                          {repo.description && (
                            <p className="mt-0.5 max-w-md truncate text-[11px] text-[#70776f]">
                              {repo.description}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3.5 font-mono text-[11px] text-[#9ba399]">
                          {repo.primary_language || "—"}
                        </td>
                        <td className="px-4 py-3.5 font-mono text-[11px] font-semibold text-[#f1f4ec]">
                          {compact(repo.stars)}
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="font-mono text-xs font-bold text-[#c7ff00]">
                            {Math.round(repo.selection_score)}
                          </span>
                          <span className="font-mono text-[9px] text-[#565d56]">/100</span>
                        </td>
                        <td className="px-4 py-3.5">
                          {repo.promise_score ? (
                            <span className="border border-[#c7ff00]/40 bg-[#c7ff00]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[#c7ff00]">
                              {repo.promise_score}
                            </span>
                          ) : (
                            <span className="font-mono text-[10px] text-[#565d56]">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3.5 font-mono text-[10px] text-[#70776f]">
                          {relativeDate(repo.pushed_at)}
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <Link
                            href={`/repositories/${repo.owner}/${repo.name}`}
                            className="font-mono text-[10px] text-[#9ba399] hover:text-[#c7ff00]"
                          >
                            Inspect →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
