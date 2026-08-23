# Analysis workspace

Use `notebooks/` for exploration and `scripts/` for reproducible studies. Read database credentials from the root `.env`; never embed tokens or export personally identifying data. Analyses should consume normalized database tables or versioned extracts and keep experimental formulas out of the API until validated.

Suggested first studies: contributor concentration versus subsequent commit decline, issue responsiveness versus contributor growth, and release cadence versus star-growth rate. Use time-aware train/test splits to avoid looking into the future.

