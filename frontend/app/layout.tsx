import type { Metadata } from "next";

import { FirstRunTutorial } from "@/components/first-run-tutorial";
import { MotionShell } from "@/components/motion-shell";
import { AppNavigation } from "@/components/nav";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "RepoTrajectory", template: "%s / RepoTrajectory" },
  description: "Evidence-backed repository health, momentum, delivery, and contributor-risk intelligence",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><AppNavigation /><MotionShell>{children}</MotionShell><footer className="border-t border-[#343a34] bg-[#080a08] px-5 py-6 md:px-8 xl:px-10"><div className="mx-auto grid max-w-[1600px] gap-4 font-mono text-[9px] uppercase tracking-[.14em] text-[#70776f] md:grid-cols-[1fr_auto_1fr]"><span>RepoTrajectory / repository intelligence</span><span className="text-[#c7ff00]">Evidence over intuition</span><span className="md:text-right">Models are directional—not objective ratings</span></div></footer><FirstRunTutorial /></body></html>;
}
