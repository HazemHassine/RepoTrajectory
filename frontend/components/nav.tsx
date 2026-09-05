"use client";

import {
  ArrowsRightLeftIcon,
  BeakerIcon,
  CircleStackIcon,
  MagnifyingGlassIcon,
  QuestionMarkCircleIcon,
  RectangleGroupIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { startProductTour } from "@/components/first-run-tutorial";
import { API, type CatalogRepo } from "@/lib/api";

const navigation = [
  { href: "/", label: "Discover", icon: RectangleGroupIcon },
  { href: "/topics", label: "Topics", icon: SparklesIcon },
  { href: "/watchlist", label: "Watchlist", icon: CircleStackIcon },
  { href: "/repositories", label: "Repositories", icon: CircleStackIcon },
  { href: "/scout", label: "Scout", icon: SparklesIcon },
  { href: "/compare", label: "Compare", icon: ArrowsRightLeftIcon },
  { href: "/methodology", label: "Methodology", icon: BeakerIcon },
];

export function AppNavigation() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-[70] border-b border-[#222222] bg-[#050505]/95 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-4 px-4 md:px-6 xl:px-8">
        <Link href="/" className="shrink-0">
          <BrandMark />
        </Link>

        <div className="hidden w-full max-w-md md:block">
          <RepositorySearch />
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/admin"
            className="hidden h-8 items-center rounded-md border border-[#222222] px-3 font-mono text-[10px] font-medium uppercase tracking-wider text-[#9a9a9a] transition hover:border-[#333333] hover:text-[#ffffff] sm:inline-flex"
            title="Administration"
          >
            <ShieldCheckIcon className="mr-1.5 size-3.5" />
            Admin
          </Link>
          <button
            onClick={startProductTour}
            className="grid size-8 place-items-center rounded-md border border-[#222222] text-[#9a9a9a] transition hover:border-[#ccf200] hover:text-[#ccf200]"
            aria-label="Open product tour"
            title="Overview tour"
          >
            <QuestionMarkCircleIcon className="size-4" />
          </button>
          <a
            href={`${API}/docs`}
            target="_blank"
            rel="noreferrer"
            className="hidden h-8 items-center rounded-md border border-[#222222] px-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-[#9a9a9a] transition hover:border-[#ccf200] hover:text-[#ccf200] lg:inline-flex"
          >
            API Docs ↗
          </a>
        </div>
      </div>

      <nav
        className="mx-auto flex h-10 max-w-[1600px] items-center gap-1 overflow-x-auto border-t border-[#1c1c1c] px-4 md:px-6 xl:px-8"
        aria-label="Primary navigation"
      >
        {navigation.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              data-tour={`nav-${href === "/" ? "home" : href.slice(1)}`}
              className={`relative flex h-7 items-center gap-2 rounded-md px-3 font-mono text-[11px] font-semibold uppercase tracking-wider transition-colors ${
                active
                  ? "bg-[#ccf200] text-[#050505]"
                  : "text-[#9a9a9a] hover:bg-[#141414] hover:text-[#ffffff]"
              }`}
            >
              <Icon className="size-3.5" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

function RepositorySearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CatalogRepo[]>([]);
  const [focused, setFocused] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults([]);
      return;
    }
    const timer = setTimeout(() => {
      setLoading(true);
      fetch(`${API}/api/v2/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit: 6 }),
      })
        .then((res) => (res.ok ? res.json() : { items: [] }))
        .then((data) => {
          setResults(data.items || []);
          setLoading(false);
        })
        .catch(() => {
          setResults([]);
          setLoading(false);
        });
    }, 200);

    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div className="relative">
      <div className="flex h-9 items-center gap-2.5 rounded-md border border-[#222222] bg-[#0c0c0c] px-3 focus-within:border-[#ccf200]">
        <MagnifyingGlassIcon className="size-4 text-[#646464]" />
        <input
          aria-label="Search repositories"
          value={query}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 200)}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) {
              router.push(`/repositories?q=${encodeURIComponent(query.trim())}`);
            }
          }}
          placeholder="Search repositories (name, topic, purpose)…"
          className="min-w-0 flex-1 bg-transparent font-mono text-xs text-[#ffffff] placeholder:text-[#646464] focus:outline-none"
        />
        {loading ? (
          <span className="size-2 animate-ping rounded-full bg-[#ccf200]" />
        ) : (
          <span className="rounded bg-[#161616] px-1.5 py-0.5 font-mono text-[9px] text-[#646464]">
            ↵
          </span>
        )}
      </div>

      {focused && results.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute left-0 right-0 top-11 z-50 overflow-hidden rounded-md border border-[#222222] bg-[#0c0c0c] shadow-xl"
        >
          {results.map((repo, index) => (
            <button
              key={repo.full_name}
              onMouseDown={() =>
                router.push(`/repositories/${repo.owner}/${repo.name}`)
              }
              className="flex w-full items-center justify-between border-b border-[#1c1c1c] px-3.5 py-2.5 text-left font-mono text-xs text-[#ffffff] last:border-0 hover:bg-[#161616]"
            >
              <span className="flex items-center gap-2 truncate">
                <span className="text-[#646464]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="font-semibold">{repo.full_name}</span>
              </span>
              <span className="flex items-center gap-2 text-[11px] text-[#9a9a9a]">
                {repo.primary_language && <span>{repo.primary_language}</span>}
                <span>★ {repo.stars}</span>
              </span>
            </button>
          ))}
        </motion.div>
      )}
    </div>
  );
}
