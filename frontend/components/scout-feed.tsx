"use client";

import {
  ArrowRightIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  SparklesIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useTransition } from "react";

import { ScoreBar, StatusBadge } from "@/components/ui";
import type { Facets, ScoutFeedItem } from "@/lib/api";
import { compact, relativeDate } from "@/lib/format";

interface ScoutFeedProps {
  items: ScoutFeedItem[];
  totalCount: number;
  nextCursor: string | null;
  facets?: Facets;
  currentFilters: {
    cursor?: string;
    lang?: string;
    min_score?: string;
  };
}

export function ScoutFeed({
  items,
  totalCount,
  nextCursor,
  facets,
  currentFilters,
}: ScoutFeedProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const updateFilters = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      if (!("cursor" in updates)) {
        params.delete("cursor");
      }
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === undefined || value === "") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      startTransition(() => {
        router.push(`${pathname}?${params.toString()}`);
      });
    },
    [router, pathname, searchParams]
  );

  const availableLanguages =
    facets?.languages?.map((l) => l.name) ||
    Array.from(new Set(items.map((i) => i.primary_language).filter(Boolean) as string[])).sort();

  return (
    <div className="space-y-6">
      {/* Control bar */}
      <div className="panel flex flex-wrap items-center justify-between gap-4 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <SparklesIcon className="size-4 text-[#c7ff00]" />
            <span className="font-mono text-xs font-bold text-[#f1f4ec]">
              {totalCount.toLocaleString()} High-Promise Candidates Evaluated
            </span>
          </div>

          <div className="h-4 w-px bg-[#343a34]" />

          {/* Language filter */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-[9px] uppercase tracking-wider text-[#70776f]">Language:</span>
            <select
              value={currentFilters.lang || ""}
              onChange={(e) => updateFilters({ lang: e.target.value || null })}
              className="border border-[#343a34] bg-[#101310] px-2.5 py-1 font-mono text-[10px] uppercase text-[#f1f4ec] outline-none focus:border-[#c7ff00]"
            >
              <option value="">All Languages</option>
              {availableLanguages.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </div>

          {/* Min score filter */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-[9px] uppercase tracking-wider text-[#70776f]">Min Promise:</span>
            <select
              value={currentFilters.min_score || "60"}
              onChange={(e) => updateFilters({ min_score: e.target.value })}
              className="border border-[#343a34] bg-[#101310] px-2.5 py-1 font-mono text-[10px] uppercase text-[#f1f4ec] outline-none focus:border-[#c7ff00]"
            >
              <option value="50">&gt;= 50 Promise</option>
              <option value="60">&gt;= 60 Promise (Standard)</option>
              <option value="75">&gt;= 75 Top Tier</option>
              <option value="85">&gt;= 85 Exceptional</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-wider text-[#70776f]">
          {isPending && <span className="text-[#c7ff00] animate-pulse">Updating...</span>}
          <span>Forks &amp; archived excluded</span>
          <span>•</span>
          <span>Low-star discovery enabled</span>
        </div>
      </div>

      {/* Cards Feed */}
      <div className="space-y-4">
        {items.map((item) => (
          <article
            key={item.github_id}
            className="panel border border-[#343a34] bg-[#0c0f0c] p-6 transition-colors hover:border-[#697168]"
          >
            <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
              {/* Left Column: Repository Info & AI Assessment */}
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    href={`/repositories/${item.owner}/${item.name}`}
                    className="font-mono text-lg font-bold text-[#f1f4ec] hover:text-[#c7ff00]"
                  >
                    {item.full_name}
                  </Link>
                  {item.primary_language && (
                    <span className="border border-[#343a34] bg-[#101310] px-2 py-0.5 font-mono text-[9px] font-bold text-[#c7ff00]">
                      {item.primary_language}
                    </span>
                  )}
                  {item.license && (
                    <span className="border border-[#343a34] bg-[#101310] px-2 py-0.5 font-mono text-[9px] text-[#9ba399]">
                      {item.license}
                    </span>
                  )}
                  <span className="font-mono text-[10px] text-[#70776f]">
                    Pushed {relativeDate(item.pushed_at)}
                  </span>
                </div>

                <p className="text-sm leading-relaxed text-[#b9c0b7]">
                  {item.description || "No project description provided."}
                </p>

                {/* Why it surfaced */}
                <div className="rounded border-l-2 border-[#c7ff00] bg-[#101310] p-4">
                  <p className="font-mono text-[9px] font-black uppercase tracking-wider text-[#c7ff00]">
                    Why It Surfaced (AI &amp; Momentum Reasoning)
                  </p>
                  <p className="mt-1.5 text-xs leading-5 text-[#f1f4ec]">
                    {item.why_it_surfaced || "High velocity human commits and release cadence relative to community size."}
                  </p>
                </div>

                {/* Supporting Facts Checklist */}
                {item.supporting_facts && item.supporting_facts.length > 0 && (
                  <div>
                    <p className="font-mono text-[9px] font-bold uppercase tracking-wider text-[#70776f]">
                      Supporting Evidence
                    </p>
                    <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
                      {item.supporting_facts.map((fact, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-xs text-[#9ba399]">
                          <CheckCircleIcon className="size-3.5 shrink-0 text-[#c7ff00] mt-0.5" />
                          <span>{fact}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Risk Flags & Uncertainty */}
                <div className="flex flex-wrap items-center gap-4 pt-2">
                  {item.risk_flags && item.risk_flags.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[9px] uppercase tracking-wider text-[#e5534b]">
                        Identified Risks:
                      </span>
                      {item.risk_flags.map((risk, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 border border-[#e5534b]/30 bg-[#1f1212] px-2 py-0.5 font-mono text-[9px] text-[#f87171]"
                        >
                          <ExclamationTriangleIcon className="size-3" />
                          {risk}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="inline-flex items-center gap-1 font-mono text-[9px] text-[#70776f]">
                      <CheckCircleIcon className="size-3 text-[#c7ff00]" /> No critical risk flags detected
                    </span>
                  )}

                  {item.uncertainty && (
                    <span className="inline-flex items-center gap-1 font-mono text-[9px] text-[#70776f]">
                      <InformationCircleIcon className="size-3" />
                      {item.uncertainty}
                    </span>
                  )}
                </div>
              </div>

              {/* Right Column: Score Breakdown & Stats */}
              <div className="flex flex-col justify-between border-t border-[#343a34] pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                <div className="space-y-4">
                  {/* Promise Score Big Display */}
                  <div className="panel border border-[#343a34] bg-[#101310] p-4 text-center">
                    <span className="font-mono text-[9px] font-black uppercase tracking-wider text-[#70776f]">
                      Scout Promise Score
                    </span>
                    <div className="mt-1 flex items-baseline justify-center gap-1">
                      <span className="font-mono text-3xl font-black text-[#c7ff00]">
                        {item.promise_score}
                      </span>
                      <span className="font-mono text-xs text-[#70776f]">/100</span>
                    </div>
                    <div className="mt-2 text-center">
                      <StatusBadge
                        status={
                          item.promise_score >= 80
                            ? "High Conviction"
                            : item.promise_score >= 65
                            ? "Emerging Signal"
                            : "Early Discovery"
                        }
                        tone={item.promise_score >= 80 ? "positive" : "warning"}
                      />
                    </div>
                  </div>

                  {/* 70/30 Score Breakdown */}
                  <div className="space-y-2 font-mono text-[10px]">
                    <div className="flex justify-between text-[#9ba399]">
                      <span>Quantitative (70%):</span>
                      <span className="font-bold text-[#f1f4ec]">
                        {item.score_components?.quantitative_score?.toFixed(1) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between text-[#9ba399]">
                      <span>AI Assessment (30%):</span>
                      <span className="font-bold text-[#f1f4ec]">
                        {item.score_components?.ai_score?.toFixed(1) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between text-[#9ba399]">
                      <span>Confidence:</span>
                      <span className="font-bold text-[#c7ff00]">
                        {item.confidence ? `${Math.round(item.confidence * 100)}%` : "70%"}
                      </span>
                    </div>
                  </div>

                  {/* Scale Stats */}
                  <div className="grid grid-cols-2 gap-2 border-t border-[#343a34] pt-3 font-mono text-center">
                    <div>
                      <span className="block text-[8px] uppercase text-[#70776f]">Stars</span>
                      <b className="text-xs text-[#f1f4ec]">{compact(item.stars)}</b>
                    </div>
                    <div>
                      <span className="block text-[8px] uppercase text-[#70776f]">Forks</span>
                      <b className="text-xs text-[#f1f4ec]">{compact(item.forks)}</b>
                    </div>
                  </div>
                </div>

                <div className="pt-4">
                  <Link
                    href={`/repositories/${item.owner}/${item.name}`}
                    className="flex w-full items-center justify-center gap-2 border border-[#697168] bg-[#101310] py-2 font-mono text-[10px] font-bold uppercase text-[#c7ff00] hover:border-[#c7ff00] hover:bg-[#171b17]"
                  >
                    View 5-Section Profile <ArrowRightIcon className="size-3" />
                  </Link>
                </div>
              </div>
            </div>
          </article>
        ))}

        {items.length === 0 && (
          <div className="panel p-12 text-center font-mono text-xs uppercase text-[#9ba399]">
            No Scout discoveries meet the current filter criteria.
          </div>
        )}
      </div>

      {/* Pagination */}
      {nextCursor && (
        <div className="flex justify-center pt-4">
          <button
            type="button"
            onClick={() => updateFilters({ cursor: nextCursor })}
            disabled={isPending}
            className="border border-[#c7ff00] bg-[#c7ff00] px-6 py-2.5 font-mono text-[10px] font-black uppercase text-[#080a08] transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            Load More Discoveries
          </button>
        </div>
      )}
    </div>
  );
}
