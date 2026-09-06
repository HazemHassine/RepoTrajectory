import Link from "next/link";
import { StarIcon } from "@heroicons/react/24/outline";

export type DiscoveryProject = {
  github_id: number; full_name: string; description: string | null;
  primary_language: string | null; stars: number; pushed_at: string | null;
};

export function DiscoveryCard({ project }: { project: DiscoveryProject }) {
  const [owner, ...name] = project.full_name.split("/");
  const date = project.pushed_at ? new Date(project.pushed_at) : null;
  const validDate = date && !Number.isNaN(date.getTime()) ? date : null;
  return <article className="group flex h-full min-w-0 flex-col rounded-lg border border-[#262626] bg-[#0c0c0c] p-5 transition-colors hover:border-[#ccf200]/40">
    <p className="mb-1 truncate text-xs text-[#9a9a9a]">{owner}</p>
    <h3 className="break-words text-lg font-semibold"><Link prefetch={false} href={`/repositories/${project.full_name}`} className="group-hover:text-[#ccf200]">{name.join("/") || owner}<span aria-hidden="true" className="ml-2 text-sm text-[#646464]">↗</span></Link></h3>
    <p className="mb-5 mt-3 line-clamp-3 text-sm leading-relaxed text-[#aaa]">{project.description || "No description available."}</p>
    <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-[#9a9a9a]">
      {project.primary_language && <span className="inline-flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-[#ccf200]" />{project.primary_language}</span>}
      <span className="inline-flex items-center gap-1" title={`${project.stars.toLocaleString("en-GB")} stars`}><StarIcon className="size-3.5" />{new Intl.NumberFormat("en-GB", { notation: "compact", maximumFractionDigits: 1 }).format(project.stars)}</span>
      {validDate && <time dateTime={validDate.toISOString()} className="ml-auto">Pushed {validDate.toLocaleDateString("en-GB", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}</time>}
    </div>
    <div className="mt-4 flex items-center justify-between border-t border-[#222] pt-3 text-xs">
      <Link prefetch={false} href={`/compare?a=${encodeURIComponent(project.full_name)}`} className="text-[#9a9a9a] hover:text-[#ccf200]">Compare</Link>
      <Link prefetch={false} href={`/repositories/${project.full_name}`} className="text-[#ccf200]">View project →</Link>
    </div>
  </article>;
}
