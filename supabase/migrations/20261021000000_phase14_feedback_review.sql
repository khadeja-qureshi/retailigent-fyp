-- Phase 14: feedback classification and staff review queue.
-- Additive migration; does not modify the original schema migration.

alter table public.feedback
    add column if not exists needs_review boolean not null default false;

alter table public.feedback
    add column if not exists classification_source text not null
    default 'unclassified'
    check (
        classification_source in ('ai', 'fallback', 'unclassified')
    );

create index if not exists idx_feedback_needs_review
    on public.feedback (created_at desc)
    where needs_review = true;

drop policy if exists insert_own_feedback on public.feedback;

create policy insert_own_feedback
on public.feedback
for insert
to authenticated
with check (
    customer_id = auth.uid()
    and ai_category is null
    and ai_sentiment is null
    and staff_category is null
    and staff_sentiment is null
    and staff_corrected = false
    and needs_review = false
    and classification_source = 'unclassified'
    and (
        conversation_id is null
        or exists (
            select 1
            from public.conversations c
            where c.id = feedback.conversation_id
              and c.customer_id = auth.uid()
        )
    )
);
