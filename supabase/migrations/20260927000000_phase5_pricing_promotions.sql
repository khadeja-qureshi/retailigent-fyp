-- ============================================================================
-- RETAILIGENT
-- Phase 5 — Pricing & Promotions
-- Add batch authoritative variant pricing RPC
-- ============================================================================

create or replace function public.get_effective_variant_prices(
    p_variant_ids uuid[]
)
returns table (
    variant_id uuid,
    base_price numeric(12,2),
    effective_price numeric(12,2),
    discount_amount numeric(12,2)
)
language sql
stable
security definer
set search_path = public
as $$
    select
        v.id as variant_id,

        coalesce(
            v.price,
            p.base_price
        )::numeric(12,2) as base_price,

        get_effective_variant_price(
            v.id
        )::numeric(12,2) as effective_price,

        round(
            coalesce(
                v.price,
                p.base_price
            )
            -
            get_effective_variant_price(
                v.id
            ),
            2
        )::numeric(12,2) as discount_amount

    from product_variants v
    join products p
        on p.id = v.product_id

    where v.id = any(p_variant_ids)
      and v.is_active = true
      and p.is_active = true;
$$;