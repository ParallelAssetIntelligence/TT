-- Migration v2 for the leads table — apply once on top of create_leads_table.sql.
--
-- Adds:
--   1. enrichment tracking (status / attempts / error / enriched_at) so failed
--      SerpAPI runs are visible and can be retried.
--   2. dedupe_key column + unique partial index so duplicate inserts are caught
--      at the DB layer (insensitive to "Inc"/"LLC" suffixes, whitespace, casing).
--      Phone (last 10 digits) is preferred as the identity; falls back to a
--      normalized name+company composite when phone is missing.
--
-- Idempotent — safe to re-run.

ALTER TABLE public.leads
    ADD COLUMN IF NOT EXISTS enrichment_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (enrichment_status IN ('pending','done','failed','skipped')),
    ADD COLUMN IF NOT EXISTS enrichment_attempts INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS enrichment_error TEXT,
    ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dedupe_key TEXT;

CREATE INDEX IF NOT EXISTS leads_enrichment_status_idx
    ON public.leads (enrichment_status);

-- Full (non-partial) unique index — PostgREST's INSERT ... ON CONFLICT (col)
-- requires a matching full unique constraint; partial indexes are rejected
-- with error 42P10. NULL dedupe_key values are still permitted because
-- Postgres treats them as distinct in unique indexes (so legacy rows without
-- a dedupe_key won't collide with each other).
DROP INDEX IF EXISTS public.leads_dedupe_key_uidx;
CREATE UNIQUE INDEX leads_dedupe_key_uidx
    ON public.leads (dedupe_key);

-- ---------------------------------------------------------------------------
-- Helper expression for building the canonical dedupe key. Kept here as a
-- one-shot UPDATE so the Python writer doesn't need to depend on a SQL fn.
-- ---------------------------------------------------------------------------

UPDATE public.leads
SET dedupe_key = CASE
        WHEN phone IS NOT NULL
             AND length(regexp_replace(phone, '\D', '', 'g')) >= 10
        THEN 'phone:' || right(regexp_replace(phone, '\D', '', 'g'), 10)
        ELSE 'nc:' || lower(btrim(coalesce(name, ''))) || '|' ||
             regexp_replace(
                 lower(btrim(coalesce(company, ''))),
                 '[,.\s]+(inc|llc|ltd|corp|corporation|company|co|gmbh|sa|plc|pty|holdings)\.?\s*$',
                 ''
             )
    END
WHERE dedupe_key IS NULL;

-- Existing seed rows already have full enrichment (LinkedIn, opener, etc.).
-- Mark them as done so they don't get re-enriched if a retry sweep runs.
UPDATE public.leads
SET enrichment_status = 'done',
    enriched_at = COALESCE(enriched_at, now())
WHERE enrichment_status = 'pending'
  AND enrichment ? 'personalized_opener'
  AND (enrichment->>'personalized_opener') <> '';
