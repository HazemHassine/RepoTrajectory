# Discovery frontend integration

The homepage and Topics share `TopicPicker`. Parent routes select a category and
show its children; child routes retain the parent selection. Search in the picker
filters the loaded taxonomy locally. Category/project links disable eager prefetch
to avoid fetching every visible destination. No frontend taxonomy or repository
counts are fabricated.

Topic results use GET /api/v2/topics/{slug} with `q`, `language`, `sort`, `cursor`,
and `limit=30`. Sort values are relevance, stars, updated. Search/filter submission
starts at the first page. Pagination preserves filters in the URL, and browser
Back restores earlier URLs. The results count uses `total_count`, language options
use `languages`, and the next page uses `next_cursor`.

GET /api/v2/topics remains an array with additive `parent_slug` and
`repository_count`. Existing flat API responses retain their links under the old
AI category. Old detail responses omit pagination/filter controls and label the
number of returned projects as “shown”, rather than presenting it as a total.
The backend expansion supplies broader categories and additional catalog coverage.

The collection release feed is removed. Cards show description, language, stars,
last push, profile, and compare links. Discovery/compare/watchlist/profile copy is
shortened; source-specific limitations remain near the corresponding facts.
Compare no longer offers free-text context (which was not evaluated) or deployment
preference (which always returned unknown). The underlying API types remain intact.

Verification in this workspace:
- TypeScript `npx tsc --noEmit`: passed.
- `npm test`: passed, including URL/filter/cursor regression tests.
- Tailwind compilation and server rendering of picker/cards with isolated parent/
  child fixtures: passed.
- Full build remains unverified: Turbopack was denied its local worker socket,
  including an escalated retry; webpack fallback failed parsing TypeScript
  --showConfig output.
- Browser checks remain unverified: local HTTP binding and headless Chrome's
  socket operations were denied by this environment. Preview fixtures were only
  written under /tmp and never added to product data.

After rebuilding the combined application, verify category → subtopic navigation, topic search,
language filtering, all three sorts, multi-page browsing and Back, zero-result
states, and desktop/mobile layout against the running application.

Integration review replaced backend offset cursors with validated keyset positions,
added stale count-cache recovery, escaped literal search wildcards, and connected
search discovery directly to catalog metadata updates. Existing offset URLs must
restart from the first page; normal saved topic/filter URLs remain compatible.
