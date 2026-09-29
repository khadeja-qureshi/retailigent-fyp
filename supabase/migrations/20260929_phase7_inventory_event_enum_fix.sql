-- Phase 7
-- Fix inventory-event emission so the CASE result is explicitly
-- cast to the retail_event_type enum.




create or replace function emit_inventory_retail_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_event_id uuid;
begin
    if new.available_quantity is distinct from old.available_quantity then
        insert into retail_events(
            event_type,
            variant_id,
            branch_id,
            previous_available_quantity,
            current_available_quantity
        )
        values (
            (
                case
                    when old.available_quantity <= 0
                     and new.available_quantity > 0
                    then 'restocked'
                    else 'inventory_changed'
                end
            )::retail_event_type,
            new.variant_id,
            new.branch_id,
            old.available_quantity,
            new.available_quantity
        )
        returning id into v_event_id;

        perform process_retail_event(v_event_id);
    end if;

    return new;
end;
$$;