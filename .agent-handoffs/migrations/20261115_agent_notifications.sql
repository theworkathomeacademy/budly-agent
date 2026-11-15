-- Migration: 20261115_agent_notifications.sql
-- Project: budly-bros-dev (gfcgrpvvqstdohnkhmyl)
-- Description: Completion monitor and notification queue for BROS agent handoff bridge

CREATE TABLE IF NOT EXISTS public.agent_handoff_notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    handoff_id text NOT NULL REFERENCES public.agent_handoff_dispatch(handoff_id) ON DELETE CASCADE,
    from_agent text NOT NULL,
    from_agent_instance text NOT NULL,
    return_to_agent text NOT NULL,
    return_agent_instance text NOT NULL,
    project_folder text,
    project_area text,
    project_execution_id text,
    monitor_status text NOT NULL DEFAULT 'MONITOR_REGISTERED'
        CHECK (monitor_status IN (
            'MONITOR_REGISTERED',
            'MONITOR_ACTIVE',
            'RESULT_DETECTED',
            'NOTIFICATION_SENT',
            'MONITOR_CLOSED',
            'NOTIFICATION_FAILED',
            'MONITOR_EXPIRED'
        )),
    terminal_status text,
    return_commit text,
    notification_status text NOT NULL DEFAULT 'PENDING'
        CHECK (notification_status IN (
            'PENDING',
            'SENT',
            'FAILED',
            'SUPPRESSED'
        )),
    notification_channel text DEFAULT 'DESKTOP+GITHUB+SUPABASE',
    notification_payload jsonb,
    notification_sent_at timestamptz,
    last_checked_at timestamptz,
    error_message text,
    retry_count integer DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_notifications_handoff ON public.agent_handoff_notifications(handoff_id);
CREATE INDEX IF NOT EXISTS idx_agent_notifications_status ON public.agent_handoff_notifications(monitor_status, notification_status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_notifications_dedup ON public.agent_handoff_notifications(handoff_id, terminal_status);

ALTER TABLE public.agent_handoff_notifications ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.agent_handoff_notifications FROM anon, authenticated, public;
GRANT ALL ON public.agent_handoff_notifications TO service_role;

CREATE OR REPLACE FUNCTION public.get_agent_notifications(
    p_agent text,
    p_instance text
)
RETURNS TABLE (
    id uuid,
    handoff_id text,
    from_agent text,
    from_agent_instance text,
    return_to_agent text,
    return_agent_instance text,
    project_folder text,
    project_area text,
    terminal_status text,
    notification_status text,
    notification_payload jsonb,
    notification_sent_at timestamptz,
    monitor_status text
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        n.id,
        n.handoff_id,
        n.from_agent,
        n.from_agent_instance,
        n.return_to_agent,
        n.return_agent_instance,
        n.project_folder,
        n.project_area,
        n.terminal_status,
        n.notification_status,
        n.notification_payload,
        n.notification_sent_at,
        n.monitor_status
    FROM public.agent_handoff_notifications n
    WHERE n.return_to_agent = p_agent
      AND n.return_agent_instance = p_instance
    ORDER BY n.created_at DESC;
END;
$$;

REVOKE ALL ON FUNCTION public.get_agent_notifications(text, text) FROM anon, authenticated, public;
GRANT EXECUTE ON FUNCTION public.get_agent_notifications(text, text) TO service_role;
