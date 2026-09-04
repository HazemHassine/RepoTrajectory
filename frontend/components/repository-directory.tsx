"use client";

import {
  ArrowLeftIcon,
  ArrowRightIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState, useTransition } from "react";

import { ScoreBar, StatusBadge } from "@/components/ui";
import type { CatalogRepo, Facets } from "@/lib/api";
import { compact, relativeDate } from "@/lib/format";

interface RepositoryDirectoryProps {
  records: CatalogRepo[];
  totalCount: number;
  nextCursor: string | null;
  facets?: Facets;
  currentFilters: {
    cursor?: string;
    lang?: string;
    lens?: string;
    sort?: string;
    order?: string;
    q?: string;
  };
}

export function RepositoryDirectory({
  records,
  totalCount,
  nextCursor,
  facets,
  currentFilters,
}: RepositoryDirectoryProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const [searchQuery, setSearchQuery] = useState(currentFilters.q || "");

  const updateFilters = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      // When changing filters (other than cursor), reset cursor
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

  const clearAllFilters = useCallback(() => {
    startTransition(() => {
      router.push(pathname);
      setSearchQuery("");
    });
  }, [router, pathname]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateFilters({ q: searchQuery.trim() || null });
  };

  const activeLens = currentFilters.lens || "developer";
  const activeSort = currentFilters.sort || "stars";
  const activeLang = currentFilters.lang || "";

  // Available languages from facets or distinct records
  const availableLanguages =
    facets?.languages?.map((l) => l.name) ||
    Array.from(new Set(records.map((r) => r.primary_language).filter(Boolean) as string[])).sort();

  // Active filter chips
  const activeChips: { label: string; onRemove: () => void }[] = [];
  if (currentFilters.q) {
    activeChips.push({
      label: `Search: "${currentFilters.q}"`,
      onRemove: () => {
        setSearchQuery("");
        updateFilters({ q: null });
      },
    });
  }
  if (currentFilters.lang) {
    activeChips.push({
      label: `Lang: ${currentFilters.lang}`,
      onRemove: () => updateFilters({ lang: null }),
    });
  }
  if (currentFilters.lens && currentFilters.lens !== "developer") {
    activeChips.push({
      label: `Lens: ${currentFilters.lens}`,
      onRemove: () => updateFilters({ lens: null }),
    });
  }
  if (currentFilters.sort && currentFilters.sort !== "stars") {
    activeChips.push({
      label: `Sort: ${currentFilters.sort}`,
      onRemove: () => updateFilters({ sort: null }),
    });
  }

  return (
    <div className="panel overflow-hidden">
      {/* Top Filter and Search Bar */}
      <div className="grid gap-px border-b border-[#343a34] bg-[#343a34] lg:grid-cols-[1fr_auto_auto_auto]">
        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="flex h-12 items-center gap-3 bg-[#101310] px-4 focus-within:bg-[#171b17]">
          <MagnifyingGlassIcon className="size-4 text-[#c7ff00]" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="SEARCH CANONICAL REPOSITORIES / (PRESS ENTER)"
            className="min-w-0 flex-1 bg-transparent font-mono text-[10px] uppercase tracking-[.08em] outline-none placeholder:text-[#70776f]"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                updateFilters({ q: null });
              }}
              className="font-mono text-[10px] text-[#70776f] hover:text-[#f1f4ec]"
            >
              CLEAR
            </button>
          )}
        </form>

        {/* Language Filter */}
        <div className="flex items-center bg-[#101310] px-3">
          <label className="mr-2 font-mono text-[9px] uppercase tracking-[.1em] text-[#70776f]">Lang:</label>
          <select
            value={activeLang}
            onChange={(e) => updateFilters({ lang: e.target.value || null })}
            className="h-12 border-0 bg-transparent font-mono text-[10px] font-bold uppercase outline-none focus:text-[#c7ff00]"
          >
            <option value="" className="bg-[#101310]">All Languages</option>
            {availableLanguages.map((lang) => (
              <option key={lang} value={lang} className="bg-[#101310]">
                {lang}
              </option>
            ))}
          </select>
        </div>

        {/* Audience Lens Tabs */}
        <div className="flex h-12 items-center bg-[#101310] px-2">
          <div className="flex items-center gap-1 border border-[#343a34] p-0.5">
            {(["developer", "maintainer", "investor"] as const).map((lensKey) => (
              <button
                key={lensKey}
                type="button"
                onClick={() => updateFilters({ lens: lensKey === "developer" ? null : lensKey })}
                className={`px-3 py-1 font-mono text-[9px] font-black uppercase tracking-[.08em] transition-colors ${
                  activeLens === lensKey
                    ? "bg-[#c7ff00] text-[#080a08]"
                    : "text-[#9ba399] hover:bg-[#171b17] hover:text-[#f1f4ec]"
                }`}
              >
                {lensKey}
              </button>
            ))}
          </div>
        </div>

        {/* Sort */}
        <div className="flex items-center bg-[#101310] px-3">
          <label className="mr-2 font-mono text-[9px] uppercase tracking-[.1em] text-[#70776f]">Sort:</label>
          <select
            value={activeSort}
            onChange={(e) => updateFilters({ sort: e.target.value === "stars" ? null : e.target.value })}
            className="h-12 border-0 bg-transparent font-mono text-[10px] font-bold uppercase outline-none focus:text-[#c7ff00]"
          >
            <option value="stars" className="bg-[#101310]">Stars</option>
            <option value="promise" className="bg-[#101310]">Promise Score</option>
            <option value="growth" className="bg-[#101310]">Momentum / Growth</option>
            <option value="health" className="bg-[#101310]">Community Health</option>
            <option value="name" className="bg-[#101310]">Alphabetical</option>
          </select>
        </div>
      </div>

      {/* Active Filter Chips & Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#343a34] bg-[#0c0f0c] px-5 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[9px] uppercase tracking-[.1em] text-[#70776f]">
            {totalCount ? `${totalCount.toLocaleString()} Repositories In Index` : "Loading..."}
          </span>
          {activeChips.length > 0 && (
            <>
              <span className="text-[#343a34]">|</span>
              {activeChips.map((chip, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 border border-[#c7ff00]/40 bg-[#171b17] px-2 py-0.5 font-mono text-[9px] text-[#c7ff00]"
                >
                  {chip.label}
                  <button
                    type="button"
                    onClick={chip.onRemove}
                    className="text-[#9ba399] hover:text-[#f1f4ec]"
                    aria-label={`Remove filter ${chip.label}`}
                  >
                    <XMarkIcon className="size-3" />
                  </button>
                </span>
              ))}
              <button
                type="button"
                onClick={clearAllFilters}
                className="font-mono text-[9px] text-[#9ba399] underline underline-offset-2 hover:text-[#c7ff00]"
              >
                Clear all
              </button>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 font-mono text-[9px] uppercase tracking-[.1em] text-[#70776f]">
          {isPending && <span className="text-[#c7ff00] animate-pulse">Filtering...</span>}
          <span>Showing {records.length} items</span>
          <span>•</span>
          <span>Max 25% diversity cap</span>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1040px]">
          <thead>
            <tr className="border-b border-[#343a34] bg-[#101310]">
              <th className="table-head px-5 py-3">Repository</th>
              <th className="table-head px-4 py-3">Language</th>
              <th className="table-head px-4 py-3">Stars</th>
              <th className="table-head px-4 py-3">Forks</th>
              {activeLens === "developer" && (
                <>
                  <th className="table-head px-4 py-3">Promise Score</th>
                  <th className="table-head px-4 py-3">Classification</th>
                  <th className="table-head px-4 py-3">License</th>
                </>
              )}
              {activeLens === "maintainer" && (
                <>
                  <th className="table-head px-4 py-3">Health Profile</th>
                  <th className="table-head px-4 py-3">Open Issues</th>
                  <th className="table-head px-4 py-3">Cohort</th>
                </>
              )}
              {activeLens === "investor" && (
                <>
                  <th className="table-head px-4 py-3">Momentum</th>
                  <th className="table-head px-4 py-3">Cohort Tier</th>
                  <th className="table-head px-4 py-3">Selection Score</th>
                </>
              )}
              <th className="table-head px-4 py-3">Activity Freshness</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record, index) => {
              const promiseVal = record.promise_score ?? (record.scout?.promise_score ?? null);
              return (
                <tr
                  key={record.full_name}
                  className="group border-b border-[#343a34] last:border-0 hover:bg-[#171b17] transition-colors"
                >
                  {/* Repository Identity */}
                  <td className="max-w-[340px] px-5 py-4">
                    <div className="flex items-start gap-3">
                      <span className="font-mono text-[9px] text-[#70776f]">
                        {String(index + 1).padStart(3, "0")}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/repositories/${record.owner}/${record.name}`}
                            className="font-mono text-[13px] font-bold text-[#f1f4ec] group-hover:text-[#c7ff00]"
                          >
                            {record.full_name}
                          </Link>
                          {record.is_deep && (
                            <span className="border border-[#c7ff00]/40 px-1 py-0.2 font-mono text-[8px] font-black uppercase text-[#c7ff00]">
                              Deep Cohort
                            </span>
                          )}
                        </div>
                        <p className="mt-1 truncate text-xs text-[#9ba399]">
                          {record.description || "No description provided"}
                        </p>
                      </div>
                    </div>
                  </td>

                  {/* Primary Language */}
                  <td className="px-4">
                    <span className="font-mono text-xs font-semibold text-[#f1f4ec]">
                      {record.primary_language || "—"}
                    </span>
                  </td>

                  {/* Stars */}
                  <td className="px-4">
                    <b className="font-mono text-xs text-[#f1f4ec]">{compact(record.stars)}</b>
                    <span className="block font-mono text-[9px] uppercase text-[#70776f]">stars</span>
                  </td>

                  {/* Forks */}
                  <td className="px-4">
                    <span className="font-mono text-xs text-[#9ba399]">{compact(record.forks)}</span>
                  </td>

                  {/* Lens-specific columns */}
                  {activeLens === "developer" && (
                    <>
                      <td className="px-4">
                        {promiseVal != null ? (
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold text-[#c7ff00]">{promiseVal}</span>
                            <span className="font-mono text-[9px] text-[#70776f]">/100</span>
                          </div>
                        ) : (
                          <span className="font-mono text-[10px] text-[#70776f]">—</span>
                        )}
                      </td>
                      <td className="px-4">
                        <span className="border border-[#343a34] bg-[#101310] px-2 py-0.5 font-mono text-[9px] uppercase text-[#9ba399]">
                          {record.classification || "General"}
                        </span>
                      </td>
                      <td className="px-4 font-mono text-[11px] text-[#9ba399]">
                        {record.license || "None"}
                      </td>
                    </>
                  )}

                  {activeLens === "maintainer" && (
                    <>
                      <td className="px-4">
                        <StatusBadge
                          status={record.is_deep ? "Comprehensive" : "Catalog Tier"}
                          tone={record.is_deep ? "positive" : "neutral"}
                        />
                      </td>
                      <td className="px-4 font-mono text-xs text-[#9ba399]">
                        {compact(record.open_issues)}
                      </td>
                      <td className="px-4 font-mono text-[10px] uppercase text-[#70776f]">
                        {record.tier}
                      </td>
                    </>
                  )}

                  {activeLens === "investor" && (
                    <>
                      <td className="px-4">
                        <ScoreBar compact value={record.promise_score ?? 50} />
                      </td>
                      <td className="px-4">
                        <span className="font-mono text-[10px] font-bold uppercase text-[#c7ff00]">
                          {record.is_deep ? "500-Deep" : "10k-Catalog"}
                        </span>
                      </td>
                      <td className="px-4 font-mono text-xs text-[#9ba399]">
                        {record.selection_score?.toFixed(1) ?? "—"}
                      </td>
                    </>
                  )}

                  {/* Freshness / Pushed */}
                  <td className="px-4 font-mono text-[10px] text-[#9ba399]">
                    {relativeDate(record.pushed_at || record.updated_at)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {records.length === 0 && (
          <div className="p-12 text-center">
            <p className="font-mono text-xs uppercase tracking-wider text-[#9ba399]">
              No repositories match current filters.
            </p>
            <button
              type="button"
              onClick={clearAllFilters}
              className="mt-3 border border-[#697168] bg-[#101310] px-4 py-2 font-mono text-[10px] text-[#c7ff00] hover:bg-[#171b17]"
            >
              Reset all filters
            </button>
          </div>
        )}
      </div>

      {/* Pagination Footer */}
      <div className="flex items-center justify-between border-t border-[#343a34] bg-[#101310] px-5 py-4">
        <div className="font-mono text-[10px] text-[#70776f]">
          {currentFilters.cursor ? (
            <button
              type="button"
              onClick={() => updateFilters({ cursor: null })}
              className="inline-flex items-center gap-1.5 text-[#c7ff00] hover:underline"
            >
              <ArrowLeftIcon className="size-3" /> Back to first page
            </button>
          ) : (
            <span>Page 1</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {nextCursor ? (
            <button
              type="button"
              onClick={() => updateFilters({ cursor: nextCursor })}
              disabled={isPending}
              className="inline-flex items-center gap-2 border border-[#c7ff00] bg-[#c7ff00] px-4 py-2 font-mono text-[10px] font-black uppercase text-[#080a08] transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Next 50 Repositories <ArrowRightIcon className="size-3.5" />
            </button>
          ) : (
            <span className="font-mono text-[10px] uppercase text-[#70776f]">End of results</span>
          )}
        </div>
      </div>
    </div>
  );
}
