export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="group flex items-center gap-3" aria-label="RepoTrajectory">
      <span className="relative grid size-10 shrink-0 place-items-center border border-[#c7ff00] bg-[#c7ff00] font-mono text-[11px] font-black text-[#080a08] transition-transform group-hover:-rotate-3">
        R/T
        <span className="absolute -bottom-1 -right-1 size-2 border border-[#c7ff00] bg-[#080a08]" />
      </span>
      {!compact && <span><span className="display-face block text-xl leading-none tracking-[.02em] text-[#f1f4ec]">Repo<span className="outline-text">Trajectory</span></span><span className="mt-1 block font-mono text-[8px] uppercase tracking-[0.2em] text-[#9ba399]">Repository intelligence / 01</span></span>}
    </div>
  );
}
