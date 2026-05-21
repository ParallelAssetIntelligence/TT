-- Create the "uploaded-leads" Supabase Storage bucket + RLS policies.
--
-- Used by POST /copilot/upload-file to stage raw .xlsx lead files that Matt
-- drops in the Copilot Studio chat. The downstream enrichment job reads
-- from this bucket and writes results to "enriched-files".
--
-- Run once in Supabase → SQL Editor.
--
-- The RLS policies below are only needed when the backend uses the anon
-- key. If you switch SUPABASE_KEY to the service_role key (recommended for
-- production), the policies are unnecessary because service_role bypasses
-- RLS — but leaving them in place is harmless.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'uploaded-leads',
    'uploaded-leads',
    true,
    52428800,  -- 50 MB
    ARRAY[
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel'
    ]
)
ON CONFLICT (id) DO NOTHING;

-- Allow the backend (anon role) to write to this bucket
DROP POLICY IF EXISTS "Allow uploads to uploaded-leads" ON storage.objects;
CREATE POLICY "Allow uploads to uploaded-leads"
    ON storage.objects
    FOR INSERT
    TO public
    WITH CHECK (bucket_id = 'uploaded-leads');

-- Allow reads (the bucket is public, but the policy is still required for anon SELECT)
DROP POLICY IF EXISTS "Allow reads from uploaded-leads" ON storage.objects;
CREATE POLICY "Allow reads from uploaded-leads"
    ON storage.objects
    FOR SELECT
    TO public
    USING (bucket_id = 'uploaded-leads');

-- Verify
SELECT id, public, file_size_limit, allowed_mime_types, created_at
FROM storage.buckets
WHERE id = 'uploaded-leads';
