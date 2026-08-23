import { CompareExplorer } from "@/components/compare-explorer";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
export default async function Compare({searchParams}:{searchParams:Promise<{a?:string;b?:string}>}){const query=await searchParams;let repos:any[]=[];try{repos=await api.repos()}catch{}return <main><PageHeader eyebrow="Decision workspace" title="Repository comparison" description="Compare normalized strategy signals and absolute operating evidence on the same analysis window."/><div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 xl:px-10"><CompareExplorer repositories={repos} initialA={query.a} initialB={query.b}/></div></main>}
