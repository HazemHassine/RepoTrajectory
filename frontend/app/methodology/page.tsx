import { CheckCircleIcon, ClockIcon, ExclamationTriangleIcon } from "@heroicons/react/20/solid";

import { PageHeader, SectionHeader } from "@/components/ui";

const questions = [
  ["Which projects are gaining momentum?", "Available with baseline", "Uses star and contributor growth plus human commit, PR, and release acceleration. Growth remains provisional until snapshots span the window."],
  ["Which communities are healthy and active?", "Available", "Combines human contributors, delivery activity, resolved-item cycle times, PR acceptance, and stable release cadence."],
  ["Which projects depend on very few contributors?", "Available as a proxy", "Reports top-one/top-three human commit share and HHI. This is contribution concentration—not true maintainer permissions or knowledge."],
  ["How quickly are issues and PRs handled?", "Partially available", "Measures resolution and merge cycle time. First response and review latency require additional timeline ingestion."],
  ["How frequently does a project release?", "Available", "Counts published stable releases and reports cadence. Draft and prerelease behavior is kept separate."],
  ["Is development increasing or declining?", "Available", "Compares human activity with the immediately preceding equal window."],
  ["What correlates with repository growth?", "Collecting cohort", "Correlation is suppressed until the portfolio has enough repositories and historical snapshot coverage."],
  ["How do competing projects compare?", "Available", "Uses the same scoring window and shows evidence/confidence beside normalized and absolute measures."],
  ["Which smaller repositories are unusually healthy?", "Collecting cohort", "Requires a meaningful portfolio distribution before identifying under-the-radar outliers."],
  ["Which popular repositories are cooling?", "Collecting cohort", "Requires a popularity cohort plus sustained historical activity and freshness evidence."],
];

const scores = [
  { name: "Momentum", answer: "Is activity accelerating?", method: "Star growth 25% · contributor growth 20% · human commit acceleration 25% · PR acceleration 20% · release cadence 10%", caveat: "Growth inputs are unavailable until actual snapshots span the selected window." },
  { name: "Community health", answer: "Can the community respond and deliver?", method: "Active human contributors 20% · issue cycle 15% · PR merge cycle 15% · resolved-PR acceptance 20% · releases 10% · human commits 20%", caveat: "Cycle time is not first response time. Sparse samples are shown with explicit evidence counts." },
  { name: "Contribution concentration", answer: "How dependent is work on a small contributor set?", method: "Top-one share 45% · top-three share 25% · HHI 30%, calculated from recent human-authored commits where available", caveat: "This is a maintainer-dependency proxy, not a literal bus-factor measurement." },
];

export default function Methodology() {
  return <main><PageHeader eyebrow="Model governance" title="Methodology & coverage" description="RepoTrajectory makes analytical choices visible. Scores are heuristics, missing evidence stays visible, and every claim traces back to stored events." /><div className="mx-auto max-w-[1200px] space-y-6 px-5 py-6 md:px-8 xl:px-10"><section className="panel overflow-hidden"><SectionHeader title="What the platform can answer" description="Coverage of the ten core repository-intelligence questions." /><div className="divide-y divide-[#343a34]">{questions.map(([question,status,detail],index)=><div key={question} className="grid gap-3 px-5 py-4 md:grid-cols-[36px_1fr_170px_1.4fr] md:items-start"><span className="font-mono text-xs text-[#70776f]">{String(index+1).padStart(2,"0")}</span><h3 className="text-sm font-semibold">{question}</h3><Coverage status={status}/><p className="text-xs leading-5 text-[#9ba399]">{detail}</p></div>)}</div></section><section className="grid gap-4 lg:grid-cols-3">{scores.map((item)=><article key={item.name} className="panel p-5"><p className="eyebrow">Composite score</p><h2 className="mt-2 text-lg font-semibold">{item.name}</h2><p className="mt-1 text-sm text-[#b9c0b7]">{item.answer}</p><div className="my-4 h-px bg-[#343a34]"/><p className="text-xs font-semibold text-[#f1f4ec]">Weighting</p><p className="mt-2 text-xs leading-5 text-[#9ba399]">{item.method}</p><p className="mt-4 rounded-md bg-[#171b17] p-3 text-[11px] leading-4 text-[#c7ff00]">{item.caveat}</p></article>)}</section><section className="panel p-5"><h2 className="section-title">Data contract</h2><div className="mt-4 grid gap-5 text-xs leading-5 text-[#9ba399] md:grid-cols-3"><p><b className="block text-[#f1f4ec]">Raw remains raw</b>GitHub entities and historical observations are stored separately from metric snapshots.</p><p><b className="block text-[#f1f4ec]">Humans and automation differ</b>Bot commits remain visible as automation, but do not inflate human community scores.</p><p><b className="block text-[#f1f4ec]">No reconstructed history</b>Growth is unavailable—not zero—until captured snapshots provide a real baseline.</p></div></section></div></main>;
}

function Coverage({status}:{status:string}) { const pending=status.includes("Collecting"); const partial=status.includes("Partial")||status.includes("proxy")||status.includes("baseline"); const Icon=pending?ClockIcon:partial?ExclamationTriangleIcon:CheckCircleIcon; return <span className={`inline-flex w-fit items-center gap-1.5 text-[11px] font-semibold ${pending?"text-[#9ba399]":partial?"text-[#c7ff00]":"text-[#c7ff00]"}`}><Icon className="size-3.5"/>{status}</span>; }
