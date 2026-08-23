"use client";

import {
  ArrowsRightLeftIcon,
  BeakerIcon,
  ChartBarSquareIcon,
  CircleStackIcon,
  CloudArrowDownIcon,
  MagnifyingGlassIcon,
  QuestionMarkCircleIcon,
  RectangleGroupIcon,
  ShieldCheckIcon,
} from "@heroicons/react/24/outline";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { startProductTour } from "@/components/first-run-tutorial";
import { API, type Repo } from "@/lib/api";

const navigation = [
  { href: "/", label: "Overview", code: "00", icon: RectangleGroupIcon },
  { href: "/repositories", label: "Repositories", code: "01", icon: CircleStackIcon },
  { href: "/collection", label: "Collection", code: "02", icon: CloudArrowDownIcon },
  { href: "/rankings", label: "Rankings", code: "03", icon: ChartBarSquareIcon },
  { href: "/compare", label: "Compare", code: "04", icon: ArrowsRightLeftIcon },
  { href: "/methodology", label: "Methodology", code: "05", icon: BeakerIcon },
  { href: "/admin", label: "Admin", code: "06", icon: ShieldCheckIcon },
];

export function AppNavigation() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-[70] border-b border-[#343a34] bg-[#080a08]/95 backdrop-blur-md">
      <div className="mx-auto flex h-[68px] max-w-[1600px] items-center gap-4 px-4 md:px-6 xl:px-8">
        <Link href="/" className="shrink-0"><BrandMark /></Link>
        <div className="ml-auto hidden items-center gap-2 border-l border-[#343a34] pl-4 xl:flex">
          <span className="size-2 animate-pulse bg-[#c7ff00]" />
          <span className="font-mono text-[9px] uppercase tracking-[.14em] text-[#9ba399]">Local index / online</span>
        </div>
        <div className="hidden w-full max-w-[360px] lg:block"><RepositorySearch /></div>
        <div className="ml-auto flex items-center gap-1">
          <button onClick={startProductTour} className="grid size-9 place-items-center border border-[#343a34] text-[#9ba399] transition hover:border-[#c7ff00] hover:text-[#c7ff00]" aria-label="Open product tour" title="Product tour"><QuestionMarkCircleIcon className="size-[18px]" /></button>
          <a href={`${API}/docs`} target="_blank" rel="noreferrer" className="hidden h-9 items-center border border-[#343a34] px-3 font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#9ba399] transition hover:border-[#c7ff00] hover:text-[#c7ff00] sm:inline-flex">API / ↗</a>
        </div>
      </div>
      <nav className="mx-auto flex h-[38px] max-w-[1600px] overflow-x-auto border-t border-[#343a34] px-2 md:px-4 xl:px-6" aria-label="Primary navigation">
        {navigation.map(({ href, label, code, icon: Icon }) => {
          const active = href === "/" ? pathname === href : pathname.startsWith(href);
          return <motion.div key={href} className="relative shrink-0" whileHover={{ y: -2 }} whileTap={{ y: 0 }}>
            <Link href={href} data-tour={`nav-${href === "/" ? "overview" : href.slice(1)}`} className={`relative flex h-full items-center gap-2 border-x border-transparent px-3 font-mono text-[9px] font-bold uppercase tracking-[.1em] transition md:px-4 ${active ? "bg-[#c7ff00] text-[#080a08]" : "text-[#9ba399] hover:border-[#343a34] hover:text-[#f1f4ec]"}`}>
              <span className="text-[8px] opacity-60">{code}</span><Icon className="size-3.5 md:hidden" /><span>{label}</span>
              {active && <motion.span layoutId="nav-active" className="absolute inset-x-0 -bottom-px h-px bg-[#f1f4ec]" />}
            </Link>
          </motion.div>;
        })}
        <span className="ml-auto hidden items-center px-3 font-mono text-[8px] uppercase tracking-[.18em] text-[#565d56] xl:flex">RT–INTEL / v0.1</span>
      </nav>
    </header>
  );
}

function RepositorySearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [repositories, setRepositories] = useState<Repo[]>([]);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/v1/repositories?limit=100`).then((response) => response.ok ? response.json() : []).then(setRepositories).catch(() => setRepositories([]));
  }, []);

  const matches = query ? repositories.filter((repo) => repo.full_name.toLowerCase().includes(query.toLowerCase())).slice(0, 6) : [];
  return <div className="relative">
    <div className="flex h-9 items-center gap-2 border border-[#343a34] bg-[#101310] px-3 focus-within:border-[#c7ff00]">
      <MagnifyingGlassIcon className="size-4 text-[#70776f]" />
      <input aria-label="Search repositories" value={query} onFocus={() => setFocused(true)} onBlur={() => setTimeout(() => setFocused(false), 150)} onChange={(event) => setQuery(event.target.value)} placeholder="SEARCH INDEX / OWNER/REPO" className="min-w-0 flex-1 bg-transparent font-mono text-[9px] uppercase tracking-[.08em] text-[#f1f4ec] placeholder:text-[#565d56] focus:outline-none" />
      <span className="font-mono text-[8px] text-[#565d56]">⌘K</span>
    </div>
    {focused && matches.length > 0 && <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} className="absolute left-0 right-0 top-10 z-50 border border-[#697168] bg-[#080a08] shadow-[6px_6px_0_#c7ff00]">{matches.map((repo, index) => <button key={repo.full_name} onMouseDown={() => router.push(`/repositories/${repo.owner}/${repo.name}`)} className="flex w-full items-center gap-3 border-b border-[#343a34] px-3 py-2.5 text-left font-mono text-[10px] text-[#f1f4ec] last:border-0 hover:bg-[#c7ff00] hover:text-[#080a08]"><span className="opacity-50">{String(index + 1).padStart(2, "0")}</span>{repo.full_name}</button>)}</motion.div>}
  </div>;
}
