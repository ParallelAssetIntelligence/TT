-- Leads table backs /copilot/lookup, /copilot/brief, /copilot/respond.
--
-- Split: searchable / filterable fields live as top-level columns; the rest of
-- the enriched payload (LinkedIn, tenure, opener, etc.) lives in `enrichment`
-- jsonb so we can add new enrichment fields without schema migrations.

CREATE TABLE IF NOT EXISTS public.leads (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name                TEXT NOT NULL,
    company             TEXT,
    title               TEXT,
    phone               TEXT,
    email               TEXT,
    signal_tag          TEXT,          -- NEW_HIRE, LONG_TENURED, CAREER_MOVER, ...
    title_qualifier     TEXT,          -- DECISION_MAKER, INFLUENCER, IN_HOUSE, UNKNOWN
    enrichment          JSONB NOT NULL DEFAULT '{}',
    source_file         TEXT,          -- which uploaded file this row came from
    -- Enrichment tracking (lets the retry sweep find failed/stuck rows)
    enrichment_status   TEXT NOT NULL DEFAULT 'pending'
        CHECK (enrichment_status IN ('pending','done','failed','skipped')),
    enrichment_attempts INT NOT NULL DEFAULT 0,
    enrichment_error    TEXT,
    enriched_at         TIMESTAMPTZ,
    -- Canonical identity key for dedupe (phone:NNN... or nc:name|normalized_company)
    dedupe_key          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Case-insensitive name lookup (powers find_lead_by_name).
CREATE INDEX IF NOT EXISTS leads_name_lower_idx
    ON public.leads (LOWER(name));

CREATE INDEX IF NOT EXISTS leads_company_idx
    ON public.leads (company);

CREATE INDEX IF NOT EXISTS leads_signal_tag_idx
    ON public.leads (signal_tag);

CREATE INDEX IF NOT EXISTS leads_title_qualifier_idx
    ON public.leads (title_qualifier);

CREATE INDEX IF NOT EXISTS leads_enrichment_status_idx
    ON public.leads (enrichment_status);

CREATE UNIQUE INDEX IF NOT EXISTS leads_dedupe_key_uidx
    ON public.leads (dedupe_key)
    WHERE dedupe_key IS NOT NULL;

-- Allow the service-role key (used by the FastAPI backend) full access.
-- If you turn on RLS later, add policies for the anon/authenticated roles.
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access"
    ON public.leads
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- Dummy data for testing /copilot/lookup, /brief, /respond end-to-end.
-- Mirrors the example leads from context/meetingplan.md.
-- ---------------------------------------------------------------------------

INSERT INTO public.leads
    (name, company, title, phone, email, signal_tag, title_qualifier, enrichment, source_file)
VALUES
(
    'John Smith',
    'ABC Hospital',
    'Director of Facilities',
    '215-555-1234',
    'john.smith@abchospital.org',
    'NEW_HIRE',
    'DECISION_MAKER',
    jsonb_build_object(
        'city', 'Philadelphia',
        'state', 'PA',
        'linkedin_url', 'https://linkedin.com/in/johnsmith',
        'linkedin_headline', 'Director of Facilities at ABC Hospital',
        'linkedin_summary', 'Facilities leader with 15+ years in healthcare operations.',
        'tenure_months', 8,
        'tenure_label', 'NEW_HIRE',
        'prior_company_1', 'Penn Medicine',
        'prior_company_2', 'Temple Health',
        'script_used', 'Script 2: New Occupant',
        'personalized_opener',
            'Hey John, saw you joined ABC Hospital recently from Penn Medicine — we work with a lot of facility leads in that first-year ramp and have helped cut HVAC costs fast. Got 15 minutes this week?'
    ),
    'dummy_seed.xlsx'
),
(
    'Jane Doe',
    'XYZ School',
    'Maintenance Manager',
    '215-555-5678',
    'jane.doe@xyzschool.edu',
    'LONG_TENURED',
    'INFLUENCER',
    jsonb_build_object(
        'city', 'Pittsburgh',
        'state', 'PA',
        'linkedin_url', 'https://linkedin.com/in/janedoe',
        'linkedin_headline', 'Maintenance Manager at XYZ School',
        'linkedin_summary', 'Twelve years keeping XYZ''s campus running.',
        'tenure_months', 144,
        'tenure_label', 'LONG_TENURED',
        'prior_company_1', 'Pittsburgh Public Schools',
        'prior_company_2', NULL,
        'script_used', 'Script 3: Long-Tenured',
        'personalized_opener',
            'Jane, you''ve run XYZ for over a decade — quick question: when''s the last time your current vendor did a full systems audit to make sure you''re still getting max savings?'
    ),
    'dummy_seed.xlsx'
),
(
    'Leigh Guarino',
    'Westtown School',
    'Physical Plant Manager',
    '610-399-7627',
    'leigh.guarino@westtown.edu',
    'UNKNOWN',
    'IN_HOUSE',
    jsonb_build_object(
        'city', 'West Chester',
        'state', 'PA',
        'linkedin_url', 'https://linkedin.com/in/leighguarino',
        'linkedin_headline', 'Physical Plant Manager at Westtown School',
        'linkedin_summary', 'Facilities professional managing HVAC, water, and fire safety for an independent school.',
        'tenure_months', 36,
        'tenure_label', 'MID_TENURE',
        'prior_company_1', NULL,
        'prior_company_2', NULL,
        'script_used', 'Script 6: Reactive',
        'personalized_opener',
            'Hi Leigh, this is Matt from The Tustin Group — we''re a commercial building services company working with schools and institutions across the greater Philadelphia area. I''m calling because most facilities teams like yours are managing HVAC, water treatment, and fire safety across multiple vendors on a reactive basis…'
    ),
    'dummy_seed.xlsx'
),
(
    'Harsh Soni',
    'Liberty Property Trust',
    'Director of Operations',
    '484-555-9012',
    'harsh.soni@libertyproperty.com',
    'CAREER_MOVER',
    'DECISION_MAKER',
    jsonb_build_object(
        'city', 'Malvern',
        'state', 'PA',
        'linkedin_url', 'https://linkedin.com/in/harshsoni',
        'linkedin_headline', 'Director of Operations at Liberty Property Trust',
        'linkedin_summary', 'Operations leader focused on portfolio-wide facility performance across commercial real estate.',
        'tenure_months', 14,
        'tenure_label', 'MID_TENURE',
        'prior_company_1', 'Brandywine Realty Trust',
        'prior_company_2', 'CBRE',
        'script_used', 'Script 4: Career Mover',
        'personalized_opener',
            'Hey Harsh, saw you moved from Brandywine to Liberty about a year ago — usually a good window to revisit vendor contracts across a portfolio. Worth a 15-minute conversation on benchmarking HVAC and water spend?'
    ),
    'dummy_seed.xlsx'
);
