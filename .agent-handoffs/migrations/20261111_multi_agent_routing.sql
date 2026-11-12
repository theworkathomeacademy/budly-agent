-- Migration: 20261111_multi_agent_routing.sql
-- Project: budly-bros-dev (gfcgrpvvqstdohnkhmyl)
-- Description: Multi-agent routing schema extension for BROS agent handoff bridge

-- 1. Extend dispatch queue table with routing metadata
ALTER TABLE public.agent_handoff_dispatch 
ADD COLUMN IF NOT EXISTS from_agent_instance text,
ADD COLUMN IF NOT EXISTS return_to_agent text,
ADD COLUMN IF NOT EXISTS return_agent_instance text,
ADD COLUMN IF NOT EXISTS return_channel text DEFAULT 'SUPABASE+GITHUB',
ADD COLUMN IF NOT EXISTS return_status text,
ADD COLUMN IF NOT EXISTS return_payload text,
ADD COLUMN IF NOT EXISTS return_commit text;

-- 2. Update status check constraint to include RETURNED_TO_AGENT
ALTER TABLE public.agent_handoff_dispatch 
DROP CONSTRAINT IF EXISTS agent_handoff_dispatch_status_check;

ALTER TABLE public.agent_handoff_dispatch 
ADD CONSTRAINT agent_handoff_dispatch_status_check 
CHECK (status = ANY (ARRAY[
    'DRAFT'::text,
    'OWNER_REVIEW'::text,
    'AUTHORIZED'::text,
    'IN_PROGRESS'::text,
    'RETURNED_TO_MATT'::text,
    'RETURNED_TO_AGENT'::text,
    'BLOCKED'::text,
    'CLOSED'::text
]));

-- 3. Create dedicated agent handoff returns table
CREATE TABLE IF NOT EXISTS public.agent_handoff_returns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    handoff_id text UNIQUE NOT NULL REFERENCES public.agent_handoff_dispatch(handoff_id) ON DELETE CASCADE,
    from_agent text NOT NULL,
    from_agent_instance text NOT NULL,
    return_to_agent text NOT NULL,
    return_agent_instance text NOT NULL,
    return_status text NOT NULL,
    return_payload text NOT NULL,
    return_commit text NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.agent_handoff_returns ENABLE ROW LEVEL SECURITY;

-- 5. Enforce service-role-only access
REVOKE ALL ON public.agent_handoff_returns FROM anon, authenticated, public;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_handoff_returns TO service_role;

-- 6. Helper function for secure agent return retrieval
CREATE OR REPLACE FUNCTION public.get_agent_return(
    p_handoff_id text,
    p_agent text,
    p_instance text
)
RETURNS TABLE (
    handoff_id text,
    return_to_agent text,
    return_agent_instance text,
    return_status text,
    return_payload text,
    return_commit text,
    completed_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.handoff_id,
        r.return_to_agent,
        r.return_agent_instance,
        r.return_status,
        r.return_payload,
        r.return_commit,
        r.completed_at
    FROM public.agent_handoff_returns r
    WHERE r.handoff_id = p_handoff_id
      AND r.return_to_agent = p_agent
      AND r.return_agent_instance = p_instance;
END;
$$;

REVOKE ALL ON FUNCTION public.get_agent_return(text, text, text) FROM anon, authenticated, public;
GRANT EXECUTE ON FUNCTION public.get_agent_return(text, text, text) TO service_role;
