import type { Metadata } from "next";

import { FirstRunTutorial } from "@/components/first-run-tutorial";
import { MotionShell } from "@/components/motion-shell";
import { AppNavigation } from "@/components/nav";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "RepoTrajectory", template: "%s / RepoTrajectory" },
  description:
    "Evidence-backed repository health, momentum, delivery, and contributor-risk intelligence",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppNavigation />
        <MotionShell>{children}</MotionShell>
        <footer className="border-t border-[#222222] bg-[#050505] px-5 py-6 md:px-8 xl:px-10">
          <div className="mx-auto flex max-w-[1600px] flex-col justify-between gap-4 font-mono text-[10px] text-[#646464] sm:flex-row sm:items-center">
            <span>RepoTrajectory — Open Source Repository Intelligence</span>
            <div className="flex items-center gap-4">
              <a href="/methodology" className="transition-colors hover:text-[#ffffff]">
                Methodology
              </a>
              <a href="/repositories" className="transition-colors hover:text-[#ffffff]">
                Repositories
              </a>
              <a href="/compare" className="transition-colors hover:text-[#ffffff]">
                Compare
              </a>
            </div>
          </div>
        </footer>
        <FirstRunTutorial />
      </body>
    </html>
  );
}
