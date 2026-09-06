"use client";
import { useState } from "react";
import { api, type CatalogRepo } from "@/lib/api";
import { productApi, type Comparison, type Constraints } from "@/lib/product-api";
import { FactValue, SourceAnchor } from "./project-brief";
import { WatchButton } from "./watch-button";

export function CompareExplorer({ repositories, initialA, initialB }: {
  repositories: CatalogRepo[]; initialA?: string; initialB?: string;
}) {
  const [first, setFirst] = useState(initialA ?? repositories[0]?.full_name ?? "");
  const [second, setSecond] = useState(initialB ?? repositories[1]?.full_name ?? "");
  const [constraints, setConstraints] = useState<Constraints>({ context: "" });
  const [result, setResult] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  return <div className="space-y-6">
    <form className="panel space-y-4 p-5" onChange={() => setResult(null)} onSubmit={async event => {
      event.preventDefault(); setLoading(true); setError(""); setResult(null);
      try {
        const profiles = await Promise.all([first, second].map(name => {
          const [owner, repo] = name.trim().split("/");
          if (!owner || !repo) throw new Error("Use owner/repository for both projects.");
          return api.v2.repository(owner, repo);
        }));
        setResult(await productApi.compare(profiles.map(p => p.catalog.github_id), constraints));
      } catch (error) { setError(error instanceof Error ? error.message : "Comparison unavailable."); }
      finally { setLoading(false); }
    }}>
      <fieldset disabled={loading} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {[[first, setFirst, "First repository"], [second, setSecond, "Second repository"]] .map(([value, setter, label]) => <label className="text-sm" key={String(label)}>{String(label)}
            <input required list="catalog-projects" className="input mt-1 w-full bg-[#111]" value={String(value)}
              onChange={e => (setter as (value: string) => void)(e.target.value)} placeholder="owner/repository" />
          </label>)}
        </div>
        <datalist id="catalog-projects">{repositories.map(repo => <option key={repo.github_id} value={repo.full_name} />)}</datalist>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm">Primary language<input className="input mt-1 w-full bg-[#111]" maxLength={100} value={constraints.language ?? ""} onChange={e => setConstraints({ ...constraints, language: e.target.value || undefined })} placeholder="Python" /></label>
          <label className="text-sm">License identifier<input className="input mt-1 w-full bg-[#111]" maxLength={100} value={constraints.license ?? ""} onChange={e => setConstraints({ ...constraints, license: e.target.value || undefined })} placeholder="Apache-2.0" /></label>
          <label className="text-sm">Package ecosystem<select className="input mt-1 w-full bg-[#111]" value={constraints.package_ecosystem ?? ""} onChange={e => setConstraints({ ...constraints, package_ecosystem: e.target.value as Constraints["package_ecosystem"] || undefined })}><option value="">Any / unknown</option><option value="npm">npm</option><option value="pypi">PyPI</option></select></label>
          <label className="text-sm">Repository push within days<input type="number" min={1} max={730} className="input mt-1 w-full bg-[#111]" value={constraints.activity_within_days ?? ""} onChange={e => setConstraints({ ...constraints, activity_within_days: e.target.value ? Number(e.target.value) : undefined })} /></label>
        </div>
        <button className="button-primary" type="submit">{loading ? "Comparing…" : "Compare"}</button>
      </fieldset>
    </form>
    {error && <p role="alert" className="panel p-4 text-amber-300">{error}</p>}
    {result && <>
      {result.constraints.context && <p className="panel p-4">Notes: {result.constraints.context}</p>}
      <div className="grid gap-5 lg:grid-cols-2">{result.projects.map(project => <article className="panel space-y-5 p-5" key={project.brief.github_id}>
        <h2 className="text-xl font-bold">{project.brief.full_name}</h2>
        <FactValue fact={project.brief.description} />
        <div className="space-y-3">{project.fit.map(fit => <div key={fit.constraint} className="border-l border-[#444] pl-3">
          <p className="font-semibold">{fit.constraint}: {fit.status}</p><p className="text-sm text-[#bbb]">{fit.explanation}</p>
          {fit.source_url && <SourceAnchor url={fit.source_url}>Evidence</SourceAnchor>}
        </div>)}</div>
        {project.brief.facts.map((fact, i) => <FactValue fact={fact} key={i} />)}
        <details><summary className="cursor-pointer text-[#ccf200]">Unknowns</summary><ul className="mt-3 space-y-2 text-sm">{project.brief.missing.map((item, i) => <li key={i}>{item}</li>)}</ul></details>
        <WatchButton githubId={project.brief.github_id} fullName={project.brief.full_name} />
      </article>)}</div>
    </>}
  </div>;
}
