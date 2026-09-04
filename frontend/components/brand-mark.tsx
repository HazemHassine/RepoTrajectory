import React from "react";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 select-none" aria-label="RepoTrajectory">
      <span className="font-mono text-base font-bold tracking-tight text-[#ccf200]">
        /RT/
      </span>
      {!compact && (
        <div className="flex flex-col">
          <span className="text-sm font-bold tracking-tight text-[#ffffff]">
            RepoTrajectory
          </span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-[#9a9a9a]">
            Intelligence
          </span>
        </div>
      )}
    </div>
  );
}
