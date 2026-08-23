import { RepositoryDirectory } from "@/components/repository-directory";
import { IngestionCommand } from "@/components/ingestion-command";
import { EmptyState, PageHeader, WindowControl } from "@/components/ui";
import { api, mergeRepositories, type RepositoryRecord } from "@/lib/api";

export default async function Repositories({ searchParams }: { searchParams: Promise<{ window?: string }> }) {
  const requested = Number((await searchParams).window ?? 30);
  const window = [30, 90, 365].includes(requested) ? requested : 30;
  let records: RepositoryRecord[] = [];
  let unavailable = false;
  try { const [repositories, metrics] = await Promise.all([api.repos(), api.rankings("momentum", window)]); records = mergeRepositories(repositories, metrics); } catch { unavailable = true; }
  return <main><PageHeader eyebrow="Coverage" title="Repository directory" description="Search the tracked universe and review scale, activity, health, and data freshness in one place." action={<div className="flex items-center gap-2"><WindowControl active={window}/><IngestionCommand/></div>} /><div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 xl:px-10">{unavailable ? <EmptyState title="The API is not available" description="Start FastAPI on port 8000 to load the repository directory." /> : records.length ? <RepositoryDirectory records={records} /> : <EmptyState />}</div></main>;
}
