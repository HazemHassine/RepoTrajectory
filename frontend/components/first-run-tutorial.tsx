"use client";

import {
  ArrowsRightLeftIcon,
  BeakerIcon,
  ChartBarSquareIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleStackIcon,
  CloudArrowDownIcon,
  XMarkIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import type { CSSProperties, ElementType } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "repotrajectory:onboarding:v1";
const START_EVENT = "repotrajectory:start-tour";

type TourStep = {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  detail: string;
  target?: string;
  icon: ElementType;
};

const steps: TourStep[] = [
  {
    id: "welcome",
    eyebrow: "Orientation briefing",
    title: "Welcome to RepoTrajectory",
    description: "A research console for understanding open-source momentum, delivery health, and contributor dependency.",
    detail: "This two-minute tour shows where evidence enters the system and how to move from a broad market signal to a defensible repository decision.",
    icon: ChartBarSquareIcon,
  },
  {
    id: "collection",
    eyebrow: "01 · Build the universe",
    title: "Collection runs continuously",
    description: "GitHub Search finds established software while GH Archive contributes emerging adoption and collaboration signals.",
    detail: "Open Collection to inspect the candidate universe, queue depth, rate budget, active cohort, and hydration progress—or to pin a repository yourself.",
    target: "[data-tour='nav-collection']",
    icon: CloudArrowDownIcon,
  },
  {
    id: "repositories",
    eyebrow: "02 · Investigate",
    title: "Repository dossiers hold the evidence",
    description: "Use the directory or sidebar search to open a project’s activity, delivery, release, community, and concentration record.",
    detail: "Automation is separated from human work, and unavailable history stays unavailable instead of becoming a misleading zero.",
    target: "[data-tour='nav-repositories']",
    icon: CircleStackIcon,
  },
  {
    id: "rankings",
    eyebrow: "03 · Prioritize",
    title: "Rankings are decision views",
    description: "Sort the tracked universe by momentum, health, or contributor-concentration risk using a shared observation window.",
    detail: "Pay attention to confidence and baseline coverage. A high score with limited evidence should still be treated as provisional.",
    target: "[data-tour='nav-rankings']",
    icon: ChartBarSquareIcon,
  },
  {
    id: "compare",
    eyebrow: "04 · Compare",
    title: "Put repositories on equal footing",
    description: "Compare projects side by side with the same time window, metric definitions, and evidence caveats.",
    detail: "This is the fastest way to distinguish raw popularity from current trajectory, operating health, and community resilience.",
    target: "[data-tour='nav-compare']",
    icon: ArrowsRightLeftIcon,
  },
  {
    id: "methodology",
    eyebrow: "05 · Govern the conclusion",
    title: "Every score should be explainable",
    description: "Methodology documents what each metric measures, what it cannot claim, and when the evidence is too weak.",
    detail: "You are ready. Start in Collection if the database is still building, or open Repositories when hydrated dossiers are available.",
    target: "[data-tour='nav-methodology']",
    icon: BeakerIcon,
  },
];

function saveCompletion() {
  try {
    window.localStorage.setItem(STORAGE_KEY, "complete");
  } catch {
    // Browsers may block local storage; the tour still remains usable for this visit.
  }
}

export function startProductTour() {
  window.dispatchEvent(new Event(START_EVENT));
}

export function FirstRunTutorial() {
  const [isOpen, setIsOpen] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
  const cardRef = useRef<HTMLElement>(null);
  const step = steps[stepIndex];
  const isLast = stepIndex === steps.length - 1;

  const openTour = useCallback(() => {
    setStepIndex(0);
    setIsOpen(true);
  }, []);

  const closeTour = useCallback(() => {
    saveCompletion();
    setIsOpen(false);
  }, []);

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("tour") === "1";

    if (requested) {
      const url = new URL(window.location.href);
      url.searchParams.delete("tour");
      window.history.replaceState({}, "", url);
      openTour();
    }

    window.addEventListener(START_EVENT, openTour);
    return () => {
      window.removeEventListener(START_EVENT, openTour);
    };
  }, [openTour]);

  useEffect(() => {
    if (!isOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    cardRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen, stepIndex]);

  useEffect(() => {
    if (!isOpen) return;

    function measureTarget() {
      const element = step.target ? document.querySelector(step.target) : null;
      const rect = element?.getBoundingClientRect();
      setTargetRect(rect && rect.width > 0 && rect.height > 0 ? rect : null);
    }

    measureTarget();
    window.addEventListener("resize", measureTarget);
    return () => window.removeEventListener("resize", measureTarget);
  }, [isOpen, step]);

  useEffect(() => {
    if (!isOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeTour();
      if (event.key === "ArrowLeft" && stepIndex > 0) setStepIndex((current) => current - 1);
      if (event.key === "ArrowRight" && !isLast) setStepIndex((current) => current + 1);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeTour, isLast, isOpen, stepIndex]);

  if (!isOpen) return null;

  const cardStyle: CSSProperties = targetRect
    ? {
        left: Math.min(targetRect.right + 20, window.innerWidth - 460),
        top: Math.max(20, Math.min(targetRect.top - 24, window.innerHeight - 500)),
      }
    : { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };
  const Icon = step.icon;

  return <div className="fixed inset-0 z-[100]" aria-live="polite">
    <div className="absolute inset-0" aria-hidden="true" />
    {targetRect ? <div
      className="pointer-events-none fixed z-[101] rounded-lg ring-2 ring-[#ccf200]/90 shadow-[0_0_0_9999px_rgba(5,5,5,0.85)] transition-all duration-200"
      style={{
        left: targetRect.left - 6,
        top: targetRect.top - 6,
        width: targetRect.width + 12,
        height: targetRect.height + 12,
      }}
      aria-hidden="true"
    /> : <div className="fixed inset-0 z-[101] bg-[#050505]/85 backdrop-blur-[2px]" aria-hidden="true" />}

    <section
      key={step.id}
      ref={cardRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
      tabIndex={-1}
      style={cardStyle}
      className="tour-card fixed z-[102] max-h-[calc(100vh-40px)] w-[min(420px,calc(100vw-32px))] overflow-y-auto rounded-lg border border-[#222222] bg-[#0c0c0c] shadow-[0_24px_70px_rgba(0,0,0,.7)] focus:outline-none"
    >
      <div className="flex items-center justify-between border-b border-[#222222] px-5 py-3.5">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-[#9a9a9a]">
          <span className="font-mono text-[#ccf200]">{String(stepIndex + 1).padStart(2, "0")}</span>
          <span>/</span>
          <span className="font-mono">{String(steps.length).padStart(2, "0")}</span>
        </div>
        <button onClick={closeTour} className="rounded p-1 text-[#9a9a9a] hover:bg-[#161616] hover:text-[#ffffff]" aria-label="Close tutorial">
          <XMarkIcon className="size-5" />
        </button>
      </div>

      <div className="p-6">
        <div className="grid size-11 place-items-center rounded-md border border-[#222222] bg-[#161616] text-[#ccf200]"><Icon className="size-5" /></div>
        <p className="eyebrow mt-5 text-[#ccf200]">{step.eyebrow}</p>
        <h2 id="tour-title" className="mt-2 text-[23px] font-semibold leading-7 tracking-[-0.035em] text-[#ffffff]">{step.title}</h2>
        <p className="mt-3 text-sm font-medium leading-6 text-[#9a9a9a]">{step.description}</p>
        <p className="mt-3 text-xs leading-5 text-[#9a9a9a]">{step.detail}</p>

        {isLast && <div className="mt-5 grid grid-cols-2 gap-2">
          <Link href="/collection" onClick={closeTour} className="rounded-md border border-[#222222] px-3 py-2.5 text-center text-xs font-semibold text-[#ffffff] hover:bg-[#161616]">Open collection</Link>
          <Link href="/repositories" onClick={closeTour} className="rounded-md border border-[#222222] px-3 py-2.5 text-center text-xs font-semibold text-[#ffffff] hover:bg-[#161616]">Browse repositories</Link>
        </div>}
      </div>

      <div className="flex items-center justify-between border-t border-[#222222] bg-[#0c0c0c] px-5 py-4">
        {stepIndex === 0
          ? <button onClick={closeTour} className="text-xs font-semibold text-[#9a9a9a] hover:text-[#ffffff]">Skip tour</button>
          : <button onClick={() => setStepIndex((current) => current - 1)} className="inline-flex items-center gap-1 text-xs font-semibold text-[#9a9a9a] hover:text-[#ffffff]"><ChevronLeftIcon className="size-4" />Back</button>}
        <div className="flex items-center gap-3">
          <div className="hidden gap-1 sm:flex" aria-hidden="true">{steps.map((item, index) => <span key={item.id} className={`h-1 rounded-full transition-all ${index === stepIndex ? "w-5 bg-[#ccf200]" : index < stepIndex ? "w-2 bg-[#ccf200]" : "w-2 bg-[#222222]"}`} />)}</div>
          <button onClick={() => isLast ? closeTour() : setStepIndex((current) => current + 1)} className="button-primary min-w-[94px] px-3">
            {isLast ? <><CheckIcon className="size-4" />Finish</> : <>Next<ChevronRightIcon className="size-4" /></>}
          </button>
        </div>
      </div>
    </section>
  </div>;
}
