// Browser traffic stays on the web app's single public port. Next.js proxies `/backend` to the
// private API container, while server-rendered pages use the internal Docker hostname directly.
export const API = "/backend";
const SERVER_API = process.env.API_INTERNAL_URL ?? "http://localhost:8001";

function apiBase(): string {
  return typeof window === "undefined" ? SERVER_API : API;
}

export type Repo = {
  owner: string;
  name: string;
  full_name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  pushed_at: string | null;
  last_ingested_at: string | null;
  stars: number;
  forks: number;
  watchers: number;
  open_issues: number;
  default_branch: string;
  primary_language: string | null;
  license: string | null;
  archived: boolean;
};

export type Metric = {
  repository: string;
  calculated_at: string | null;
  window_days: number;
  momentum_score: number | null;
  health_score: number | null;
  bus_factor_risk: number | null;
  components: Record<string, any>;
};

export type Activity = { period: string; commits: number; merged_prs: number; issues_closed: number; releases: number };
export type History = { captured_at: string; stars: number; forks: number; open_issues: number; watchers: number };
export type Contributor = { login: string; contributions: number; avatar_url: string | null };
export type RepositoryRecord = Repo & { metric?: Metric };

export type Candidate = {
  id: number;
  github_id: number;
  repository_id: number | null;
  owner: string;
  name: string;
  full_name: string;
  description: string | null;
  primary_language: string | null;
  topics: string[];
  classification: string;
  classification_confidence: number;
  rejection_reason: string | null;
  stars: number;
  forks: number;
  pushed_at: string | null;
  source: string;
  source_score: number;
  trend_score: number;
  trend_components: Record<string, any>;
  tier: string;
  eligible: boolean;
  discovered_at: string;
  last_seen_at: string;
  promoted_at: string | null;
  next_refresh_at: string | null;
};

export type CollectionRecord = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  candidate_limit: number;
  active_limit: number;
  refresh_hours: number;
  enabled: boolean;
  candidate_count: number;
  selected_count: number;
  updated_at: string;
};

export type CollectorOverview = {
  tiers: Record<string, number>;
  classifications: Record<string, number>;
  jobs: Record<string, number>;
  github_rate: Record<string, any>;
  last_archive_hour: string | null;
  archive_hours_processed: number;
  archive_events_processed: number;
  archive_compressed_bytes: number;
  external_activity_rows: number;
  hydrated_repositories: number;
  database_size_bytes: number | null;
  oldest_queued_at: string | null;
  last_completed_at: string | null;
};

export type CollectorJob = {
  id: number;
  job_type: string;
  status: string;
  candidate_id: number | null;
  repository_id: number | null;
  priority: number;
  scheduled_for: string;
  locked_at: string | null;
  locked_by: string | null;
  attempts: number;
  max_attempts: number;
  payload: Record<string, any>;
  last_error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}/api/v1${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`API returned ${response.status} for ${path}`);
  return response.json();
}

export const api = {
  repos: () => get<Repo[]>("/repositories"),
  rankings: (kind: string, window = 30) => get<Metric[]>(`/rankings/${kind}?window=${window}`),
  repo: (owner: string, repo: string) => get<Repo>(`/repositories/${owner}/${repo}`),
  metrics: (owner: string, repo: string, window = 30) => get<Metric>(`/repositories/${owner}/${repo}/metrics?window=${window}`),
  activity: (owner: string, repo: string, weeks = 12) => get<Activity[]>(`/repositories/${owner}/${repo}/activity?weeks=${weeks}`),
  history: (owner: string, repo: string) => get<History[]>(`/repositories/${owner}/${repo}/history`),
  contributors: (owner: string, repo: string) => get<Contributor[]>(`/repositories/${owner}/${repo}/contributors`),
  collections: () => get<CollectionRecord[]>("/collections"),
  trending: (limit = 100) => get<Candidate[]>(`/trending?limit=${limit}`),
  collectorOverview: () => get<CollectorOverview>("/collector/overview"),
  collectorJobs: (limit = 100) => get<CollectorJob[]>(`/collector/jobs?limit=${limit}`),
};

export function mergeRepositories(repositories: Repo[], metrics: Metric[]): RepositoryRecord[] {
  const byName = new Map(metrics.map((metric) => [metric.repository.toLowerCase(), metric]));
  return repositories.map((repository) => ({ ...repository, metric: byName.get(repository.full_name.toLowerCase()) }));
}
