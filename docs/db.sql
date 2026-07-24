-- OIKONOMIA — DuckDB bootstrap for the derived economic database (deliverable #2).
--
-- Creates one view per shipped table over the parquet files in
-- data/processed/db/, so every query in docs/database.md runs verbatim.
--
--   duckdb -init docs/db.sql            # interactive shell
--   duckdb -init docs/db.sql -c "SELECT * FROM documents LIMIT 5"
--   python3 -c "import duckdb; duckdb.sql(open('docs/db.sql').read())"
--
-- Run it from the repository root (paths are relative). Nothing is copied: the
-- views read the parquet files in place, so a re-run of `oik db …` is picked up
-- the next time a query touches the view.

-- The spine and the coreference-lite people (written by `oik db export`).
CREATE OR REPLACE VIEW documents        AS SELECT * FROM read_parquet('data/processed/db/export/documents.parquet');
CREATE OR REPLACE VIEW persons_distinct AS SELECT * FROM read_parquet('data/processed/db/export/persons_distinct.parquet');

-- The fact tables.
CREATE OR REPLACE VIEW monetary   AS SELECT * FROM read_parquet('data/processed/db/monetary.parquet');
CREATE OR REPLACE VIEW prices     AS SELECT * FROM read_parquet('data/processed/db/prices.parquet');
CREATE OR REPLACE VIEW taxes      AS SELECT * FROM read_parquet('data/processed/db/taxes.parquet');
CREATE OR REPLACE VIEW persons    AS SELECT * FROM read_parquet('data/processed/db/persons.parquet');
CREATE OR REPLACE VIEW principals AS SELECT * FROM read_parquet('data/processed/db/principals.parquet');

-- The published autonomy curve (a derived summary, not a fact table).
CREATE OR REPLACE VIEW autonomy   AS SELECT * FROM read_parquet('data/processed/db/autonomy.parquet');

-- Convenience: silver-system money only, normalized and datable. `value_base`
-- is in drachmas here and ONLY here is it safe to sum — never across `system`.
CREATE OR REPLACE VIEW monetary_silver AS
SELECT * FROM monetary
WHERE system = 'silver' AND value_base IS NOT NULL AND century IS NOT NULL;

-- Convenience: the document text itself, for auditing a span. Requires the
-- (gitignored, re-derivable) corpus table — `oik ingest build`.
-- CREATE OR REPLACE VIEW corpus AS SELECT * FROM read_parquet('data/processed/corpus.parquet');
