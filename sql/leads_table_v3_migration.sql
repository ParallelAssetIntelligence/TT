-- Migration v3 for the leads table — adds a verbatim copy of each Excel row.
--
-- Background: client wants the original lead Excel preserved in the table
-- exactly as it was uploaded, not just the subset we mapped to columns +
-- enrichment.extras. This new column stores every cell from the original
-- xlsx row keyed by its column header, so the table can faithfully
-- reproduce the source spreadsheet (and the /leads/download endpoint can
-- emit an xlsx that looks identical to what Matt uploaded, plus our
-- enrichment columns appended on the right).
--
-- Idempotent — safe to re-run.

ALTER TABLE public.leads
    ADD COLUMN IF NOT EXISTS raw_excel_row JSONB NOT NULL DEFAULT '{}';
