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
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { startProductTour } from "@/components/first-run-tutorial";
import { API, type CatalogRepo } from "@/lib/api";

const navigation = [
  { href: "/", label: "Home", code: "00", icon: RectangleGroupIcon },
  { href: "/repositories", label: "Directory", code: "01", icon: CircleStackIcon },
  { href: "/scout", label: "Scout", code: "02", icon: SparklesIcon },
  { href: "/compare", label: "Compare", code: "03", icon: ArrowsRightLeftIcon },
  { href: "/methodology", label: "Methodology", code: "04", icon: BeakerIcon },
];

export function AppNavigation() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-[70] border-b border-[#343a34] bg-[#080a08]/95 backdrop-blur-md">
      <div className="mx-auto flex h-[68px] max-w-[1600px] items-center gap-4 px-4 md:px-6 xl:px-8">
        <Link href="/" className="shrink-0"><BrandMark /></Link>
        <div className="ml-auto hidden items-center gap-2 border-l border-[#343a34] pl-4 xl:flex">
          <span className="size-2 animate-pulse bg-[#c7ff00]" />
          <span className="font-mono text-[9px] uppercase tracking-[.14em] text-[#9ba399]">10K Directory / Online</span>
        </div>
        <div className="hidden w-full max-w-[380px] lg:block"><RepositorySearch /></div>
        <div className="ml-auto flex items-center gap-2">
          <Link href="/admin" className="hidden h-9 items-center border border-[#343a34] px-2.5 font-mono text-[9px] uppercase tracking-[.1em] text-[#70776f] transition hover:border-[#9ba399] hover:text-[#f1f4ec] md:inline-flex" title="Operator Admin Console">
            <ShieldCheckIcon className="mr-1 size-3.5" />Admin
          </Link>
          <button onClick={startProductTour} className="grid size-9 place-items-center border border-[#343a34] text-[#9ba399] transition hover:border-[#c7ff00] hover:text-[#c7ff00]" aria-label="Open product tour" title="Product tour"><QuestionMarkCircleIcon className="size-[18px]" /></button>
          <a href={`${API}/docs`} target="_blank" rel="noreferrer" className="hidden h-9 items-center border border-[#343a34] px-3 font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#9ba399] transition hover:border-[#c7ff00] hover:text-[#c7ff00] sm:inline-flex">API / ↗</a>
        </div>
      </div>
      <nav className="mx-auto flex h-[38px] max-w-[1600px] overflow-x-auto border-t border-[#343a34] px-2 md:px-4 xl:px-6" aria-label="Primary navigation">
        {navigation.map(({ href, label, code, icon: Icon }) => {
          const active = href === "/" ? pathname === href : pathname.startsWith(href);
          return (
            <motion.div key={href} className="relative shrink-0" whileHover={{ y: -2 }} whileTap={{ y: 0 }}>
              <Link href={href} data-tour={`nav-${href === "/" ? "home" : href.slice(1)}`} className={`relative flex h-full items-center gap-2 border-x border-transparent px-3 font-mono text-[9px] font-bold uppercase tracking-[.1em] transition md:px-4 ${active ? "bg-[#c7ff00] text-[#080a08]" : "text-[#9ba399] hover:border-[#343a34] hover:text-[#f1f4ec]"}`}>
                <span className="text-[8px] opacity-60">{code}</span><Icon className="size-3.5 md:hidden" /><span>{label}</span>
                {active && <motion.span layoutId="nav-active" className="absolute inset-x-0 -bottom-px h-px bg-[#f1f4ec]" />}
              </Link>
            </motion.div>
          );
        })}
        <span className="ml-auto hidden items-center px-3 font-mono text-[8px] uppercase tracking-[.18em] text-[#565d56] xl:flex">RT–INTEL / v2.0</span>
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
      <div className="flex h-9 items-center gap-2 border border-[#343a34] bg-[#101310] px-3 focus-within:border-[#c7ff00]">
        <MagnifyingGlassIcon className="size-4 text-[#70776f]" />
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
          placeholder="SEARCH 10K DIRECTORY (SEMANTIC / KEYWORD)"
          className="min-w-0 flex-1 bg-transparent font-mono text-[9px] uppercase tracking-[.08em] text-[#f1f4ec] placeholder:text-[#565d56] focus:outline-none"
        />
        {loading ? (
          <span className="size-2 animate-ping bg-[#c7ff00]" />
        ) : (
          <span className="font-mono text-[8px] text-[#565d56]">ENTER ↵</span>
        )}
      </div>
      {focused && results.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute left-0 right-0 top-10 z-50 border border-[#697168] bg-[#080a08] shadow-[6px_6px_0_#c7ff00]"
        >
          {results.map((repo, index) => (
            <button
              key={repo.full_name}
              onMouseDown={() => router.push(`/repositories/${repo.owner}/${repo.name}`)}
              className="flex w-full items-center justify-between border-b border-[#343a34] px-3 py-2.5 text-left font-mono text-[10px] text-[#f1f4ec] last:border-0 hover:bg-[#c7ff00] hover:text-[#080a08]"
            >
              <span className="flex items-center gap-2 truncate">
                <span className="opacity-50">{String(index + 1).padStart(2, "0")}</span>
                <span className="font-bold">{repo.full_name}</span>
              </span>
              <span className="flex items-center gap-2 text-[9px] opacity-75">
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

