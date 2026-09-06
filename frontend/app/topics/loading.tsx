export default function TopicsLoading() {
  return <main aria-label="Loading topics" aria-busy="true" className="mx-auto max-w-[1200px] space-y-6 px-5 py-10 motion-safe:animate-pulse">
    <p role="status" className="text-sm text-[#9a9a9a]">Loading topics…</p>
    <div className="h-64 rounded-xl border border-[#222] bg-[#0c0c0c]" />
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2, 3, 4, 5].map(key => <div key={key} className="h-48 rounded-lg border border-[#222] bg-[#0c0c0c]" />)}</div>
  </main>;
}
