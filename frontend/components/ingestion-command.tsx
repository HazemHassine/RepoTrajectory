"use client";

import { ClipboardDocumentIcon, PlusIcon, XMarkIcon } from "@heroicons/react/20/solid";
import { useState } from "react";

export function IngestionCommand() {
  const [open, setOpen] = useState(false);
  const [repository, setRepository] = useState("owner/repository");
  const command = `python -m app.cli ingest ${repository || "owner/repository"}`;

  return (
    <>
      <button onClick={() => setOpen(true)} className="button-primary">
        <PlusIcon className="size-4" />
        Add repository
      </button>
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[100] grid place-items-center bg-[#050505]/80 p-4 backdrop-blur-sm"
          onMouseDown={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-lg border border-[#222222] bg-[#0c0c0c] shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#222222] px-5 py-4">
              <div>
                <h2 className="text-sm font-semibold text-[#ffffff]">Add repository evidence</h2>
                <p className="mt-1 text-xs text-[#9a9a9a]">Ingestion remains an explicit backend operation.</p>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="rounded p-1 text-[#9a9a9a] hover:bg-[#161616] hover:text-[#ffffff]"
              >
                <XMarkIcon className="size-5" />
              </button>
            </div>
            <div className="p-5">
              <label className="data-label">
                GitHub repository
                <input
                  value={repository}
                  onFocus={() => repository === "owner/repository" && setRepository("")}
                  onChange={(event) => setRepository(event.target.value)}
                  className="mt-2 h-10 w-full rounded-md border border-[#222222] bg-[#161616] px-3 font-mono text-xs text-[#ffffff] focus:border-[#ccf200] focus:outline-none"
                />
              </label>
              <p className="mt-4 text-xs leading-5 text-[#9a9a9a]">From the activated backend virtual environment, run:</p>
              <div className="mt-2 flex items-center gap-2 rounded-md border border-[#222222] bg-[#050505] p-3">
                <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs text-[#ffffff]">
                  {command}
                </code>
                <button
                  onClick={() => navigator.clipboard.writeText(command)}
                  title="Copy command"
                  className="text-[#9a9a9a] hover:text-[#ccf200]"
                >
                  <ClipboardDocumentIcon className="size-4" />
                </button>
              </div>
              <p className="mt-4 rounded-md border border-[#222222] bg-[#161616] p-3 text-[11px] leading-4 text-[#9a9a9a]">
                The first run collects available history. Later runs are incremental and add the snapshots needed for real growth rates.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
