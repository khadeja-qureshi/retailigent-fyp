-- Phase 15: readable labels for staff analytics.
-- Additive migration: preserve existing view column order and count semantics.

create or replace view public.v_high_interest_low_availability
with (security_invoker = true) as
select
    ds.product_id,
    ds.variant_id,
    ds.branch_id,
    count(*) as demand_signal_count,
    count(*) filter (where ds.fulfilled = false) as unfulfilled_signal_count,
    max(ds.created_at) as latest_signal_at,
    p.name as product_name,
    c.name as color_name,
    s.name as size_name,
    b.name as branch_name
from public.demand_signals ds
left join public.products p on p.id = ds.product_id
left join public.product_variants pv on pv.id = ds.variant_id
left join public.colors c on c.id = pv.color_id
left join public.sizes s on s.id = pv.size_id
left join public.branches b on b.id = ds.branch_id
where ds.fulfilled = false
group by
    ds.product_id, ds.variant_id, ds.branch_id,
    p.name, c.name, s.name, b.name;

create or replace view public.v_unavailable_searches
with (security_invoker = true) as
select
    ds.signal_type,
    ds.requested_size,
    ds.requested_color,
    count(*) as signal_count,
    max(ds.created_at) as latest_signal_at
from public.demand_signals ds
where ds.fulfilled = false
group by
    ds.signal_type,
    ds.requested_size,
    ds.requested_color;

create or replace view public.v_branch_inventory_summary
with (security_invoker = true) as
select
    bi.branch_id,
    count(*) as total_variants,
    count(*) filter (where bi.available_quantity > 2) as available_variants,
    count(*) filter (where bi.available_quantity between 1 and 2) as low_stock_variants,
    count(*) filter (where bi.available_quantity <= 0) as out_of_stock_variants,
    b.name as branch_name,
    b.city as branch_city
from public.branch_inventory bi
join public.branches b on b.id = bi.branch_id
group by bi.branch_id, b.name, b.city;

create or replace view public.v_product_demand_availability
with (security_invoker = true) as
select
    ds.product_id,
    ds.variant_id,
    count(*) as demand_signal_count,
    count(*) filter (where ds.fulfilled = false) as unfulfilled_signal_count,
    count(distinct ds.branch_id) as affected_branches,
    max(ds.created_at) as latest_signal_at,
    p.name as product_name,
    c.name as color_name,
    s.name as size_name
from public.demand_signals ds
left join public.products p on p.id = ds.product_id
left join public.product_variants pv on pv.id = ds.variant_id
left join public.colors c on c.id = pv.color_id
left join public.sizes s on s.id = pv.size_id
group by
    ds.product_id, ds.variant_id,
    p.name, c.name, s.name;
