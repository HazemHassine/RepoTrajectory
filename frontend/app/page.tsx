import {
  ArrowRightIcon,
  CodeBracketIcon,
  ExclamationTriangleIcon,
  FireIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  UserGroupIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import React from "react";

import { EmptyState, PageHeader } from "@/components/ui";
import {
  api,
  type CatalogRepo,
  type Facets,
  type ScoutFeedItem,
} from "@/lib/api";
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
        title="RepoTrajectory"
        description="Evidence-backed open-source repository health, momentum, delivery velocity, and community resilience analytics."
        action={
          <div className="flex items-center gap-3">
            <Link href="/repositories" className="button-primary">
              Explore Repositories
            </Link>
            <Link href="/compare" className="button-secondary">
              Compare
            </Link>
          </div>
        }
      />

      <div className="mx-auto max-w-[1600px] space-y-10 px-4 py-8 md:px-6 xl:px-8">
        {unavailable ? (
          <EmptyState
            title="Backend Service Offline"
            description="Start the RepoTrajectory backend service on port 8000 to query repository intelligence and live evaluation feeds."
          />
        ) : (
          <>
            {/* Search Hero */}
            <section className="panel p-6 md:p-8">
              <div className="max-w-3xl space-y-4">
                <h2 className="text-2xl font-bold text-[#ffffff] md:text-3xl">
                  Discover software by purpose, activity, and health
                </h2>
                <p className="text-sm leading-relaxed text-[#9a9a9a]">
                  Search across open-source software using natural language or technical keywords. Combine full-text search with semantic similarity.
                </p>

                <form
                  action="/repositories"
                  method="GET"
                  className="mt-4 flex flex-col gap-2.5 sm:flex-row"
                >
                  <div className="relative flex flex-1 items-center rounded-md border border-[#262626] bg-[#090909] px-3 focus-within:border-[#ccf200]">
                    <MagnifyingGlassIcon className="size-4 text-[#646464]" />
                    <input
                      name="q"
                      placeholder="e.g. rust web framework, distributed consensus, or developer tools"
                      className="min-w-0 flex-1 bg-transparent px-2.5 py-2.5 font-mono text-xs text-[#ffffff] placeholder:text-[#646464] focus:outline-none"
                    />
                  </div>
                  <button type="submit" className="button-primary">
                    <span>Search</span>
                    <ArrowRightIcon className="size-3.5" />
                  </button>
                </form>

                {/* Popular tags */}
                <div className="flex flex-wrap items-center gap-2 pt-2">
                  <span className="font-mono text-[10px] text-[#646464]">
                    Popular topics:
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
                      className="rounded border border-[#222222] bg-[#111111] px-2.5 py-1 font-mono text-[10px] text-[#9a9a9a] transition hover:border-[#ccf200] hover:text-[#ccf200]"
                    >
                      #{tag}
                    </Link>
                  ))}
                </div>
              </div>
            </section>

            {/* Analytical Lenses */}
            <section className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#222222] pb-2.5">
                <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-[#9a9a9a]">
                  Analytical Perspectives
                </h3>
                <span className="font-mono text-[10px] text-[#646464]">
                  Select a focus area
                </span>
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                <Link
                  href="/repositories?lens=developer"
                  className="panel group p-5 transition hover:border-[#333333]"
                >
                  <div className="flex items-center gap-2 font-mono text-xs font-semibold text-[#ccf200]">
                    <CodeBracketIcon className="size-4" />
                    <span>Developer Focus</span>
                  </div>
                  <h4 className="mt-2 text-base font-bold text-[#ffffff] group-hover:text-[#ccf200]">
                    Architecture & Technology
                  </h4>
                  <p className="mt-2 text-xs leading-relaxed text-[#9a9a9a]">
                    Inspect technical classifications, language footprints, issue burndown, and default branch activity.
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 font-mono text-[10px] text-[#646464] group-hover:text-[#ccf200]">
                    Browse developer view →
                  </span>
                </Link>

                <Link
                  href="/repositories?lens=maintainer"
                  className="panel group p-5 transition hover:border-[#333333]"
                >
                  <div className="flex items-center gap-2 font-mono text-xs font-semibold text-[#ccf200]">
                    <UserGroupIcon className="size-4" />
                    <span>Maintainer Focus</span>
                  </div>
                  <h4 className="mt-2 text-base font-bold text-[#ffffff] group-hover:text-[#ccf200]">
                    Sustainability & Resilience
                  </h4>
                  <p className="mt-2 text-xs leading-relaxed text-[#9a9a9a]">
                    Examine contributor concentration, PR merge latency, community responsiveness, and maintenance workload.
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 font-mono text-[10px] text-[#646464] group-hover:text-[#ccf200]">
                    Browse maintainer view →
                  </span>
                </Link>

                <Link
                  href="/repositories?lens=investor"
                  className="panel group p-5 transition hover:border-[#333333]"
                >
                  <div className="flex items-center gap-2 font-mono text-xs font-semibold text-[#ccf200]">
                    <FireIcon className="size-4" />
                    <span>Growth Focus</span>
                  </div>
                  <h4 className="mt-2 text-base font-bold text-[#ffffff] group-hover:text-[#ccf200]">
                    Momentum & Trajectory
                  </h4>
                  <p className="mt-2 text-xs leading-relaxed text-[#9a9a9a]">
                    Identify adoption acceleration, star momentum, under-the-radar promise scores, and inflection points.
                  </p>
                  <span className="mt-4 inline-flex items-center gap-1 font-mono text-[10px] text-[#646464] group-hover:text-[#ccf200]">
                    Browse growth view →
                  </span>
                </Link>
              </div>
            </section>

            {/* Scout Discoveries */}
            <section className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#222222] pb-2.5">
                <div className="flex items-center gap-2">
                  <SparklesIcon className="size-4 text-[#ccf200]" />
                  <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-[#9a9a9a]">
                    Scout Discoveries
                  </h3>
                </div>
                <Link
                  href="/scout"
                  className="font-mono text-[10px] font-semibold text-[#ccf200] hover:underline"
                >
                  View full Scout feed ({scoutPicks.length}+ picks) →
                </Link>
              </div>

              {scoutPicks.length === 0 ? (
                <div className="panel p-6 text-center font-mono text-xs text-[#646464]">
                  No Scout evaluations generated yet.
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {scoutPicks.map((item) => (
                    <div
                      key={item.full_name}
                      className="panel flex flex-col justify-between p-5 transition hover:border-[#333333]"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <Link
                            href={`/repositories/${item.owner}/${item.name}`}
                            className="font-mono text-sm font-bold text-[#ffffff] hover:text-[#ccf200]"
                          >
                            {item.full_name}
                          </Link>
                          <span className="inline-flex items-center gap-1 rounded border border-[#ccf200]/40 bg-[#ccf200]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[#ccf200]">
                            ★ {item.promise_score} Promise
                          </span>
                        </div>

                        <div className="mt-2 flex items-center gap-3 font-mono text-[10px] text-[#646464]">
                          <span>{item.primary_language || "General"}</span>
                          <span>·</span>
                          <span>{item.stars} stars</span>
                          <span>·</span>
                          <span>Updated {relativeDate(item.pushed_at)}</span>
                        </div>

                        <p className="mt-3 text-xs leading-relaxed text-[#9a9a9a]">
                          {item.description || "No description provided."}
                        </p>

                        <div className="mt-3 rounded-md border-l-2 border-[#ccf200] bg-[#050505] p-3">
                          <p className="font-mono text-[9px] font-semibold text-[#ccf200]">
                            SURFACING RATIONALE:
                          </p>
                          <p className="mt-1 text-xs text-[#ffffff]">
                            {item.why_it_surfaced}
                          </p>
                        </div>

                        {item.supporting_facts.length > 0 && (
                          <div className="mt-3 space-y-1">
                            {item.supporting_facts.slice(0, 2).map((fact, idx) => (
                              <div
                                key={idx}
                                className="flex items-center gap-1.5 font-mono text-[10px] text-[#9a9a9a]"
                              >
                                <span className="size-1 rounded-full bg-[#ccf200]" />
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
                                className="inline-flex items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[9px] text-amber-300"
                              >
                                <ExclamationTriangleIcon className="size-2.5" />
                                {flag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="mt-4 flex items-center justify-between border-t border-[#222222] pt-3 font-mono text-[10px] text-[#646464]">
                        <span>Confidence: {Math.round(item.confidence * 100)}%</span>
                        <Link
                          href={`/repositories/${item.owner}/${item.name}`}
                          className="text-[#ccf200] hover:underline"
                        >
                          View Profile →
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Featured Repositories Table */}
            <section className="space-y-4">
              <div className="flex items-center justify-between border-b border-[#222222] pb-2.5">
                <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-[#9a9a9a]">
                  Featured Repositories
                </h3>
                <Link
                  href="/repositories"
                  className="font-mono text-[10px] font-semibold text-[#ccf200] hover:underline"
                >
                  Browse all repositories →
                </Link>
              </div>

              <div className="overflow-x-auto rounded-lg border border-[#222222] bg-[#0c0c0c]">
                <table className="w-full min-w-[900px]">
                  <thead>
                    <tr className="border-b border-[#222222] bg-[#090909] text-left font-mono text-[10px] text-[#646464]">
                      <th className="px-5 py-3">Repository</th>
                      <th className="px-4 py-3">Language</th>
                      <th className="px-4 py-3">Stars</th>
                      <th className="px-4 py-3">Selection Score</th>
                      <th className="px-4 py-3">Scout Promise</th>
                      <th className="px-4 py-3">Freshness</th>
                      <th className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#222222]">
                    {directoryItems.map((repo) => (
                      <tr
                        key={repo.full_name}
                        className="transition hover:bg-[#111111]"
                      >
                        <td className="px-5 py-3.5">
                          <Link
                            href={`/repositories/${repo.owner}/${repo.name}`}
                            className="font-mono text-xs font-bold text-[#ffffff] hover:text-[#ccf200]"
                          >
                            {repo.full_name}
                          </Link>
                          {repo.description && (
                            <p className="mt-0.5 max-w-md truncate text-[11px] text-[#646464]">
                              {repo.description}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3.5 font-mono text-xs text-[#9a9a9a]">
                          {repo.primary_language || "—"}
                        </td>
                        <td className="px-4 py-3.5 font-mono text-xs font-semibold text-[#ffffff]">
                          {compact(repo.stars)}
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="font-mono text-xs font-bold text-[#ccf200]">
                            {Math.round(repo.selection_score)}
                          </span>
                          <span className="font-mono text-[10px] text-[#646464]">
                            /100
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          {repo.promise_score ? (
                            <span className="rounded border border-[#ccf200]/40 bg-[#ccf200]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[#ccf200]">
                              {repo.promise_score}
                            </span>
                          ) : (
                            <span className="font-mono text-xs text-[#646464]">
                              —
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3.5 font-mono text-xs text-[#646464]">
                          {relativeDate(repo.pushed_at)}
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <Link
                            href={`/repositories/${repo.owner}/${repo.name}`}
                            className="font-mono text-xs text-[#9a9a9a] hover:text-[#ccf200]"
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
