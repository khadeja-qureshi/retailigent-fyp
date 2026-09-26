-- ============================================================================
-- RETAILIGENT
-- Agentic AI-Powered Intelligent Retail Customer Support System
-- with Smart Sale Cart & Automated Purchase
--
-- FINAL DATABASE — v1.13 (Requirements-Aligned Schema Freeze Candidate)
-- Supabase PostgreSQL
--
-- IMPORTANT DEPLOYMENT MODE:
--   This file is the FRESH-INSTALL / INITIAL-MIGRATION master schema.
--   Apply it to a clean Retailigent Supabase project. After first deployment,
--   use new timestamped ALTER migrations for later changes; do not rerun an
--   older master file as if it were an incremental migration.
--
-- CHANGELOG v1.13 (requirements-alignment review on top of v1.12):
--   [FIX / REQUIREMENT] Added durable cross-conversation customer memory required
--              by Rev. 3: customer_memory_type enum, customer_memory table with
--              confidence/provenance/last-confirmed timestamps, service-role-only
--              upsert_customer_memory(), and get_customer_context_snapshot().
--              Customers can read and delete only their own remembered facts.
--   [FIX / REQUIREMENT] Added the Memory & Context Agent to agent_registry, bringing
--              the seeded architecture from 10 to the required 11 agents.
--   [FIX / REQUIREMENT] Added structured support_escalations.sentiment so the
--              staff dashboard can sort/filter tickets by sentiment as required;
--              customer-created tickets cannot forge this system-owned value.
--   [HARDEN / AUDIT] Inventory corrections now record explicit before/after stock
--              state; reservation release/conversion and expected purchase failures
--              also record before/after state where a row is mutated.
--   [REVIEW NOTE] Rev. 3 contains one policy-level wording conflict: its NFR says
--              every mutation must use service_role, while Phase 2 and the agent
--              flow explicitly require authenticated self-service writes for
--              profile/cart/wishlist/etc. This schema follows the detailed phase
--              plan: ordinary customer-owned bookkeeping uses RLS; all stock,
--              pricing, reservation, purchase, role, promotion and audit mutations
--              remain backend/service_role-only.
--
-- CHANGELOG v1.12 (this revision, on top of v1.11 — third review / schema freeze candidate):
--   [FIX / HIGH]   Hybrid search keyword candidates now use the exact indexed
--              expressions (`p.brand % query_text`, `v.sku % query_text`)
--              instead of wrapping indexed columns in COALESCE, and the
--              keyword candidate pool is explicitly bounded. Per-field
--              index-backed candidate passes are merged and capped before
--              exact scoring, so a deliberately low trigram threshold cannot
--              make the expensive scoring stage grow without bound.
--   [FIX / HIGH]   Pure semantic search and hybrid semantic candidates now use
--              an explicit bounded ANN candidate pass and do not let stale
--              embeddings contribute semantic scores. Hybrid keyword matching
--              can still surface a stale/missing-embedding variant, while the
--              returned `is_stale` flag tells FastAPI it needs re-embedding.
--   [FIX / HIGH]   Customer deactivation is now serialized with stock-holding
--              operations. create_reservation(), execute_mock_purchase(), and
--              convert_reservation_to_purchase() lock the relevant profiles
--              row (`FOR UPDATE`) before committing a new reservation/purchase.
--              execute_mock_purchase() also checks an existing idempotency key
--              BEFORE mutable account/branch state, so a replay of an already
--              completed request still returns the original success result.
--   [FIX / HIGH]   Cart history is now immutable after conversion. Customer cart
--              policies are split by operation: new carts must start active;
--              converted carts cannot be deleted; cart items can only be
--              inserted/updated/deleted while the parent cart is active.
--   [FIX / HIGH]   Smart Cart delete policy now preserves triggered/completed
--              rules and their event/audit history instead of allowing a
--              customer to delete a rule after it fired.
--   [FIX / MEDIUM] Alert trigger history is now system-owned: customers cannot
--              forge/clear triggered_at or mutate an already-triggered alert.
--              Wishlist writes are insert/delete only, and the database now
--              enforces at most one active cart per customer.
--   [FIX / MEDIUM] Embedding staleness tracking now also reacts to category,
--              color, and size name changes, because those names are part of
--              build_variant_search_document(). product_embeddings.updated_at
--              is now maintained by the standard updated_at trigger too.
--   [FIX / MEDIUM] Added integrity checks for customer budget ranges, branch
--              latitude/longitude, price-history windows, primary product-image
--              uniqueness, payment/order customer consistency, and explicit
--              non-empty idempotency-key validation in both purchase RPCs.
--   [REVIEW NOTE] The reported `updated_at` spoofing issue was already covered:
--              §28 has BEFORE UPDATE triggers on all customer-editable tables
--              that own an updated_at column, so client-supplied updated_at is
--              overwritten with now(). No duplicate timestamp mechanism added.
--   [REVIEW NOTE] notification_deliveries is intentionally the transactional
--              outbox. Delivery itself remains asynchronous in the worker;
--              keeping the notification/outbox row atomic with the triggering
--              retail transaction is intentional for the thesis MVP.
--   [DEPLOYMENT] This remains the fresh-install / initial-migration master SQL.
--              After it is applied once, future schema changes must be separate
--              versioned ALTER migrations; do not use this file as an updater
--              for an already-populated older Retailigent schema.
--
-- CHANGELOG v1.11 (this revision, on top of v1.10 — second external review):
--   [FIX / HIGH]   Smart Cart rules were still mutable in the fields that
--              actually define what gets bought after triggering.
--              guard_smart_cart_customer_update() (v1.10) froze status,
--              triggered_at/last_evaluated_at, and ownership once a rule
--              triggered/completed, but said nothing about branch_id,
--              quantity, target_price, min_discount_percentage, or
--              authorization_mode — a customer could still edit any of
--              those on an already-triggered rule before the Purchase
--              Agent acted on it. execute_mock_purchase() re-validates all
--              of these at purchase time, so this was never an
--              authorization bypass, but it did let a triggered rule drift
--              away from the conditions that actually caused it to fire.
--              The guard now also freezes branch_id/quantity/target_price/
--              min_discount_percentage/authorization_mode once
--              old.status is 'triggered' or 'completed': an evaluated
--              Smart Cart rule is immutable from the moment it triggers.
--   [FIX / HIGH]   search_variants_hybrid()'s v1.10 trigram indexes
--              (idx_products_name_trgm/idx_products_brand_trgm/
--              idx_product_variants_sku_trgm) were never actually usable by
--              the query: it called similarity(column, query_text) against
--              every active variant, and a bare similarity() call is not
--              index-backed — only pg_trgm's `%` operator is. The semantic
--              CTE had the same problem in the other direction: it computed
--              (1 - embedding <=> query_embedding) against every row in
--              product_embeddings instead of letting the ivfflat index do
--              an ANN probe. Rewritten to build a small candidate set FIRST
--              using the operators each index actually accelerates — `%`
--              for keyword candidates, `<=> ... limit` for a semantic ANN
--              probe — and only compute exact similarity()/cosine-distance
--              scores for that candidate set afterward. Also sets
--              pg_trgm.similarity_threshold = 0.05 for the duration of the
--              call (function-local SET), since `%`'s default 0.3 threshold
--              would otherwise have silently dropped the weak-but-valid
--              matches the old `keyword_score > 0.05` filter used to allow
--              through.
--
-- Everything below this point is unchanged v1.10 history, kept for context.
--
-- CHANGELOG v1.10 (this revision, on top of v1.9 — full external review):
--   [FIX / HIGH]   Smart Cart customers could reset a triggered/completed
--              rule. trg_smart_cart_guard only blocked transitions INTO
--              'triggered'/'completed', not OUT of them — a customer could
--              flip a triggered/completed rule back to 'active' and let it
--              fire (and auto-buy) again on the next qualifying retail
--              event. guard_smart_cart_customer_update() now blocks status
--              changes in both directions once a rule is
--              triggered/completed, and also protects triggered_at/
--              last_evaluated_at (system-only timestamps) from customer
--              modification.
--   [FIX / HIGH]   Branch-active validation had a check-then-act race:
--              execute_mock_purchase()/convert_reservation_to_purchase()/
--              create_reservation() each checked branches.is_active as a
--              separate statement before calling adjust_inventory(), so a
--              branch deactivated in the window between the check and the
--              inventory write could still silently fulfill an order.
--              adjust_inventory() — the single choke point every purchase/
--              reservation flow funnels through — now takes `select ...
--              for update` on the branches row itself for 'sale'/
--              'reservation' movements, closing the race atomically:
--              a concurrent deactivation blocks on the same row lock.
--   [FIX / MEDIUM] product_images had no constraint requiring variant_id to
--              actually belong to product_id on the same row. Added a
--              unique index on product_variants(id, product_id) and a
--              composite FK from product_images(variant_id, product_id) to
--              it (MATCH SIMPLE, so product-level images with variant_id
--              null are unaffected).
--   [FIX / MEDIUM] orders/order_items had no relationship enforced between
--              subtotal/discount/total or between line_total and
--              quantity*unit_price — only the purchase RPCs computed them
--              correctly, nothing stopped a future direct write from
--              breaking that. Added check(subtotal/discount/total >= 0),
--              check(total = subtotal - discount) on orders, and
--              check(line_total = quantity * unit_price),
--              check(unit_price >= 0), check(line_total >= 0) on
--              order_items.
--   [FIX / MEDIUM] activate_due_promotions()'s "no sale_started event yet"
--              check and its insert were separate statements with no
--              uniqueness constraint behind them, so two concurrent
--              scheduler ticks (or a scheduler tick racing the
--              emit_promotion_retail_event() trigger) could both insert a
--              sale_started event for the same promotion. Added a partial
--              unique index keyed on (event_type, promotion_id, variant_id)
--              — per-variant, since one promotion legitimately produces one
--              event per affected variant in a single pass — switched both
--              insert sites to `on conflict do nothing`, and added
--              `for update of p skip locked` in activate_due_promotions()
--              so concurrent runs don't even attempt the same promotion.
--   [FIX / MEDIUM] manage_own_cart's single "for all" policy let a customer
--              set carts.status to 'converted' themselves, with no purchase
--              behind it — a problem if 'converted' is later used for
--              conversion analytics/reporting. Added trg_cart_guard:
--              'active'/'abandoned' stay fully customer-controlled;
--              moving into or out of 'converted' is staff/service_role-only.
--   [FIX / MEDIUM] execute_mock_purchase()/convert_reservation_to_purchase()/
--              create_reservation() never checked profiles.is_active —
--              trg_profile_guard stops a customer from reactivating their
--              own deactivated account, but nothing stopped a purchase or
--              reservation from still going through for one, short of
--              FastAPI independently rejecting it first. All three RPCs now
--              check it themselves ('customer_inactive' reason_code / a
--              raised exception, matching each function's existing error
--              pattern).
--   [FIX / LOW]    Staff-attributed audit_logs rows (inventory corrections,
--              feedback/support-ticket updates, role changes, promotion
--              edits) recorded auth.uid() as the actor, which does not
--              reliably identify the human staff member when FastAPI calls
--              these as service_role. Added current_actor_id() (prefers a
--              session-local `app.actor_user_id` setting FastAPI sets per
--              request, falls back to auth.uid()) and switched every
--              staff-actor audit insert to use it.
--   [PERF]         search_variants_hybrid() ran similarity() against
--              products.name/brand and product_variants.sku with no
--              trigram index behind any of them. Added GIN trigram indexes
--              on all three so the keyword half of hybrid search scales
--              like the vector half already does.
--   [PERF/FIX]     product_embeddings had no way to know when an embedding
--              had gone stale after a product/variant edit — semantic
--              search could keep serving results built from outdated text
--              indefinitely. Added product_embeddings.is_stale (+ a partial
--              index over the stale rows), triggers on products and
--              product_variants that flag the affected embedding(s) stale
--              on a relevant field change, and surfaced is_stale in both
--              match_variants_semantic()'s and search_variants_hybrid()'s
--              return shape so FastAPI can decide whether to trigger a
--              re-embed or just warn. This still does not call an
--              embedding model from inside Postgres — refreshing a
--              flagged-stale row is still a FastAPI/backfill job.
--
-- Everything below this point is unchanged v1.9 history, kept for context.
--
-- CHANGELOG v1.9 (this revision, on top of v1.8):
--   [FIX]      execute_mock_purchase() accepted p_branch_id and adjusted
--              inventory against it with no branches.is_active check of
--              its own — it relied on the caller having already used
--              find_branch_for_purchase() (which does check), so a branch
--              active when selected but deactivated before the purchase
--              call could still silently fulfill the order. As the
--              deterministic purchase-enforcement layer, this function now
--              validates branch activity itself instead of trusting the
--              caller's prior lookup.
--   [FIX]      convert_reservation_to_purchase() only inherited the
--              active-branch check create_reservation() applied at
--              reservation time; a branch that closed between reservation
--              and conversion could still fulfill the order. Now checked
--              again at conversion.
--   [FIX]      process_retail_event(): the Smart Cart rule filter
--              `(branch_id is null or branch_id = e.branch_id)` silently
--              excluded every branch-pinned rule from branch-neutral
--              events (price_changed, promotion events all carry
--              e.branch_id = NULL, making `branch_id = NULL` evaluate to
--              NULL/false) — a rule like "buy from Branch A when price <=
--              X" never got evaluated on a price change. Now
--              `(branch_id is null or e.branch_id is null or branch_id =
--              e.branch_id)`: a branch-pinned rule is skipped only when
--              the event itself is branch-specific (e.g. an inventory
--              change) and names a different branch.
--   [FIX]      create_reservation() validated quantity, expiry, and branch
--              activity, but not that the product/variant itself was
--              active — inventory rows can outlive a product being
--              deactivated, so a reservation could be created for
--              something get_effective_variant_price() would later reject
--              at conversion as 'variant_unavailable'. Now validated at
--              creation for consistency with public catalog visibility.
--   [HARDEN]   The customer profile UPDATE policy (`id = auth.uid()`)
--              permits submitting a value for any column on the row; only
--              trg_profile_guard's explicit checks stop the ones that
--              matter. Extended that trigger to also protect created_at
--              (a system-owned audit field). profiles.id was already
--              implicitly protected, since the policy's WITH CHECK
--              requires new.id = auth.uid().
--
-- CHANGELOG v1.8 (on top of v1.7):
--   [FIX / MUST]   Inactive branches could still satisfy Smart Cart
--              evaluation, branch selection, and reservation creation.
--              evaluate_smart_cart_rule() and find_branch_for_purchase()
--              now join branches and require is_active = true wherever
--              they read branch_inventory; create_reservation() now raises
--              if the target branch is not active. A closed branch can no
--              longer be silently used to fulfill an order.
--   [FIX / MUST]   profiles.is_active sat alongside customer-editable
--              fields (full_name, phone, preferred_language) with no
--              column-level protection — update_own_profile only checked
--              `id = auth.uid()`. Added trg_profile_guard (mirrors the
--              existing trg_smart_cart_guard pattern): non-staff,
--              non-service_role callers can no longer change their own
--              is_active, including reactivating an account staff
--              deactivated.
--   [FIX / MUST]   insert_own_feedback and insert_own_support_ticket (on
--              support_escalations) only checked customer_id = auth.uid(),
--              letting a customer INSERT set system-owned fields directly
--              — ai_category/ai_sentiment/staff_category/staff_sentiment/
--              staff_corrected on feedback, and status/priority/
--              assigned_staff_id/handoff_summary/agent_context on
--              support_escalations. Both policies now force those columns
--              to their defaults and verify any supplied conversation_id
--              actually belongs to the inserting customer.
--   [FIX / SHOULD] promotions constraints were too loose: discount_value
--              could exceed 100 for a 'percentage' discount_type, ends_at
--              could precede starts_at, and product_id/variant_id could
--              both be set at once (ambiguous scope). Added three check
--              constraints closing all three gaps.
--   [FIX / SHOULD] build_variant_search_document() only pulled variant-
--              level fields (color/size/variant attributes), missing
--              products.attributes/material/gender — the flexible
--              product-level metadata (fabric, occasion, collection,
--              style, season, etc.) that a query like "elegant Eid lawn
--              kurta" depends on. Now included alongside the variant-level
--              fields.
--   [FIX / SHOULD] Idempotency-key handling in execute_mock_purchase() and
--              convert_reservation_to_purchase() only checked whether a
--              key had been used before, not whether it was being reused
--              for the SAME request. A key from a failed attempt could be
--              replayed with different customer/variant/branch/quantity/
--              rule (or a different reservation) and the code would
--              silently proceed as if it were a retry of the original
--              request. Both functions now compare the stored attempt
--              against the new call's parameters at every checkpoint and
--              return 'idempotency_key_reused_with_different_request' on
--              any mismatch.
--   [FIX / NICE]   alerts.target_price had no constraint; added
--              check(target_price is null or target_price >= 0).
--   [FIX / NICE]   public_variants only checked the variant's own
--              is_active, so a variant left active on a deactivated
--              product was still publicly visible. Now also requires the
--              parent product to be active (product_images already did
--              this correctly and needed no change).
--
-- CHANGELOG v1.7 (on top of v1.6):
--   [FIX / CONCURRENCY] execute_mock_purchase() and
--              convert_reservation_to_purchase(): fixed a race condition in
--              idempotency-key handling. Both functions opened with a
--              `select ... where idempotency_key = p_idempotency_key for
--              update` to guard *pre-existing* keys, but for a brand-new
--              key two concurrent calls both see "not found" there and
--              race at the later `insert ... on conflict(idempotency_key)
--              do update set status = excluded.status`. DO UPDATE let the
--              loser of that race silently receive the SAME
--              purchase_attempts.id as the winner via `returning id`, so
--              both went on to call adjust_inventory() for the same
--              logical purchase — one idempotency key producing two
--              inventory deductions and, in execute_mock_purchase(), two
--              orders. Fixed by changing the insert to `on conflict
--              (idempotency_key) do nothing` and explicitly handling the
--              case where it returns no id: the loser now locks the
--              winner's row (blocking until that transaction finishes),
--              then defers to it — returning 'already_completed' /
--              'attempt_in_progress' as appropriate, or, if the winner's
--              attempt ended in 'failed', legitimately reclaiming that same
--              row for a retry instead of starting a second one. A residual
--              edge case (the winner's transaction rolling back entirely
--              on an unanticipated error, so its row vanishes) is also
--              handled by re-inserting at that point.
--
-- CHANGELOG v1.6 (on top of v1.5):
--   [ADDED]    orders.branch_id — a nullable FK to branches(id), on delete
--              set null. execute_mock_purchase() and
--              convert_reservation_to_purchase() now populate it from
--              p_branch_id / the reservation's branch_id respectively, so
--              every order records which branch fulfilled it. Added
--              idx_orders_branch (branch_id, created_at desc) for
--              branch-level order history/reporting queries. This was
--              previously listed as "recommended, not applied" because it
--              changes an existing table's shape — now applied directly
--              since this is a fresh-install script, not a live migration
--              against data that already exists.
--   [ADDED]    Supabase Storage bucket `product-images` (public) with
--              explicit RLS policies on storage.objects: anyone can read,
--              only staff (is_staff()) or the trusted backend
--              (service_role, which bypasses RLS) can upload/update/
--              delete. product_images (§8) was metadata-only before this —
--              rows could reference an image_url with nowhere for that URL
--              to actually resolve. If you'd rather keep photos private,
--              flip `public` to false in that section and serve them via
--              signed URLs from FastAPI instead.
--
-- CHANGELOG v1.5 (on top of v1.4):
--   [FIX / API CHANGE] execute_mock_purchase() and
--              convert_reservation_to_purchase() now RETURN JSONB instead
--              of UUID, and no longer re-raise after writing a failure
--              record. Resolves the v1.4 known issue below: previously,
--              on an inventory-adjustment failure, the function wrote
--              purchase_attempts.status='failed' + an audit_logs row, then
--              re-raised — which rolled those very writes back along with
--              everything else, so failed attempts never actually
--              persisted. Every expected/business-rule failure (invalid
--              quantity, an unmatched Smart Cart rule, an expired/inactive
--              reservation, insufficient stock, etc.) now returns a
--              structured result instead of raising:
--                {
--                  "success": boolean,
--                  "order_id": uuid | null,
--                  "purchase_attempt_id": uuid | null,
--                  "reason_code": text | null,
--                  "reason": text | null
--                }
--              A bare `raise exception` is still possible for genuinely
--              unexpected errors (a real bug, an unanticipated constraint
--              violation) — those should still roll back everything, since
--              the function has no defined recovery for a state it didn't
--              anticipate. FastAPI callers must be updated: check
--              result->>'success' instead of wrapping the RPC call in
--              try/except and reading a returned uuid directly. Both
--              functions are `drop function if exists ... ; create or
--              replace function ...` since PostgreSQL requires a DROP when
--              a function's return type changes.
--
-- CHANGELOG v1.4 (on top of v1.3):
--   [FIX]      evaluate_smart_cart_rule(): when a Smart Cart rule has no
--              fixed branch_id, inventory availability now uses
--              max(available_quantity) across branches instead of
--              sum(available_quantity). Summing let a rule match (and
--              potentially auto-buy) when no single branch actually had
--              enough stock to fulfill the order — e.g. 1 unit at Dolmen +
--              1 at Lucky One summed to "2" for a quantity-2 rule.
--   [FIX]      evaluate_smart_cart_rule(): discount percentage is now
--              computed against the variant's actual effective regular
--              price (coalesce(variant.price, product.base_price)) instead
--              of always against product.base_price. A variant with its
--              own price override was previously getting its discount
--              computed off the wrong denominator (understating or
--              zeroing out a real discount).
--   [FIX]      support_ticket_messages insert policy: previously any
--              authenticated customer could insert a message marked
--              sender_type='staff' on any ticket they could reference by
--              id. Now customer messages require sender_id = auth.uid()
--              AND ownership of the ticket; staff messages require
--              sender_id = auth.uid() AND is_staff(). Agent messages are
--              written only by the trusted backend (service_role).
--   [FIX]      messages insert policy: an authenticated customer could
--              previously insert a message with role='assistant'/'system'/
--              'tool' into their own conversation, corrupting the agent
--              audit trail. Customer inserts are now forced to
--              role='user' with agent_key/tool_name null; the backend
--              writes every other role.
--   [FIX]      smart_cart_rules: the single "for all" customer policy is
--              now split into insert/update/delete. The insert policy
--              forces new customer-created rules to start
--              status='active', triggered_at=null, last_evaluated_at=null
--              — previously a customer could INSERT a rule already marked
--              'triggered'/'completed'. trg_smart_cart_guard (unchanged)
--              continues to protect status transitions on UPDATE.
--   [FIX]      Semantic search RPCs (match_variants_semantic,
--              search_variants_hybrid) are now service_role-only, matching
--              product_embeddings' RLS (which has no authenticated read
--              policy) and the rest of this schema's "FastAPI is the
--              trusted service-role layer" posture. Both now also require
--              the parent product to be active (p.is_active = true), not
--              just the variant.
--   [NOTE]     Corrected: the semantic-search section below is appended
--              to THIS file rather than shipped as a truly separate
--              0003_semantic_search.sql — v1.3's note calling it a
--              separate migration no longer matches how it's delivered.
--              It's still logically self-contained (its own extension,
--              tables, functions, grants) and can be split back out into
--              its own migration file if you run migrations that way.
--   [RESOLVED IN v1.5] execute_mock_purchase()/convert_reservation_to_purchase()
--              re-raising after writing a failure record — see the v1.5
--              entry above.
--   [RESOLVED IN v1.6] orders.branch_id and the product-images Storage
--              bucket — see the v1.6 entry above.
--
-- CHANGELOG v1.3 (on top of v1.2):
--   [CRITICAL] Table creation order fixed: `reservations` (§19) now comes
--              BEFORE `purchase_attempts` (§20). purchase_attempts.
--              reservation_id references reservations(id); on a fresh
--              database v1.2's order (purchase_attempts first) would fail
--              with "relation reservations does not exist". No column or
--              constraint changed — only the order of two CREATE TABLE
--              statements.
--   [FIX]      branch_inventory now has
--                  check (reserved_quantity + safety_stock <= on_hand_quantity)
--              at the table level, in addition to the existing checks in
--              adjust_inventory(), so privileged direct-SQL writes can no
--              longer create on_hand < reserved+safety states that
--              available_quantity would silently floor to 0.
--   [FIX]      smart_cart_events.retail_event_id now has a real foreign
--              key to retail_events(id) (on delete set null), added right
--              after retail_events is created. Previously this column had
--              no FK at all.
--   [FIX]      product_variants: added a partial unique index on
--              (product_id, color_id, size_id) where both color and size
--              are set, to stop duplicate variant rows for the same
--              product/color/size combination.
--   [FIX]      smart_cart_rules: added
--                  check(target_price is null or target_price >= 0)
--                  check(min_discount_percentage is null or
--                        min_discount_percentage between 0 and 100)
--              so out-of-range rule values can no longer be inserted.
--   [NOTE]     Semantic/vector product search lives in its own clearly
--              marked section of this same file (search "MIGRATION 0003"
--              below) — its extension, tables, functions and grants are
--              self-contained and decoupled from the core retail/agent
--              schema, so it can be split into its own migration file
--              later if you adopt separate numbered migrations.
--   [NOTE]     Real/sandbox payment integration (payment_events,
--              payment_authorizations) and a finer-grained inventory
--              ledger (separate on_hand_delta/reserved_delta columns) are
--              deliberately deferred — see the notes at the end of this
--              file. Not required for the thesis defense MVP.
--
-- CHANGELOG v1.2 (on top of v1.1):
--   [CRITICAL] get_effective_variant_price(): the promotion-selection
--              ORDER BY referenced a bare `v_price`, which PL/pgSQL bound to
--              the outer plpgsql variable of that name (no column alias
--              existed on the SELECT list), not the per-row computed
--              discount. So "cheapest promotion wins" never actually
--              evaluated the price — it silently fell through to whatever
--              came next in the ORDER BY. Fixed by computing the discount in
--              a subquery with a real alias (computed_price) and ordering by
--              that.
--
-- CHANGELOG v1.1 (on top of v1.0):
--   [FIX] execute_mock_purchase(): now verifies that when a Smart Cart rule
--         specifies a branch_id, the purchase's branch_id must match it —
--         previously a rule pinned to one branch could be fulfilled from any
--         branch.
--   [NEW] convert_reservation_to_purchase(): reservations previously had a
--         'converted' status with no function that ever set it. Converting
--         a reservation (in full or in part) now atomically decrements BOTH
--         on_hand_quantity and reserved_quantity by the converted amount (via
--         adjust_inventory), creates the order/order_items/payment rows, and
--         marks the reservation 'converted' (or shrinks its quantity on a
--         partial conversion). Added purchase_attempts.reservation_id to
--         trace these attempts the same way smart_cart_rule_id does for
--         Smart Cart purchases.
--   [FIX] get_effective_variant_price(): promotion selection now adds pr.id
--         as a final tiebreaker so two promotions tied on
--         (variant-vs-product, priority, computed price) resolve
--         deterministically instead of arbitrarily.
--   [FIX] public_images policy: no longer exposes images for
--         inactive products/variants — it now mirrors the same
--         is_active checks as public_products/public_variants.
--   [NEW] seed_initial_price_history(): a newly inserted product_variant now
--         gets a row 0 in price_history reflecting its starting price,
--         instead of price_history staying empty until the first price
--         change.
--   [NOTE] This script uses `create table if not exists`, which is safe on a
--          fresh database but will NOT alter an existing Retailigent table
--          (new columns, changed constraints, etc. are not retroactively
--          applied). If you are re-running this against a Supabase project
--          that already has the v1.0 schema, add the two new columns
--          manually first (see §19a below) or reset the project.
--
-- CHANGELOG vs original draft (carried over from v1.0):
--   [CRITICAL] RLS enabled on 10 previously-unprotected tables: branch_inventory,
--              inventory_movements, price_history, promotions, retail_events,
--              purchase_attempts, notification_deliveries, demand_signals,
--              agent_registry, audit_logs.
--   [CRITICAL] adjust_inventory(): fixed a bug where greatest(0, x) was checked
--              against < 0, which can never be true — the sellable-stock
--              validation was silently never firing. Also now audit-logs
--              staff-initiated movement types.
--   [CRITICAL] execute_mock_purchase(): now validates that a supplied Smart
--              Cart rule actually belongs to the calling customer, matches
--              variant/quantity, and is in a triggered+auto_buy state before
--              executing — prevents supplying an arbitrary rule id.
--   [CRITICAL] emit_promotion_retail_event() and activate_due_promotions() now
--              agree on event metadata (promotion_id), so the scheduler no
--              longer re-fires events the trigger already created; the
--              scheduler also now inserts+processes one event per variant in
--              an explicit loop instead of a multi-row INSERT...RETURNING INTO
--              (which was silently dropping all but one row's processing).
--   [CRITICAL] products.base_price changes now emit price_changed events for
--              every variant that inherits it (price IS NULL) — previously
--              only product_variants.price changes were wired up.
--   [FIX]      price_history.valid_to is now closed out when a new price row
--              is inserted.
--   [FIX]      Deterministic alert evaluation added (evaluate_alerts_for_variant)
--              so price-drop/restock/sale alerts actually fire, not just Smart
--              Cart rules.
--   [FIX]      Broader audit logging: purchase completion/failure, reservation
--              create/release, role grants/revokes, promotion create/update.
--   [FIX]      Analytics views marked security_invoker so RLS on their
--              underlying tables is evaluated as the caller, not the view
--              owner (Postgres views otherwise run as the owner by default).
--   [FIX]      "Drop all policies" loop scoped to Retailigent's own tables
--              instead of every policy in the public schema.
--   [FIX]      Function grants tightened: all inventory/purchase/reservation/
--              notification RPCs are now service_role-only (called from the
--              trusted FastAPI backend after it verifies the caller's JWT),
--              not directly callable by `authenticated`.
--   [MINOR]    products.brand no longer defaults to 'Khaadi' (nullable, no
--              default) — avoids implying demo data is real Khaadi inventory.
--   [MINOR]    Added get_stock_status() and find_branch_for_purchase() helpers.
-- ============================================================================


-- ============================================================================
-- 0. EXTENSIONS
-- ============================================================================

create extension if not exists pgcrypto;


-- ============================================================================
-- 1. ENUMS
-- ============================================================================

do $$ begin
    create type user_role as enum ('customer','staff','manager','admin');
exception when duplicate_object then null; end $$;

do $$ begin
    create type product_gender as enum ('women','men','kids','unisex','home','other');
exception when duplicate_object then null; end $$;

do $$ begin
    create type inventory_movement_type as enum (
        'restock','sale','reservation','reservation_release',
        'adjustment','return','damage','transfer_in','transfer_out'
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type order_status as enum ('pending','confirmed','cancelled','completed','failed');
exception when duplicate_object then null; end $$;

do $$ begin
    create type payment_status as enum ('pending','authorized','paid','failed','refunded');
exception when duplicate_object then null; end $$;

do $$ begin
    create type notification_type as enum (
        'price_drop','restock','sale','smart_cart_match','purchase','support','general'
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type notification_channel as enum ('in_app','email');
exception when duplicate_object then null; end $$;

do $$ begin
    create type notification_delivery_status as enum ('pending','processing','sent','failed');
exception when duplicate_object then null; end $$;

do $$ begin
    create type smart_cart_authorization as enum ('notify_only','auto_buy');
exception when duplicate_object then null; end $$;

do $$ begin
    create type smart_cart_status as enum ('active','triggered','paused','completed','cancelled');
exception when duplicate_object then null; end $$;

do $$ begin
    create type smart_cart_action as enum (
        'none','notified','auto_buy_started','purchase_completed','purchase_failed'
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type support_status as enum (
        'open','in_progress','waiting_customer','escalated','resolved','closed'
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type support_priority as enum ('low','normal','high','urgent');
exception when duplicate_object then null; end $$;

do $$ begin
    create type feedback_type as enum (
        'product','service','delivery','store','website','agent','general'
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type agent_type as enum ('language','orchestrator','specialist');
exception when duplicate_object then null; end $$;

do $$ begin
    create type agent_run_status as enum ('pending','running','completed','failed','escalated');
exception when duplicate_object then null; end $$;

do $$ begin
    create type agent_task_status as enum ('pending','running','completed','failed','skipped');
exception when duplicate_object then null; end $$;

do $$ begin
    create type reservation_status as enum ('active','released','expired','cancelled','converted');
exception when duplicate_object then null; end $$;

do $$ begin
    create type retail_event_type as enum (
        'price_changed','restocked','sale_started','inventory_changed'
    );
exception when duplicate_object then null; end $$;

do $$ begin
    create type customer_memory_type as enum (
        'product_interest','occasion_context','communication_style',
        'fabric_or_style_note','other'
    );
exception when duplicate_object then null; end $$;


-- ============================================================================
-- 2. PROFILES / ROLES
-- ============================================================================

create table if not exists profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    full_name text,
    phone text,
    preferred_language text not null default 'english',
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists user_roles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete cascade,
    role user_role not null,
    created_at timestamptz not null default now(),
    unique(user_id, role)
);


-- ============================================================================
-- 3. STORES / BRANCHES
-- ============================================================================

create table if not exists branches (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    city text not null,
    area text,
    address text,
    latitude numeric(10,7),
    longitude numeric(10,7),
    phone text,
    opening_time time,
    closing_time time,
    is_active boolean not null default true,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check(latitude is null or latitude between -90 and 90),
    check(longitude is null or longitude between -180 and 180)
);


-- ============================================================================
-- 4. CUSTOMER PREFERENCES
-- ============================================================================

create table if not exists customer_preferences (
    customer_id uuid primary key references profiles(id) on delete cascade,
    preferred_categories jsonb not null default '[]'::jsonb,
    preferred_colors jsonb not null default '[]'::jsonb,
    preferred_sizes jsonb not null default '[]'::jsonb,
    preferred_styles jsonb not null default '[]'::jsonb,
    budget_min numeric(12,2),
    budget_max numeric(12,2),
    allow_personalized_recommendations boolean not null default false,
    allow_email_notifications boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check(jsonb_typeof(preferred_categories) = 'array'),
    check(jsonb_typeof(preferred_colors) = 'array'),
    check(jsonb_typeof(preferred_sizes) = 'array'),
    check(jsonb_typeof(preferred_styles) = 'array'),
    check(budget_min is null or budget_min >= 0),
    check(budget_max is null or budget_max >= 0),
    check(budget_min is null or budget_max is null or budget_min <= budget_max)
);


-- ============================================================================
-- 5. PRODUCT TAXONOMY
-- ============================================================================

create table if not exists categories (
    id uuid primary key default gen_random_uuid(),
    parent_id uuid references categories(id) on delete set null,
    name text not null,
    slug text not null unique,
    description text,
    is_active boolean not null default true,
    sort_order integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists colors (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    hex_code text,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists sizes (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    -- Examples: XS, S, M, L, XL / 8, 10, 12 / 39, 40, 41 / FREE-SIZE / DOUBLE / KING / 18x18 / 100ML
    size_group text,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 6. PRODUCTS
-- ============================================================================

create table if not exists products (
    id uuid primary key default gen_random_uuid(),
    category_id uuid references categories(id) on delete set null,
    name text not null,
    slug text not null unique,
    sku text unique,
    description text,
    -- No hardcoded brand default: this is a Khaadi-inspired academic prototype,
    -- not a claim of real Khaadi inventory. Set explicitly per product/seed.
    brand text,
    gender product_gender,
    material text,
    care_instructions text,
    base_price numeric(12,2) not null check(base_price >= 0),
    -- Flexible product-level metadata: fabric, occasion, collection, style,
    -- season, room, fragrance family, dimensions, etc.
    attributes jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);


-- ============================================================================
-- 7. PRODUCT VARIANTS
-- ============================================================================

create table if not exists product_variants (
    id uuid primary key default gen_random_uuid(),
    product_id uuid not null references products(id) on delete cascade,
    color_id uuid references colors(id) on delete set null,
    size_id uuid references sizes(id) on delete set null,
    sku text unique,
    price numeric(12,2) check(price >= 0),
    barcode text,
    -- Cross-category attributes, e.g.:
    -- Clothing:  {"fabric":"Cambric","fit":"Regular"}
    -- Cushion:   {"dimensions":"18x18 inches","filling":"Polyester"}
    -- Bedsheet:  {"bed_size":"Double","set_pieces":4}
    -- Footwear:  {"material":"Leather","heel_type":"Flat"}
    -- Jewellery: {"material":"Metal","finish":"Gold-tone"}
    -- Fragrance: {"volume_ml":100,"fragrance_family":"Floral"}
    attributes jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- v1.3: prevent duplicate variants of the same product/color/size (e.g. two
-- separate rows both representing "Same Kurta + Black + Medium"). Partial
-- index so products without a color/size dimension aren't affected.
create unique index if not exists uq_clothing_variant
    on product_variants(product_id, color_id, size_id)
    where color_id is not null
      and size_id is not null;

-- v1.10 fix: lets product_images enforce that a variant_id it references
-- actually belongs to the same product_id on the row (see below) — a
-- composite foreign key needs a unique constraint on the referenced column
-- pair to point at.
create unique index if not exists uq_product_variants_id_product_id
    on product_variants(id, product_id);


-- ============================================================================
-- 8. PRODUCT IMAGES
-- ============================================================================

create table if not exists product_images (
    id uuid primary key default gen_random_uuid(),
    product_id uuid not null references products(id) on delete cascade,
    variant_id uuid references product_variants(id) on delete cascade,
    image_url text not null,
    alt_text text,
    image_type text not null default 'gallery',
    sort_order integer not null default 0,
    is_primary boolean not null default false,
    created_at timestamptz not null default now()
);

-- v1.10 fix: variant_id and product_id were each FKed independently, with
-- nothing requiring the referenced variant to actually belong to
-- product_id — a row could legally point variant_id at a completely
-- different product's variant while product_id said something else, and
-- RLS visibility logic that follows the variant relationship would then
-- disagree with the product_id on the same row. MATCH SIMPLE (the default)
-- means this composite FK only applies when variant_id is not null, so
-- product-level images (variant_id null) are unaffected.
do $$ begin
    alter table product_images
        add constraint fk_product_images_variant_product
        foreign key (variant_id, product_id)
        references product_variants(id, product_id)
        on delete cascade;
exception when duplicate_object then null; end $$;

-- v1.12: at most one primary image at the product level and at most one
-- primary image for each concrete variant. This prevents conflicting UI
-- "primary" choices while still allowing any number of gallery images.
create unique index if not exists uq_product_primary_image
    on product_images(product_id)
    where variant_id is null and is_primary = true;

create unique index if not exists uq_variant_primary_image
    on product_images(variant_id)
    where variant_id is not null and is_primary = true;


-- ============================================================================
-- 9. INVENTORY
-- ============================================================================

create table if not exists branch_inventory (
    id uuid primary key default gen_random_uuid(),
    branch_id uuid not null references branches(id) on delete cascade,
    variant_id uuid not null references product_variants(id) on delete cascade,
    on_hand_quantity integer not null default 0 check(on_hand_quantity >= 0),
    reserved_quantity integer not null default 0 check(reserved_quantity >= 0),
    safety_stock integer not null default 0 check(safety_stock >= 0),
    available_quantity integer generated always as (
        greatest(0, on_hand_quantity - reserved_quantity - safety_stock)
    ) stored,
    updated_at timestamptz not null default now(),
    unique(branch_id, variant_id),
    -- v1.3: protect the invariant at the table level, not just in
    -- adjust_inventory(). Without this, direct SQL access could set
    -- on_hand=4, reserved=8 and available_quantity would silently
    -- report 0 instead of surfacing the corrupted state.
    check (reserved_quantity + safety_stock <= on_hand_quantity)
);

create table if not exists inventory_movements (
    id uuid primary key default gen_random_uuid(),
    inventory_id uuid not null references branch_inventory(id) on delete cascade,
    movement_type inventory_movement_type not null,
    quantity_delta integer not null,
    reference_type text,
    reference_id uuid,
    reason text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 10. PRICE HISTORY
-- ============================================================================

create table if not exists price_history (
    id uuid primary key default gen_random_uuid(),
    variant_id uuid not null references product_variants(id) on delete cascade,
    price numeric(12,2) not null check(price >= 0),
    valid_from timestamptz not null default now(),
    valid_to timestamptz,
    created_at timestamptz not null default now(),
    check(valid_to is null or valid_to > valid_from)
);


-- ============================================================================
-- 11. PROMOTIONS
-- ============================================================================

create table if not exists promotions (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    product_id uuid references products(id) on delete cascade,
    variant_id uuid references product_variants(id) on delete cascade,
    discount_type text not null check(discount_type in ('percentage','fixed')),
    discount_value numeric(12,2) not null check(discount_value >= 0),
    starts_at timestamptz not null,
    ends_at timestamptz,
    priority integer not null default 0,
    is_active boolean not null default true,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    -- v1.8 fixes:
    --  - a percentage discount could previously exceed 100 (e.g. a typo'd
    --    "500" would zero out or invert the effective price elsewhere)
    --  - ends_at could precede starts_at, defining a promotion window that
    --    can never actually be active
    --  - product_id AND variant_id could both be set at once, which is
    --    ambiguous about whether the promotion targets the whole product or
    --    just one variant; exactly one must be set
    check(discount_type <> 'percentage' or discount_value <= 100),
    check(ends_at is null or ends_at > starts_at),
    check(num_nonnulls(product_id, variant_id) = 1)
);


-- ============================================================================
-- 12. CARTS
-- ============================================================================

create table if not exists carts (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id) on delete cascade,
    status text not null default 'active' check(status in ('active','converted','abandoned')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- v1.12: a customer can have many historical carts, but only one active cart.
create unique index if not exists uq_active_cart_per_customer
    on carts(customer_id)
    where status = 'active';

create table if not exists cart_items (
    id uuid primary key default gen_random_uuid(),
    cart_id uuid not null references carts(id) on delete cascade,
    variant_id uuid not null references product_variants(id),
    quantity integer not null check(quantity > 0),
    created_at timestamptz not null default now(),
    unique(cart_id, variant_id)
);


-- ============================================================================
-- 13. WISHLISTS
-- ============================================================================

create table if not exists wishlists (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id) on delete cascade,
    variant_id uuid not null references product_variants(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique(customer_id, variant_id)
);


-- ============================================================================
-- 14. ALERTS
-- ============================================================================

create table if not exists alerts (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id) on delete cascade,
    variant_id uuid not null references product_variants(id) on delete cascade,
    alert_type text not null check(alert_type in ('price_drop','restock','sale')),
    -- v1.8 fix: was previously unconstrained.
    target_price numeric(12,2) check(target_price is null or target_price >= 0),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    triggered_at timestamptz
);


-- ============================================================================
-- 15. SMART CART
-- ============================================================================

create table if not exists smart_cart_rules (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id) on delete cascade,
    variant_id uuid not null references product_variants(id),
    branch_id uuid references branches(id) on delete set null,
    quantity integer not null default 1 check(quantity > 0),
    target_price numeric(12,2),
    min_discount_percentage numeric(5,2),
    authorization_mode smart_cart_authorization not null default 'notify_only',
    status smart_cart_status not null default 'active',
    triggered_at timestamptz,
    last_evaluated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check(target_price is not null or min_discount_percentage is not null),
    -- v1.3: constrain sensible values, not just "one of the two is set" —
    -- previously a target_price of -500 or a min_discount_percentage of
    -- 700 were valid database values.
    check(target_price is null or target_price >= 0),
    check(min_discount_percentage is null or min_discount_percentage between 0 and 100)
);

create table if not exists smart_cart_events (
    id uuid primary key default gen_random_uuid(),
    smart_cart_rule_id uuid not null references smart_cart_rules(id) on delete cascade,
    retail_event_id uuid,
    event_type text not null,
    condition_snapshot jsonb not null default '{}'::jsonb,
    matched boolean not null default false,
    action_taken smart_cart_action not null default 'none',
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 16. RETAIL EVENTS
-- ============================================================================

create table if not exists retail_events (
    id uuid primary key default gen_random_uuid(),
    event_type retail_event_type not null,
    variant_id uuid not null references product_variants(id),
    branch_id uuid references branches(id),
    previous_price numeric(12,2),
    current_price numeric(12,2),
    previous_available_quantity integer,
    current_available_quantity integer,
    metadata jsonb not null default '{}'::jsonb,
    processed_at timestamptz,
    created_at timestamptz not null default now()
);

-- v1.3: smart_cart_events.retail_event_id had no foreign key (it's declared
-- before retail_events exists), so an invalid/arbitrary UUID could be
-- stored there. Add the constraint now that retail_events exists.
do $$ begin
    alter table smart_cart_events
        add constraint fk_smart_cart_events_retail_event
        foreign key (retail_event_id)
        references retail_events(id)
        on delete set null;
exception when duplicate_object then null; end $$;


-- ============================================================================
-- 17. ORDERS
-- ============================================================================

create table if not exists orders (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id),
    -- v1.6: Retailigent is branch-aware and the purchase workflow already
    -- knows the fulfilling branch (execute_mock_purchase/
    -- convert_reservation_to_purchase both take/derive one) — the order
    -- itself should carry it too, e.g. for branch-level sales reporting
    -- and so a customer's order history shows which store fulfilled it.
    branch_id uuid references branches(id) on delete set null,
    status order_status not null default 'pending',
    subtotal numeric(12,2) not null default 0,
    discount numeric(12,2) not null default 0,
    total numeric(12,2) not null default 0,
    currency text not null default 'PKR',
    source text not null default 'retailigent',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    -- v1.10 fix: subtotal/discount/total had no relationship to each other
    -- enforced by the database — only the purchase RPCs computed them
    -- correctly. These are immutable snapshots written solely by
    -- execute_mock_purchase()/convert_reservation_to_purchase() (both
    -- service_role-only), so the constraints simply make that invariant
    -- impossible to violate even via a future direct service_role write.
    check(subtotal >= 0),
    check(discount >= 0),
    check(total >= 0),
    check(total = subtotal - discount)
);

-- v1.12: composite identity used by payments/purchase_attempts to enforce
-- that an order reference and customer reference cannot disagree.
create unique index if not exists uq_orders_id_customer_id
    on orders(id, customer_id);

create table if not exists order_items (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null references orders(id) on delete cascade,
    variant_id uuid not null references product_variants(id),
    quantity integer not null check(quantity > 0),
    unit_price numeric(12,2) not null check(unit_price >= 0),
    line_total numeric(12,2) not null check(line_total >= 0),
    product_snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    -- v1.10 fix: nothing previously enforced line_total = quantity *
    -- unit_price; both purchase RPCs already compute it this way, this
    -- just makes the inconsistent state unrepresentable in the database.
    check(line_total = quantity * unit_price)
);


-- ============================================================================
-- 18. MOCK PAYMENTS
-- ============================================================================

create table if not exists payments (
    id uuid primary key default gen_random_uuid(),
    order_id uuid not null references orders(id) on delete cascade,
    customer_id uuid not null references profiles(id),
    amount numeric(12,2) not null check(amount >= 0),
    status payment_status not null default 'pending',
    provider text not null default 'mock',
    provider_reference text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

do $$ begin
    alter table payments
        add constraint fk_payments_order_customer
        foreign key (order_id, customer_id)
        references orders(id, customer_id)
        on delete cascade;
exception when duplicate_object then null; end $$;

create unique index if not exists uq_payments_provider_reference
    on payments(provider, provider_reference)
    where provider_reference is not null;


-- ============================================================================
-- 19. RESERVATIONS
--
-- v1.3: moved ABOVE purchase_attempts. purchase_attempts.reservation_id
-- references reservations(id), and PostgreSQL requires the referenced
-- table to exist at the point the foreign key is created. In v1.2 this
-- table came after purchase_attempts, so a fresh install would fail with
-- "relation reservations does not exist". Reordering fixes it with no
-- change to the table definitions themselves.
-- ============================================================================

create table if not exists reservations (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id),
    variant_id uuid not null references product_variants(id),
    branch_id uuid not null references branches(id),
    quantity integer not null check(quantity > 0),
    status reservation_status not null default 'active',
    expires_at timestamptz not null,
    released_at timestamptz,
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 20. PURCHASE ATTEMPTS
--
-- v1.1: added reservation_id so a reservation->purchase conversion is
-- traceable the same way a Smart Cart purchase is via smart_cart_rule_id.
-- If you're re-running this on an existing v1.0 database, add it manually:
--   alter table purchase_attempts add column if not exists
--       reservation_id uuid references reservations(id);
-- v1.3: no longer needs a table-ordering workaround — reservations (§19)
-- is now created before this table.
-- ============================================================================

create table if not exists purchase_attempts (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id),
    smart_cart_rule_id uuid references smart_cart_rules(id),
    reservation_id uuid references reservations(id),
    variant_id uuid not null references product_variants(id),
    branch_id uuid references branches(id),
    quantity integer not null check(quantity > 0),
    status text not null check(status in ('started','validated','completed','failed')),
    failure_reason text,
    validation_snapshot jsonb not null default '{}'::jsonb,
    idempotency_key text not null unique,
    order_id uuid references orders(id),
    created_at timestamptz not null default now(),
    completed_at timestamptz
);

do $$ begin
    alter table purchase_attempts
        add constraint fk_purchase_attempt_order_customer
        foreign key (order_id, customer_id)
        references orders(id, customer_id);
exception when duplicate_object then null; end $$;


-- ============================================================================
-- 21. NOTIFICATIONS
-- ============================================================================

create table if not exists notifications (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id) on delete cascade,
    type notification_type not null,
    title text not null,
    message text not null,
    metadata jsonb not null default '{}'::jsonb,
    read_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists notification_deliveries (
    id uuid primary key default gen_random_uuid(),
    notification_id uuid not null references notifications(id) on delete cascade,
    channel notification_channel not null,
    status notification_delivery_status not null default 'pending',
    attempts integer not null default 0,
    last_attempt_at timestamptz,
    sent_at timestamptz,
    error_message text,
    created_at timestamptz not null default now(),
    unique(notification_id, channel)
);


-- ============================================================================
-- 22. CONVERSATIONS
-- ============================================================================

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id) on delete cascade,
    title text,
    language text not null default 'english',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check(role in ('user','assistant','system','agent','tool')),
    content text,
    agent_key text,
    tool_name text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists conversation_state (
    conversation_id uuid primary key references conversations(id) on delete cascade,
    state jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);


-- ============================================================================
-- 22b. DURABLE CROSS-CONVERSATION CUSTOMER MEMORY
-- ============================================================================
create table if not exists customer_memory (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id) on delete cascade,
    memory_type customer_memory_type not null,
    memory_key text not null check(btrim(memory_key) <> ''),
    memory_value jsonb not null,
    confidence numeric(5,4) not null default 1.0 check(confidence between 0 and 1),
    source_conversation_id uuid references conversations(id) on delete set null,
    is_active boolean not null default true,
    last_confirmed_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(customer_id, memory_key)
);


-- ============================================================================
-- 23. FEEDBACK / SUPPORT
-- ============================================================================

create table if not exists feedback (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid references profiles(id) on delete set null,
    conversation_id uuid references conversations(id) on delete set null,
    feedback_type feedback_type not null,
    rating integer check(rating between 1 and 5),
    message text not null,
    ai_category text,
    ai_sentiment text,
    staff_category text,
    staff_sentiment text,
    staff_corrected boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists support_escalations (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid not null references profiles(id),
    conversation_id uuid references conversations(id),
    subject text not null,
    description text,
    status support_status not null default 'open',
    priority support_priority not null default 'normal',
    sentiment text,
    assigned_staff_id uuid references profiles(id),
    handoff_summary text,
    agent_context jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists support_ticket_messages (
    id uuid primary key default gen_random_uuid(),
    ticket_id uuid not null references support_escalations(id) on delete cascade,
    sender_id uuid references profiles(id),
    sender_type text not null check(sender_type in ('customer','staff','agent')),
    message text not null,
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 24. DEMAND SIGNALS
-- ============================================================================

create table if not exists demand_signals (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid references profiles(id) on delete set null,
    product_id uuid references products(id) on delete set null,
    variant_id uuid references product_variants(id) on delete set null,
    branch_id uuid references branches(id) on delete set null,
    signal_type text not null,
    requested_size text,
    requested_color text,
    fulfilled boolean not null default false,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 25. AGENT REGISTRY / RUNS / TASKS / TOOL CALLS
-- ============================================================================

create table if not exists agent_registry (
    id uuid primary key default gen_random_uuid(),
    agent_key text not null unique,
    display_name text not null,
    description text not null,
    agent_type agent_type not null,
    is_active boolean not null default true,
    config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists agent_runs (
    id uuid primary key default gen_random_uuid(),
    customer_id uuid references profiles(id) on delete set null,
    conversation_id uuid references conversations(id) on delete set null,
    root_agent_key text,
    input_text text,
    status agent_run_status not null default 'pending',
    final_response text,
    metadata jsonb not null default '{}'::jsonb,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists agent_tasks (
    id uuid primary key default gen_random_uuid(),
    agent_run_id uuid not null references agent_runs(id) on delete cascade,
    agent_key text not null,
    task_type text not null,
    input_payload jsonb not null default '{}'::jsonb,
    output_payload jsonb not null default '{}'::jsonb,
    status agent_task_status not null default 'pending',
    error_message text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists agent_tool_calls (
    id uuid primary key default gen_random_uuid(),
    agent_run_id uuid references agent_runs(id) on delete cascade,
    agent_task_id uuid references agent_tasks(id) on delete cascade,
    agent_key text not null,
    tool_name text not null,
    arguments jsonb not null default '{}'::jsonb,
    result jsonb,
    success boolean,
    error_message text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 26. AUDIT LOG
-- ============================================================================

create table if not exists audit_logs (
    id uuid primary key default gen_random_uuid(),
    actor_user_id uuid references profiles(id) on delete set null,
    actor_type text not null check(actor_type in ('user','staff','agent','system')),
    action text not null,
    entity_type text not null,
    entity_id uuid,
    before_data jsonb,
    after_data jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);


-- ============================================================================
-- 27. HELPER FUNCTIONS
-- ============================================================================

create or replace function is_staff()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (
        select 1 from user_roles ur
        where ur.user_id = auth.uid()
          and ur.role in ('staff','manager','admin')
    );
$$;

-- v1.10 fix: FastAPI calls the sensitive RPCs and triggers-worthy staff
-- actions (inventory corrections, promotion edits, support-ticket updates,
-- role changes) as `service_role`, under which `auth.uid()` does not
-- reliably identify which human staff member actually initiated the
-- action — audit_logs entries could end up with actor_type='staff' and
-- actor_user_id=null even though a real person triggered the write. This
-- helper prefers a per-request session setting FastAPI is expected to set
-- (`SET LOCAL app.actor_user_id = '<staff-profile-uuid>';`) right before
-- running a statement on behalf of an identified staff member, and falls
-- back to auth.uid() for ordinary authenticated (non-service_role) calls
-- where that already works correctly. Every audit_logs insert that
-- currently records a staff-side actor via auth.uid() now goes through
-- this function instead.
create or replace function current_actor_id()
returns uuid
language sql
stable
as $$
    select coalesce(
        nullif(current_setting('app.actor_user_id', true), '')::uuid,
        auth.uid()
    );
$$;

-- Consistent stock-status label so the frontend/agents never re-implement
-- the 0 / 1-2 / 3+ thresholds themselves.
create or replace function get_stock_status(p_available_quantity integer)
returns text
language sql
immutable
as $$
    select case
        when p_available_quantity <= 0 then 'out_of_stock'
        when p_available_quantity <= 2 then 'low_stock'
        else 'available'
    end;
$$;


-- ============================================================================
-- 28. GENERIC updated_at TRIGGER FUNCTION
-- ============================================================================

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

do $$
declare
    t text;
    tables text[] := array[
        'profiles','branches','customer_preferences','categories',
        'products','product_variants','conversations','conversation_state',
        'customer_memory','carts','smart_cart_rules','orders','feedback','support_escalations'
    ];
begin
    foreach t in array tables loop
        execute format(
            'drop trigger if exists trg_%I_updated_at on %I;
             create trigger trg_%I_updated_at
             before update on %I
             for each row execute function set_updated_at();',
            t, t, t, t
        );
    end loop;
end $$;


-- ============================================================================
-- 29. AUTH SIGNUP -> profiles + user_roles
-- ============================================================================

create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles(id, full_name)
    values (new.id, new.raw_user_meta_data ->> 'full_name')
    on conflict (id) do nothing;

    insert into public.user_roles(user_id, role)
    values (new.id, 'customer')
    on conflict (user_id, role) do nothing;

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function handle_new_user();


-- ============================================================================
-- 30. EFFECTIVE PRICE
--
-- v1.2 FIX: the previous ORDER BY referenced `v_price` as a bare identifier,
-- which PL/pgSQL resolved against the outer plpgsql variable of that name
-- (there was no `AS v_price` alias on the SELECT list), not the per-row
-- computed discount. That made "cheapest promotion wins" a no-op — it always
-- ordered by a constant. Fixed by computing the discounted price in a
-- subquery with a real column alias (computed_price) and ordering by that.
-- pr.id stays as the final deterministic tiebreaker (v1.1 fix).
-- ============================================================================

create or replace function get_effective_variant_price(p_variant_id uuid)
returns numeric
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_base numeric;
    v_product_id uuid;
    v_price numeric;
begin
    select coalesce(v.price, p.base_price), p.id
    into v_base, v_product_id
    from product_variants v
    join products p on p.id = v.product_id
    where v.id = p_variant_id
      and v.is_active = true
      and p.is_active = true;

    if v_base is null then
        return null;
    end if;

    select s.computed_price
    into v_price
    from (
        select
            case
                when pr.discount_type = 'percentage'
                    then greatest(0, v_base - (v_base * pr.discount_value / 100))
                when pr.discount_type = 'fixed'
                    then greatest(0, v_base - pr.discount_value)
                else v_base
            end as computed_price,
            pr.variant_id,
            pr.priority,
            pr.id
        from promotions pr
        where pr.is_active = true
          and pr.starts_at <= now()
          and (pr.ends_at is null or pr.ends_at > now())
          and (
              pr.variant_id = p_variant_id
              or (pr.variant_id is null and pr.product_id = v_product_id)
          )
    ) s
    order by
        case when s.variant_id is not null then 1 else 0 end desc,
        s.priority desc,
        s.computed_price asc,
        s.id
    limit 1;

    return coalesce(v_price, v_base);
end;
$$;


-- ============================================================================
-- 31. INVENTORY ADJUSTMENT (locks the inventory row)
--
-- FIXED: the sellable-stock check previously wrapped the computed value in
-- greatest(0, ...) before comparing it to < 0, which can never be true —
-- the check was silently dead code. It now validates the raw (possibly
-- negative) value. This is also what stops a mock purchase from eating into
-- reserved/safety stock.
-- ============================================================================

create or replace function adjust_inventory(
    p_variant_id uuid,
    p_branch_id uuid,
    p_on_hand_delta integer,
    p_reserved_delta integer,
    p_movement_type inventory_movement_type,
    p_reference_type text default null,
    p_reference_id uuid default null,
    p_reason text default null,
    p_metadata jsonb default '{}'::jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_inventory branch_inventory%rowtype;
    v_new_on_hand integer;
    v_new_reserved integer;
    v_new_available integer;
begin
    -- v1.10 fix: execute_mock_purchase()/convert_reservation_to_purchase()/
    -- create_reservation() each check `branches.is_active` before calling
    -- this function, but that check and this fulfillment write were two
    -- separate statements in two separate round trips — a branch could be
    -- deactivated in between (check-then-act race) and the order/reservation
    -- would still silently go through. adjust_inventory() is the single
    -- choke point every one of those flows funnels through, so the
    -- authoritative check now happens here, under a row lock on the branch
    -- itself: any concurrent `update branches set is_active = false` on this
    -- branch blocks until this transaction commits, and this transaction
    -- either sees an active branch and proceeds atomically or sees it's
    -- already inactive and aborts — there is no window in between. Only the
    -- two movement types that actually consume/hold sellable stock against a
    -- branch (a sale, or placing a reservation) need this; releasing a
    -- reservation or a staff-side stock correction must still be allowed
    -- regardless of the branch's current active flag.
    if p_movement_type in ('sale','reservation') then
        if not exists (
            select 1 from branches where id = p_branch_id and is_active = true for update
        ) then
            raise exception 'Branch is not active';
        end if;
    end if;

    select * into v_inventory
    from branch_inventory
    where variant_id = p_variant_id and branch_id = p_branch_id
    for update;

    if not found then
        raise exception 'Inventory record not found';
    end if;

    v_new_on_hand := v_inventory.on_hand_quantity + p_on_hand_delta;
    v_new_reserved := v_inventory.reserved_quantity + p_reserved_delta;

    if v_new_on_hand < 0 then
        raise exception 'Insufficient on-hand inventory';
    end if;

    if v_new_reserved < 0 then
        raise exception 'Reserved inventory cannot be negative';
    end if;

    -- Raw value, NOT wrapped in greatest() — this is the fix. The generated
    -- column on branch_inventory may still floor at 0 for display purposes;
    -- this check needs the true (possibly negative) figure to be meaningful.
    v_new_available := v_new_on_hand - v_new_reserved - v_inventory.safety_stock;

    if v_new_available < 0 then
        raise exception 'Insufficient sellable inventory';
    end if;

    update branch_inventory
    set on_hand_quantity = v_new_on_hand,
        reserved_quantity = v_new_reserved,
        updated_at = now()
    where id = v_inventory.id;

    insert into inventory_movements(
        inventory_id, movement_type, quantity_delta,
        reference_type, reference_id, reason, metadata
    )
    values(
        v_inventory.id, p_movement_type, p_on_hand_delta + p_reserved_delta,
        p_reference_type, p_reference_id, p_reason, p_metadata
    );

    -- Audit staff-initiated stock corrections (not the high-frequency,
    -- already-audited-elsewhere sale/reservation movement types).
    if p_movement_type in ('adjustment','restock','damage','transfer_in','transfer_out') then
        insert into audit_logs(
            actor_user_id, actor_type, action, entity_type, entity_id,
            before_data, after_data
        )
        values (
            current_actor_id(), 'staff', 'inventory_' || p_movement_type::text,
            'branch_inventory', v_inventory.id,
            jsonb_build_object(
                'variant_id', p_variant_id, 'branch_id', p_branch_id,
                'on_hand_quantity', v_inventory.on_hand_quantity,
                'reserved_quantity', v_inventory.reserved_quantity,
                'safety_stock', v_inventory.safety_stock,
                'available_quantity', v_inventory.available_quantity
            ),
            jsonb_build_object(
                'variant_id', p_variant_id, 'branch_id', p_branch_id,
                'on_hand_quantity', v_new_on_hand,
                'reserved_quantity', v_new_reserved,
                'safety_stock', v_inventory.safety_stock,
                'available_quantity', v_new_available,
                'on_hand_delta', p_on_hand_delta,
                'reserved_delta', p_reserved_delta,
                'reason', p_reason
            )
        );
    end if;

    return v_inventory.id;
end;
$$;


-- ============================================================================
-- 32. NOTIFICATIONS
-- ============================================================================

create or replace function queue_notification_delivery(
    p_notification_id uuid,
    p_channel notification_channel
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_id uuid;
begin
    insert into notification_deliveries(notification_id, channel, status)
    values(p_notification_id, p_channel, 'pending')
    on conflict(notification_id, channel) do nothing
    returning id into v_id;

    if v_id is null then
        select id into v_id
        from notification_deliveries
        where notification_id = p_notification_id and channel = p_channel;
    end if;

    return v_id;
end;
$$;

create or replace function create_notification(
    p_customer_id uuid,
    p_type notification_type,
    p_title text,
    p_message text,
    p_metadata jsonb default '{}'::jsonb,
    p_email boolean default false
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_notification_id uuid;
begin
    insert into notifications(customer_id, type, title, message, metadata)
    values(p_customer_id, p_type, p_title, p_message, p_metadata)
    returning id into v_notification_id;

    perform queue_notification_delivery(v_notification_id, 'in_app');

    if p_email then
        perform queue_notification_delivery(v_notification_id, 'email');
    end if;

    return v_notification_id;
end;
$$;


-- ============================================================================
-- 33. SMART CART EVALUATION
--
-- Matching a rule NEVER purchases directly. auto_buy_started tells the
-- Purchase Agent to start the controlled purchase workflow; the actual
-- purchase happens only in execute_mock_purchase().
-- ============================================================================

create or replace function evaluate_smart_cart_rule(
    p_rule_id uuid,
    p_event_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    r smart_cart_rules%rowtype;
    v_price numeric;
    v_inventory integer;
    v_discount numeric;
    v_price_condition boolean;
    v_discount_condition boolean;
    v_inventory_condition boolean;
    v_matched boolean;
    v_action smart_cart_action := 'none';
    v_snapshot jsonb;
begin
    select * into r from smart_cart_rules where id = p_rule_id for update;

    if not found then
        raise exception 'Smart Cart rule not found';
    end if;

    if r.status <> 'active' then
        return jsonb_build_object('matched', false, 'reason', 'rule_not_active');
    end if;

    v_price := get_effective_variant_price(r.variant_id);

    -- v1.8 fix: a closed/inactive branch must never count toward stock a
    -- rule can match against. Both branches below now join `branches` and
    -- require b.is_active = true.
    if r.branch_id is not null then
        select bi.available_quantity into v_inventory
        from branch_inventory bi
        join branches b on b.id = bi.branch_id
        where bi.variant_id = r.variant_id
          and bi.branch_id = r.branch_id
          and b.is_active = true;
    else
        -- v1.4: a single order still has to be fulfilled from ONE branch.
        -- Summing stock across branches could trigger auto-buy when no
        -- single branch actually has enough units (e.g. 1 at Dolmen + 1 at
        -- Lucky One summed to "2" for a quantity-2 rule, but no branch can
        -- fulfill it alone). Use the best single branch instead.
        select coalesce(max(bi.available_quantity), 0) into v_inventory
        from branch_inventory bi
        join branches b on b.id = bi.branch_id
        where bi.variant_id = r.variant_id
          and b.is_active = true;
    end if;

    -- v1.4: discount must be measured against the actual effective regular
    -- price of THIS variant (variant override if set, else the product's
    -- base_price) — not always against products.base_price. Previously a
    -- variant with its own price (e.g. 10,000 vs a base_price of 8,000)
    -- would compute discount off the wrong denominator and understate or
    -- zero out a real discount.
    select case when v_regular_price > 0
                then ((v_regular_price - v_price) / v_regular_price) * 100
                else 0 end
    into v_discount
    from (
        select coalesce(v.price, p.base_price) as v_regular_price
        from product_variants v
        join products p on p.id = v.product_id
        where v.id = r.variant_id
    ) regular;

    v_price_condition :=
        r.target_price is null
        or (v_price is not null and v_price <= r.target_price);

    v_discount_condition :=
        r.min_discount_percentage is null
        or (v_discount is not null and v_discount >= r.min_discount_percentage);

    v_inventory_condition := coalesce(v_inventory, 0) >= r.quantity;

    v_matched := v_price_condition and v_discount_condition and v_inventory_condition;

    v_snapshot := jsonb_build_object(
        'price', v_price,
        'available_quantity', v_inventory,
        'discount_percentage', v_discount,
        'target_price', r.target_price,
        'min_discount_percentage', r.min_discount_percentage,
        'price_condition', v_price_condition,
        'discount_condition', v_discount_condition,
        'inventory_condition', v_inventory_condition
    );

    if v_matched then
        update smart_cart_rules
        set triggered_at = now(), last_evaluated_at = now(), status = 'triggered'
        where id = r.id;

        v_action := case when r.authorization_mode = 'auto_buy'
                         then 'auto_buy_started' else 'notified' end;

        insert into smart_cart_events(
            smart_cart_rule_id, retail_event_id, event_type,
            condition_snapshot, matched, action_taken
        )
        values(r.id, p_event_id, 'condition_evaluated', v_snapshot, true, v_action);

        perform create_notification(
            r.customer_id, 'smart_cart_match', 'Smart Cart condition met',
            'A product in your Smart Cart now matches your conditions.',
            jsonb_build_object('smart_cart_rule_id', r.id, 'variant_id', r.variant_id, 'price', v_price)
        );
    else
        update smart_cart_rules set last_evaluated_at = now() where id = r.id;

        insert into smart_cart_events(
            smart_cart_rule_id, retail_event_id, event_type,
            condition_snapshot, matched, action_taken
        )
        values(r.id, p_event_id, 'condition_evaluated', v_snapshot, false, 'none');
    end if;

    return jsonb_build_object('matched', v_matched, 'action', v_action, 'snapshot', v_snapshot);
end;
$$;


-- ============================================================================
-- 33b. DETERMINISTIC ALERT EVALUATION (price_drop / restock / sale)
--
-- Previously only Smart Cart rules were evaluated automatically; ordinary
-- alerts (§3.1 MVP requirement) had no evaluation pipeline at all. One-shot:
-- an alert fires once, then is deactivated (is_active = false) so the
-- customer isn't spammed; they can re-create/edit it to watch again.
-- ============================================================================

create or replace function evaluate_alerts_for_variant(
    p_variant_id uuid,
    p_event_type retail_event_type,
    p_price numeric,
    p_event_id uuid default null
)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
    a record;
    v_matched_type text;
    n int := 0;
begin
    v_matched_type := case p_event_type
        when 'price_changed' then 'price_drop'
        when 'restocked' then 'restock'
        when 'sale_started' then 'sale'
        else null
    end;

    if v_matched_type is null then
        return 0;
    end if;

    for a in
        select * from alerts
        where variant_id = p_variant_id
          and is_active = true
          and alert_type = v_matched_type
          and (
              alert_type <> 'price_drop'
              or target_price is null
              or (p_price is not null and p_price <= target_price)
          )
        for update
    loop
        update alerts set is_active = false, triggered_at = now() where id = a.id;

        perform create_notification(
            a.customer_id,
            case a.alert_type when 'price_drop' then 'price_drop' when 'restock' then 'restock' else 'sale' end,
            initcap(replace(a.alert_type, '_', ' ')) || ' alert',
            'A product on your alert list now matches your condition.',
            jsonb_build_object('alert_id', a.id, 'variant_id', p_variant_id, 'price', p_price, 'retail_event_id', p_event_id)
        );

        n := n + 1;
    end loop;

    return n;
end;
$$;


-- ============================================================================
-- 34. RETAIL EVENT PROCESSOR
--
-- Now drives BOTH Smart Cart rule evaluation and ordinary alert evaluation.
-- ============================================================================

create or replace function process_retail_event(p_event_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    e retail_events%rowtype;
    r record;
    v_result jsonb;
    v_count integer := 0;
    v_alerts_count int;
begin
    select * into e from retail_events where id = p_event_id for update;

    if not found then
        raise exception 'Retail event not found';
    end if;

    if e.processed_at is not null then
        return jsonb_build_object('processed', true, 'event_id', e.id, 'already_processed', true);
    end if;

    -- v1.9 fix: previously `(branch_id is null or branch_id = e.branch_id)`.
    -- Branch-neutral events (price_changed, promotion events) are emitted
    -- with e.branch_id = NULL, so `branch_id = e.branch_id` evaluated to
    -- NULL (not true) for any branch-pinned rule — a rule like "buy from
    -- Branch A when price <= X" was silently skipped on every price/
    -- promotion event, even though evaluate_smart_cart_rule() itself knows
    -- how to check that specific branch's inventory. A branch-pinned rule
    -- must still be considered whenever the event itself doesn't carry
    -- branch information; it only needs to be skipped when the event IS
    -- branch-specific (e.g. an inventory change) and names a different
    -- branch.
    for r in
        select id from smart_cart_rules
        where status = 'active'
          and variant_id = e.variant_id
          and (branch_id is null or e.branch_id is null or branch_id = e.branch_id)
    loop
        v_result := evaluate_smart_cart_rule(r.id, e.id);
        v_count := v_count + 1;
    end loop;

    v_alerts_count := evaluate_alerts_for_variant(e.variant_id, e.event_type, e.current_price, e.id);

    update retail_events set processed_at = now() where id = e.id;

    return jsonb_build_object(
        'processed', true, 'event_id', e.id,
        'rules_evaluated', v_count, 'alerts_triggered', v_alerts_count
    );
end;
$$;


-- ============================================================================
-- 35. RESERVATIONS
--
-- create_reservation generates its own id up front and passes it straight
-- into adjust_inventory() as the movement reference — no post-hoc lookup,
-- so concurrent reservations from the same customer can't cross-contaminate.
-- Both functions now also write an audit_logs entry.
-- ============================================================================

create or replace function create_reservation(
    p_customer_id uuid,
    p_variant_id uuid,
    p_branch_id uuid,
    p_quantity integer,
    p_expires_at timestamptz
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_id uuid := gen_random_uuid();
    v_customer profiles%rowtype;
begin
    if p_quantity <= 0 then
        raise exception 'Reservation quantity must be positive';
    end if;

    if p_expires_at <= now() then
        raise exception 'Reservation expiry must be in the future';
    end if;

    -- v1.12: lock the customer row so a concurrent staff deactivation cannot
    -- commit between this validation and the stock reservation.
    select * into v_customer
    from profiles
    where id = p_customer_id
    for update;

    if not found or not v_customer.is_active then
        raise exception 'Customer account is not active';
    end if;

    -- v1.8 fix: a reservation must never be created against a closed branch.
    if not exists (select 1 from branches where id = p_branch_id and is_active = true) then
        raise exception 'Branch is not active';
    end if;

    -- v1.9 fix: without this, a reservation could be created for an
    -- inactive product/variant (inventory rows can still exist for one),
    -- then fail on conversion with 'variant_unavailable' since
    -- get_effective_variant_price() excludes inactive products/variants —
    -- an avoidable dead-end state. Reservation creation is now consistent
    -- with what public catalog visibility and pricing already consider
    -- available.
    if not exists (
        select 1
        from product_variants v
        join products p on p.id = v.product_id
        where v.id = p_variant_id
          and v.is_active = true
          and p.is_active = true
    ) then
        raise exception 'Variant is not active';
    end if;

    insert into reservations(id, customer_id, variant_id, branch_id, quantity, expires_at)
    values(v_id, p_customer_id, p_variant_id, p_branch_id, p_quantity, p_expires_at);

    perform adjust_inventory(
        p_variant_id, p_branch_id, 0, p_quantity,
        'reservation', 'reservation', v_id, 'Reservation created',
        jsonb_build_object('customer_id', p_customer_id)
    );

    insert into audit_logs(actor_user_id, actor_type, action, entity_type, entity_id, after_data)
    values (
        p_customer_id, 'system', 'reservation_created', 'reservations', v_id,
        jsonb_build_object('variant_id', p_variant_id, 'branch_id', p_branch_id,
                            'quantity', p_quantity, 'expires_at', p_expires_at)
    );

    return v_id;
end;
$$;

create or replace function release_reservation(
    p_reservation_id uuid,
    p_status reservation_status default 'released'
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    r reservations%rowtype;
begin
    select * into r from reservations where id = p_reservation_id for update;

    if not found or r.status <> 'active' then
        return false;
    end if;

    perform adjust_inventory(
        r.variant_id, r.branch_id, 0, -r.quantity,
        'reservation_release', 'reservation', r.id, 'Reservation released',
        jsonb_build_object('customer_id', r.customer_id)
    );

    update reservations set status = p_status, released_at = now() where id = r.id;

    insert into audit_logs(
        actor_user_id, actor_type, action, entity_type, entity_id,
        before_data, after_data
    )
    values (
        r.customer_id, 'system', 'reservation_released', 'reservations', r.id,
        jsonb_build_object(
            'status', r.status, 'quantity', r.quantity,
            'expires_at', r.expires_at, 'released_at', r.released_at
        ),
        jsonb_build_object(
            'status', p_status, 'quantity', r.quantity,
            'expires_at', r.expires_at, 'released_at', now()
        )
    );

    return true;
end;
$$;

create or replace function release_expired_reservations()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    r record;
    v_count integer := 0;
begin
    for r in
        select id from reservations
        where status = 'active' and expires_at <= now()
        for update skip locked
    loop
        if release_reservation(r.id, 'expired') then
            v_count := v_count + 1;
        end if;
    end loop;

    return v_count;
end;
$$;


-- ============================================================================
-- 35b. RESERVATION -> PURCHASE CONVERSION  [NEW in v1.1]
--
-- Reservations already carried a `converted` status, but no function ever
-- set it — buying a previously-reserved item just called
-- execute_mock_purchase(), which decremented on_hand_quantity but left
-- reserved_quantity untouched, letting the two drift apart. This function
-- converts a reservation (fully, or partially via p_quantity) into a
-- completed mock purchase: adjust_inventory() decrements BOTH on_hand and
-- reserved by the same amount in one call, so they can never disagree.
-- The Purchase Agent should call this (not execute_mock_purchase) whenever
-- the item being bought is coming out of an existing reservation.
-- ============================================================================

-- v1.5: return type changed from `uuid` to `jsonb`, same rationale as
-- execute_mock_purchase() above — expected/business failures now return a
-- structured result instead of writing an audit trail then re-raising
-- (which rolled the writes back). See the comment above
-- execute_mock_purchase() for the full explanation.
drop function if exists convert_reservation_to_purchase(uuid, text, integer);

create or replace function convert_reservation_to_purchase(
    p_reservation_id uuid,
    p_idempotency_key text,
    p_quantity integer default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_reservation reservations%rowtype;
    v_existing purchase_attempts%rowtype;
    v_quantity integer;
    v_price numeric;
    v_total numeric;
    v_order_id uuid;
    v_attempt_id uuid;
    v_product_snapshot jsonb;
    v_customer profiles%rowtype;
begin
    if p_idempotency_key is null or btrim(p_idempotency_key) = '' then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'invalid_idempotency_key', 'reason', 'Idempotency key is required'
        );
    end if;

    select * into v_existing
    from purchase_attempts
    where idempotency_key = p_idempotency_key
    for update;

    if found then
        -- v1.8 fix: an idempotency key is meant to make ONE specific
        -- request safe to retry, not to be reused as a free-floating token
        -- across different requests. Previously a caller could reuse a key
        -- from a failed attempt against a different reservation entirely
        -- (or a different quantity), and the code would silently proceed as
        -- if it were the same logical request. Checked before branching on
        -- status, so this also catches a mismatched replay of an
        -- already-completed or in-progress key.
        if v_existing.reservation_id is distinct from p_reservation_id
           or (p_quantity is not null and v_existing.quantity is distinct from p_quantity) then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                'reason_code', 'idempotency_key_reused_with_different_request',
                'reason', 'This idempotency key was already used for a different request'
            );
        end if;

        if v_existing.status = 'completed' and v_existing.order_id is not null then
            return jsonb_build_object(
                'success', true, 'order_id', v_existing.order_id,
                'purchase_attempt_id', v_existing.id,
                'reason_code', 'already_completed', 'reason', 'Idempotency key already fulfilled'
            );
        end if;
        if v_existing.status in ('started','validated') then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                'reason_code', 'attempt_in_progress', 'reason', 'Purchase attempt already in progress'
            );
        end if;
    end if;

    select * into v_reservation from reservations where id = p_reservation_id for update;

    if not found then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'reservation_not_found', 'reason', 'Reservation not found'
        );
    end if;

    if v_reservation.status <> 'active' then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'reservation_not_active', 'reason', 'Reservation is not active'
        );
    end if;

    -- v1.12: serialize account deactivation with reservation conversion.
    -- The row lock is held through the purchase transaction; a concurrent
    -- staff deactivation must wait until this conversion commits/rolls back.
    select * into v_customer
    from profiles
    where id = v_reservation.customer_id
    for update;

    if not found or not v_customer.is_active then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'customer_inactive', 'reason', 'Customer account is not active'
        );
    end if;

    if v_reservation.expires_at <= now() then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'reservation_expired', 'reason', 'Reservation has expired'
        );
    end if;

    -- v1.9 fix: create_reservation() only guarantees the branch was active
    -- at the time the reservation was made. Without this check here, a
    -- branch that closed afterward could still silently fulfill the order
    -- on conversion, which contradicts the branch-active invariant applied
    -- everywhere else in the purchase path.
    if not exists (select 1 from branches where id = v_reservation.branch_id and is_active = true) then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'branch_inactive', 'reason', 'Reservation branch is no longer active'
        );
    end if;

    v_quantity := coalesce(p_quantity, v_reservation.quantity);

    if v_quantity <= 0 or v_quantity > v_reservation.quantity then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'invalid_conversion_quantity', 'reason', 'Invalid conversion quantity'
        );
    end if;

    v_price := get_effective_variant_price(v_reservation.variant_id);

    if v_price is null then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'variant_unavailable', 'reason', 'Variant unavailable'
        );
    end if;

    select jsonb_build_object(
        'product_id', p.id, 'product_name', p.name,
        'variant_id', v.id, 'variant_sku', v.sku,
        'price', v_price, 'color_id', v.color_id, 'size_id', v.size_id,
        'attributes', v.attributes
    )
    into v_product_snapshot
    from product_variants v
    join products p on p.id = v.product_id
    where v.id = v_reservation.variant_id;

    -- v1.6a fix: this INSERT used to be `on conflict(idempotency_key) do
    -- update set status = excluded.status`. The v_existing check above
    -- protects a *pre-existing* key, but for a brand-new key two concurrent
    -- calls both pass that check (both see "not found"), then race here.
    -- With DO UPDATE, the loser of that race doesn't fail — it silently
    -- gets handed the SAME purchase_attempts.id as the winner via
    -- `returning id`, and both go on to call adjust_inventory() for the
    -- same reservation: one idempotency key, two inventory deductions.
    -- DO NOTHING makes only the winner receive an id here; the loser gets
    -- null and is handled explicitly below instead of silently proceeding.
    insert into purchase_attempts(
        customer_id, reservation_id, variant_id, branch_id, quantity,
        status, validation_snapshot, idempotency_key
    )
    values(
        v_reservation.customer_id, v_reservation.id, v_reservation.variant_id,
        v_reservation.branch_id, v_quantity,
        'started',
        jsonb_build_object('price', v_price, 'product_snapshot', v_product_snapshot),
        p_idempotency_key
    )
    on conflict(idempotency_key) do nothing
    returning id into v_attempt_id;

    if v_attempt_id is null then
        -- Lost the race: another call claimed this idempotency key between
        -- our lookup above and this insert. Lock the row it created —
        -- this blocks until that other transaction commits or rolls back —
        -- and defer to it instead of double-processing the same key.
        select * into v_existing
        from purchase_attempts
        where idempotency_key = p_idempotency_key
        for update;

        if found then
            -- v1.8 fix: same payload-match guard as the initial check above
            -- — a reused key must refer to the same reservation/quantity.
            if v_existing.reservation_id is distinct from v_reservation.id
               or v_existing.quantity is distinct from v_quantity then
                return jsonb_build_object(
                    'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                    'reason_code', 'idempotency_key_reused_with_different_request',
                    'reason', 'This idempotency key was already used for a different request'
                );
            end if;

            if v_existing.status = 'completed' and v_existing.order_id is not null then
                return jsonb_build_object(
                    'success', true, 'order_id', v_existing.order_id,
                    'purchase_attempt_id', v_existing.id,
                    'reason_code', 'already_completed', 'reason', 'Idempotency key already fulfilled'
                );
            end if;

            if v_existing.status in ('started', 'validated') then
                return jsonb_build_object(
                    'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                    'reason_code', 'attempt_in_progress', 'reason', 'Purchase attempt already in progress'
                );
            end if;

            -- The other attempt is in a terminal non-success state (e.g.
            -- 'failed'): this is a legitimate retry. Reclaim its row rather
            -- than starting a second row for the same key.
            v_attempt_id := v_existing.id;
            update purchase_attempts
            set status = 'started',
                customer_id = v_reservation.customer_id,
                reservation_id = v_reservation.id,
                variant_id = v_reservation.variant_id,
                branch_id = v_reservation.branch_id,
                quantity = v_quantity,
                validation_snapshot = jsonb_build_object('price', v_price, 'product_snapshot', v_product_snapshot),
                failure_reason = null,
                order_id = null,
                completed_at = null
            where id = v_attempt_id;
        else
            -- Extremely rare: the other transaction rolled back entirely
            -- (an unhandled error) after we lost the insert race above, so
            -- its row no longer exists. Claim the key ourselves.
            insert into purchase_attempts(
                customer_id, reservation_id, variant_id, branch_id, quantity,
                status, validation_snapshot, idempotency_key
            )
            values(
                v_reservation.customer_id, v_reservation.id, v_reservation.variant_id,
                v_reservation.branch_id, v_quantity,
                'started',
                jsonb_build_object('price', v_price, 'product_snapshot', v_product_snapshot),
                p_idempotency_key
            )
            returning id into v_attempt_id;
        end if;
    end if;

    begin
        -- Both on_hand and reserved drop by the converted quantity, so a
        -- reservation can never be double-counted against availability.
        perform adjust_inventory(
            v_reservation.variant_id, v_reservation.branch_id, -v_quantity, -v_quantity,
            'sale', 'reservation_conversion', v_reservation.id, 'Reservation converted to purchase',
            jsonb_build_object('customer_id', v_reservation.customer_id)
        );
    exception when others then
        update purchase_attempts
        set status = 'failed',
            failure_reason = sqlerrm,
            validation_snapshot = validation_snapshot || jsonb_build_object('failure', sqlerrm)
        where id = v_attempt_id;

        insert into audit_logs(
            actor_user_id, actor_type, action, entity_type, entity_id,
            before_data, after_data
        )
        values (
            v_reservation.customer_id, 'system', 'purchase_failed',
            'purchase_attempts', v_attempt_id,
            jsonb_build_object('status', 'started'),
            jsonb_build_object(
                'status', 'failed', 'reason', sqlerrm,
                'reservation_id', v_reservation.id, 'quantity', v_quantity
            )
        );

        -- v1.5: return instead of re-raising, so the writes above commit.
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', v_attempt_id,
            'reason_code', 'inventory_adjustment_failed', 'reason', sqlerrm
        );
    end;

    update purchase_attempts set status = 'validated' where id = v_attempt_id;

    v_total := v_price * v_quantity;

    insert into orders(customer_id, branch_id, status, subtotal, discount, total, currency, source)
    values(v_reservation.customer_id, v_reservation.branch_id, 'confirmed', v_total, 0, v_total, 'PKR', 'retailigent_reservation')
    returning id into v_order_id;

    insert into order_items(order_id, variant_id, quantity, unit_price, line_total, product_snapshot)
    values(v_order_id, v_reservation.variant_id, v_quantity, v_price, v_total, v_product_snapshot);

    insert into payments(order_id, customer_id, amount, status, provider, provider_reference)
    values(v_order_id, v_reservation.customer_id, v_total, 'paid', 'mock', 'MOCK-' || v_order_id::text);

    update purchase_attempts
    set status = 'completed', order_id = v_order_id, completed_at = now()
    where id = v_attempt_id;

    if v_quantity = v_reservation.quantity then
        update reservations set status = 'converted', released_at = now() where id = v_reservation.id;
    else
        update reservations set quantity = quantity - v_quantity where id = v_reservation.id;
    end if;

    insert into audit_logs(
        actor_user_id, actor_type, action, entity_type, entity_id,
        before_data, after_data
    )
    select
        v_reservation.customer_id, 'system', 'reservation_converted',
        'reservations', v_reservation.id,
        jsonb_build_object(
            'status', v_reservation.status,
            'quantity', v_reservation.quantity,
            'released_at', v_reservation.released_at
        ),
        jsonb_build_object(
            'status', r.status,
            'quantity', r.quantity,
            'released_at', r.released_at,
            'converted_quantity', v_quantity
        )
    from reservations r
    where r.id = v_reservation.id;

    perform create_notification(
        v_reservation.customer_id, 'purchase', 'Purchase completed',
        'Your reserved item has been purchased.',
        jsonb_build_object('order_id', v_order_id, 'variant_id', v_reservation.variant_id,
                            'quantity', v_quantity, 'total', v_total)
    );

    insert into audit_logs(actor_user_id, actor_type, action, entity_type, entity_id, after_data)
    values (v_reservation.customer_id, 'system', 'purchase_completed', 'orders', v_order_id,
            jsonb_build_object('variant_id', v_reservation.variant_id, 'quantity', v_quantity,
                                'total', v_total, 'reservation_id', v_reservation.id));

    return jsonb_build_object(
        'success', true, 'order_id', v_order_id, 'purchase_attempt_id', v_attempt_id,
        'reason_code', null, 'reason', null
    );
end;
$$;


-- ============================================================================
-- 36. FIND A BRANCH FOR AN AUTO-BUY PURCHASE
--
-- Smart Cart rules can be branch-agnostic (branch_id is null = "anywhere").
-- The Purchase Agent must resolve an actual branch before calling
-- execute_mock_purchase(); this deterministic helper does that lookup so the
-- logic lives in one place instead of being re-implemented per agent.
-- ============================================================================

create or replace function find_branch_for_purchase(
    p_variant_id uuid,
    p_quantity integer,
    p_preferred_branch_id uuid default null
)
returns uuid
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_branch_id uuid;
begin
    -- v1.8 fix: a closed/inactive branch must never be handed back as a
    -- fulfillment branch, even if its inventory row still shows stock.
    if p_preferred_branch_id is not null then
        select bi.branch_id into v_branch_id
        from branch_inventory bi
        join branches b on b.id = bi.branch_id
        where bi.variant_id = p_variant_id
          and bi.branch_id = p_preferred_branch_id
          and bi.available_quantity >= p_quantity
          and b.is_active = true;

        if v_branch_id is not null then
            return v_branch_id;
        end if;
    end if;

    select bi.branch_id into v_branch_id
    from branch_inventory bi
    join branches b on b.id = bi.branch_id
    where bi.variant_id = p_variant_id
      and bi.available_quantity >= p_quantity
      and b.is_active = true
    order by bi.available_quantity desc
    limit 1;

    return v_branch_id; -- null if no branch currently has enough sellable stock
end;
$$;


-- ============================================================================
-- 37. CONTROLLED MOCK PURCHASE
--
-- Deterministic purchase layer. Smart Cart does NOT purchase; the Purchase
-- Agent asks this function to execute the validated action. No real payment.
--
-- FIXED (v1.0): when a smart_cart_rule_id is supplied, it is now verified to
-- actually belong to this customer/variant, be in a 'triggered' state, and
-- be authorized for auto_buy, with a matching quantity — previously any
-- rule id could be passed through unchecked.
--
-- FIXED (v1.1): if the Smart Cart rule pins a specific branch_id, the
-- purchase's branch must match it — previously a rule that said "buy from
-- the Clifton branch" could silently be fulfilled from any branch that had
-- stock.
-- ============================================================================

-- v1.5: return type changed from `uuid` to `jsonb`. Previously, on an
-- inventory-adjustment failure this function wrote a 'failed' status +
-- failure_reason to purchase_attempts and an audit_logs row, then
-- RE-RAISED the exception — which rolled back those very writes along with
-- everything else in the function, since they share one transaction.
-- Failed attempts never actually persisted for the audit trail.
--
-- Now every expected/business-rule failure (invalid input, a Smart Cart
-- rule that doesn't match, insufficient stock, etc.) is returned as a
-- normal jsonb result instead of raised, so:
--   (a) the function always completes and commits normally, so the
--       purchase_attempts row (status='failed', failure_reason set) and
--       its audit_logs row actually persist, and
--   (b) FastAPI gets one consistent contract — check result->>'success'
--       instead of wrapping every call in try/except.
-- A `raise exception` is still possible for genuinely unexpected errors
-- this function doesn't anticipate (a real bug, a constraint violation
-- elsewhere) — those SHOULD roll back everything, because the system is in
-- a state this function doesn't know how to reason about.
--
-- Return shape: {
--   "success": boolean,
--   "order_id": uuid | null,
--   "purchase_attempt_id": uuid | null,
--   "reason_code": text | null,   -- short machine-readable code
--   "reason": text | null         -- human-readable detail
-- }
drop function if exists execute_mock_purchase(uuid, uuid, uuid, integer, text, uuid);

create or replace function execute_mock_purchase(
    p_customer_id uuid,
    p_variant_id uuid,
    p_branch_id uuid,
    p_quantity integer,
    p_idempotency_key text,
    p_smart_cart_rule_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_existing purchase_attempts%rowtype;
    v_rule smart_cart_rules%rowtype;
    v_customer profiles%rowtype;
    v_price numeric;
    v_total numeric;
    v_order_id uuid;
    v_attempt_id uuid;
    v_product_snapshot jsonb;
begin
    if p_quantity <= 0 then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'invalid_quantity', 'reason', 'Purchase quantity must be greater than zero'
        );
    end if;

    if p_idempotency_key is null or btrim(p_idempotency_key) = '' then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'invalid_idempotency_key', 'reason', 'Idempotency key is required'
        );
    end if;

    select * into v_existing
    from purchase_attempts
    where idempotency_key = p_idempotency_key
    for update;

    if found then
        -- v1.8 fix: an idempotency key is meant to make ONE specific
        -- request safe to retry, not a free-floating token reusable across
        -- different requests. Previously a caller could reuse a key from a
        -- failed attempt with a different customer/variant/branch/quantity/
        -- rule and the code would silently proceed. Checked before the
        -- status branches so a mismatched replay is caught even against an
        -- already-completed or in-progress key.
        if v_existing.customer_id is distinct from p_customer_id
           or v_existing.variant_id is distinct from p_variant_id
           or v_existing.branch_id is distinct from p_branch_id
           or v_existing.quantity is distinct from p_quantity
           or v_existing.smart_cart_rule_id is distinct from p_smart_cart_rule_id then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                'reason_code', 'idempotency_key_reused_with_different_request',
                'reason', 'This idempotency key was already used for a different request'
            );
        end if;

        if v_existing.status = 'completed' and v_existing.order_id is not null then
            return jsonb_build_object(
                'success', true, 'order_id', v_existing.order_id,
                'purchase_attempt_id', v_existing.id,
                'reason_code', 'already_completed', 'reason', 'Idempotency key already fulfilled'
            );
        end if;

        if v_existing.status in ('started','validated') then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                'reason_code', 'attempt_in_progress', 'reason', 'Purchase attempt already in progress'
            );
        end if;
    end if;

    -- v1.12: idempotency is resolved before mutable account/branch state.
    -- Therefore a replay of an already-completed logical purchase returns the
    -- same success result even if the account or branch was deactivated later.
    -- New/retried work locks the customer row so concurrent deactivation is
    -- serialized with the purchase.
    select * into v_customer
    from profiles
    where id = p_customer_id
    for update;

    if not found or not v_customer.is_active then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'customer_inactive', 'reason', 'Customer account is not active'
        );
    end if;

    -- Clean early validation for an already-inactive branch. adjust_inventory()
    -- still locks and re-checks the branch atomically at the stock-write choke
    -- point, so a deactivation racing after this check cannot slip through.
    if not exists (select 1 from branches where id = p_branch_id and is_active = true) then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'branch_inactive', 'reason', 'Purchase branch is not active'
        );
    end if;

    -- Smart Cart rule authorization check (fix #4, v1.0)
    if p_smart_cart_rule_id is not null then
        select * into v_rule from smart_cart_rules where id = p_smart_cart_rule_id for update;

        if not found then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_not_found', 'reason', 'Smart Cart rule not found'
            );
        end if;
        if v_rule.customer_id <> p_customer_id then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_ownership_mismatch',
                'reason', 'Smart Cart rule does not belong to this customer'
            );
        end if;
        if v_rule.variant_id <> p_variant_id then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_variant_mismatch',
                'reason', 'Smart Cart rule variant mismatch'
            );
        end if;
        if v_rule.status <> 'triggered' then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_not_triggered',
                'reason', 'Smart Cart rule is not in a triggered state'
            );
        end if;
        if v_rule.authorization_mode <> 'auto_buy' then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_not_auto_buy',
                'reason', 'Smart Cart rule is not authorized for automated purchase'
            );
        end if;
        if p_quantity <> v_rule.quantity then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_quantity_mismatch',
                'reason', 'Purchase quantity does not match Smart Cart rule quantity'
            );
        end if;
        -- v1.1 fix: branch-pinned rules must be fulfilled from that branch.
        if v_rule.branch_id is not null and v_rule.branch_id <> p_branch_id then
            return jsonb_build_object(
                'success', false, 'order_id', null, 'purchase_attempt_id', null,
                'reason_code', 'smart_cart_rule_branch_mismatch',
                'reason', 'Purchase branch does not match Smart Cart branch'
            );
        end if;
    end if;

    v_price := get_effective_variant_price(p_variant_id);

    if v_price is null then
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', null,
            'reason_code', 'variant_unavailable', 'reason', 'Variant unavailable'
        );
    end if;

    select jsonb_build_object(
        'product_id', p.id, 'product_name', p.name,
        'variant_id', v.id, 'variant_sku', v.sku,
        'price', v_price, 'color_id', v.color_id, 'size_id', v.size_id,
        'attributes', v.attributes
    )
    into v_product_snapshot
    from product_variants v
    join products p on p.id = v.product_id
    where v.id = p_variant_id;

    -- v1.6a fix: this INSERT used to be `on conflict(idempotency_key) do
    -- update set status = excluded.status`. The v_existing check above
    -- protects a *pre-existing* key, but for a brand-new key two concurrent
    -- calls both pass that check (both see "not found"), then race here.
    -- With DO UPDATE, the loser of that race doesn't fail — it silently
    -- gets handed the SAME purchase_attempts.id as the winner via
    -- `returning id`, and both go on to call adjust_inventory(): one
    -- idempotency key, two inventory deductions / two orders.
    -- DO NOTHING makes only the winner receive an id here; the loser gets
    -- null and is handled explicitly below instead of silently proceeding.
    insert into purchase_attempts(
        customer_id, smart_cart_rule_id, variant_id, branch_id, quantity,
        status, validation_snapshot, idempotency_key
    )
    values(
        p_customer_id, p_smart_cart_rule_id, p_variant_id, p_branch_id, p_quantity,
        'started',
        jsonb_build_object('price', v_price, 'product_snapshot', v_product_snapshot),
        p_idempotency_key
    )
    on conflict(idempotency_key) do nothing
    returning id into v_attempt_id;

    if v_attempt_id is null then
        -- Lost the race: another call claimed this idempotency key between
        -- our lookup above and this insert. Lock the row it created —
        -- this blocks until that other transaction commits or rolls back —
        -- and defer to it instead of double-processing the same key.
        select * into v_existing
        from purchase_attempts
        where idempotency_key = p_idempotency_key
        for update;

        if found then
            -- v1.8 fix: same payload-match guard as the initial check above.
            if v_existing.customer_id is distinct from p_customer_id
               or v_existing.variant_id is distinct from p_variant_id
               or v_existing.branch_id is distinct from p_branch_id
               or v_existing.quantity is distinct from p_quantity
               or v_existing.smart_cart_rule_id is distinct from p_smart_cart_rule_id then
                return jsonb_build_object(
                    'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                    'reason_code', 'idempotency_key_reused_with_different_request',
                    'reason', 'This idempotency key was already used for a different request'
                );
            end if;

            if v_existing.status = 'completed' and v_existing.order_id is not null then
                return jsonb_build_object(
                    'success', true, 'order_id', v_existing.order_id,
                    'purchase_attempt_id', v_existing.id,
                    'reason_code', 'already_completed', 'reason', 'Idempotency key already fulfilled'
                );
            end if;

            if v_existing.status in ('started', 'validated') then
                return jsonb_build_object(
                    'success', false, 'order_id', null, 'purchase_attempt_id', v_existing.id,
                    'reason_code', 'attempt_in_progress', 'reason', 'Purchase attempt already in progress'
                );
            end if;

            -- The other attempt is in a terminal non-success state (e.g.
            -- 'failed'): this is a legitimate retry. Reclaim its row rather
            -- than starting a second row for the same key.
            v_attempt_id := v_existing.id;
            update purchase_attempts
            set status = 'started',
                customer_id = p_customer_id,
                smart_cart_rule_id = p_smart_cart_rule_id,
                variant_id = p_variant_id,
                branch_id = p_branch_id,
                quantity = p_quantity,
                validation_snapshot = jsonb_build_object('price', v_price, 'product_snapshot', v_product_snapshot),
                failure_reason = null,
                order_id = null,
                completed_at = null
            where id = v_attempt_id;
        else
            -- Extremely rare: the other transaction rolled back entirely
            -- (an unhandled error) after we lost the insert race above, so
            -- its row no longer exists. Claim the key ourselves.
            insert into purchase_attempts(
                customer_id, smart_cart_rule_id, variant_id, branch_id, quantity,
                status, validation_snapshot, idempotency_key
            )
            values(
                p_customer_id, p_smart_cart_rule_id, p_variant_id, p_branch_id, p_quantity,
                'started',
                jsonb_build_object('price', v_price, 'product_snapshot', v_product_snapshot),
                p_idempotency_key
            )
            returning id into v_attempt_id;
        end if;
    end if;

    begin
        perform adjust_inventory(
            p_variant_id, p_branch_id, -p_quantity, 0,
            'sale', 'purchase_attempt', v_attempt_id, 'Mock Retailigent purchase',
            jsonb_build_object('customer_id', p_customer_id)
        );
    exception when others then
        update purchase_attempts
        set status = 'failed',
            failure_reason = sqlerrm,
            validation_snapshot = validation_snapshot || jsonb_build_object('failure', sqlerrm)
        where id = v_attempt_id;

        insert into audit_logs(
            actor_user_id, actor_type, action, entity_type, entity_id,
            before_data, after_data
        )
        values (
            p_customer_id, 'system', 'purchase_failed',
            'purchase_attempts', v_attempt_id,
            jsonb_build_object('status', 'started'),
            jsonb_build_object(
                'status', 'failed', 'reason', sqlerrm,
                'variant_id', p_variant_id, 'quantity', p_quantity
            )
        );

        -- v1.5: return instead of re-raising, so the writes above commit.
        return jsonb_build_object(
            'success', false, 'order_id', null, 'purchase_attempt_id', v_attempt_id,
            'reason_code', 'inventory_adjustment_failed', 'reason', sqlerrm
        );
    end;

    update purchase_attempts set status = 'validated' where id = v_attempt_id;

    v_total := v_price * p_quantity;

    insert into orders(customer_id, branch_id, status, subtotal, discount, total, currency, source)
    values(p_customer_id, p_branch_id, 'confirmed', v_total, 0, v_total, 'PKR', 'retailigent_smart_cart')
    returning id into v_order_id;

    insert into order_items(order_id, variant_id, quantity, unit_price, line_total, product_snapshot)
    values(v_order_id, p_variant_id, p_quantity, v_price, v_total, v_product_snapshot);

    insert into payments(order_id, customer_id, amount, status, provider, provider_reference)
    values(v_order_id, p_customer_id, v_total, 'paid', 'mock', 'MOCK-' || v_order_id::text);

    update purchase_attempts
    set status = 'completed', order_id = v_order_id, completed_at = now()
    where id = v_attempt_id;

    if p_smart_cart_rule_id is not null then
        update smart_cart_rules set status = 'completed' where id = p_smart_cart_rule_id;
    end if;

    perform create_notification(
        p_customer_id, 'purchase', 'Purchase completed',
        'Your Retailigent mock purchase has been completed.',
        jsonb_build_object('order_id', v_order_id, 'variant_id', p_variant_id,
                            'quantity', p_quantity, 'total', v_total)
    );

    insert into audit_logs(actor_user_id, actor_type, action, entity_type, entity_id, after_data)
    values (p_customer_id, 'system', 'purchase_completed', 'orders', v_order_id,
            jsonb_build_object('variant_id', p_variant_id, 'quantity', p_quantity,
                                'total', v_total, 'smart_cart_rule_id', p_smart_cart_rule_id));

    return jsonb_build_object(
        'success', true, 'order_id', v_order_id, 'purchase_attempt_id', v_attempt_id,
        'reason_code', null, 'reason', null
    );
end;
$$;


-- ============================================================================
-- 38. AUTOMATIC retail_events EMISSION
--
-- Makes the database the source of truth for the SaleEvent pipeline:
-- Product -> Inventory -> Smart Cart -> SaleEvent -> Purchase Orchestrator.
-- ============================================================================

-- 38a. Inventory changes (restock / depletion) at a specific branch
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
            event_type, variant_id, branch_id,
            previous_available_quantity, current_available_quantity
        )
        values (
            case when old.available_quantity <= 0 and new.available_quantity > 0
                 then 'restocked' else 'inventory_changed' end,
            new.variant_id, new.branch_id,
            old.available_quantity, new.available_quantity
        )
        returning id into v_event_id;

        perform process_retail_event(v_event_id);
    end if;

    return new;
end;
$$;

drop trigger if exists trg_inventory_retail_event on branch_inventory;
create trigger trg_inventory_retail_event
after update on branch_inventory
for each row execute function emit_inventory_retail_event();


-- 38b. Variant base-price changes — closes out the previous
-- price_history row (valid_to) instead of leaving every row open-ended.
create or replace function emit_price_retail_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_event_id uuid;
    v_old_price numeric;
    v_new_price numeric;
begin
    if new.price is distinct from old.price then
        v_old_price := coalesce(old.price, (select base_price from products where id = old.product_id));
        v_new_price := get_effective_variant_price(new.id);

        update price_history set valid_to = now() where variant_id = new.id and valid_to is null;
        insert into price_history(variant_id, price, valid_from)
        values (new.id, coalesce(v_new_price, new.price), now());

        insert into retail_events(event_type, variant_id, previous_price, current_price)
        values ('price_changed', new.id, v_old_price, v_new_price)
        returning id into v_event_id;

        perform process_retail_event(v_event_id);
    end if;

    return new;
end;
$$;

drop trigger if exists trg_variant_price_event on product_variants;
create trigger trg_variant_price_event
after update on product_variants
for each row execute function emit_price_retail_event();


-- 38b-2. NEW in v1.1: seed price_history with a starting row when a variant
-- is first created, so history isn't empty until the first price change.
create or replace function seed_initial_price_history()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_price numeric;
begin
    v_price := get_effective_variant_price(new.id);

    insert into price_history(variant_id, price, valid_from)
    values (
        new.id,
        coalesce(v_price, new.price, (select base_price from products where id = new.product_id)),
        now()
    );

    return new;
end;
$$;

drop trigger if exists trg_variant_initial_price_history on product_variants;
create trigger trg_variant_initial_price_history
after insert on product_variants
for each row execute function seed_initial_price_history();


-- 38c. products.base_price changes. Only affects variants that
-- inherit it (product_variants.price IS NULL) — a variant with its own
-- explicit price override is unaffected by coalesce(v.price, p.base_price).
create or replace function emit_product_base_price_retail_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_variant record;
    v_new_price numeric;
    v_event_id uuid;
begin
    if new.base_price is distinct from old.base_price then
        for v_variant in
            select id from product_variants where product_id = new.id and price is null
        loop
            v_new_price := get_effective_variant_price(v_variant.id);

            update price_history set valid_to = now() where variant_id = v_variant.id and valid_to is null;
            insert into price_history(variant_id, price, valid_from)
            values (v_variant.id, coalesce(v_new_price, new.base_price), now());

            insert into retail_events(event_type, variant_id, previous_price, current_price)
            values ('price_changed', v_variant.id, old.base_price, v_new_price)
            returning id into v_event_id;

            perform process_retail_event(v_event_id);
        end loop;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_product_base_price_event on products;
create trigger trg_product_base_price_event
after update on products
for each row execute function emit_product_base_price_retail_event();


-- v1.10 fix: nothing stopped two concurrent writers (this trigger firing
-- alongside a scheduler tick of activate_due_promotions(), or two scheduler
-- instances) from both passing the "no sale_started event for this
-- promotion yet" check and both inserting one — the check and the insert
-- were separate statements with no uniqueness constraint behind them. Keyed
-- on (promotion_id, variant_id) rather than promotion_id alone, since one
-- promotion legitimately produces one sale_started event PER affected
-- variant in a single pass — a promotion-only key would have made every
-- variant after the first in that same loop silently collide with the
-- first. This makes a second sale_started event for the same
-- promotion+variant impossible at the database level, regardless of how
-- many callers race for it; each insert below now uses `on conflict do
-- nothing` instead of relying solely on the pre-check.
create unique index if not exists uq_retail_events_promotion_variant_sale_started
    on retail_events (event_type, (metadata ->> 'promotion_id'), variant_id)
    where event_type = 'sale_started' and metadata ? 'promotion_id';

-- 38d. Promotions active immediately at creation/update time.
-- Stamps metadata.promotion_id so activate_due_promotions()'s dedup check
-- actually recognizes events this trigger already created.
create or replace function emit_promotion_retail_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_event_id uuid;
    v_variant record;
begin
    if new.is_active and new.starts_at <= now()
       and (new.ends_at is null or new.ends_at > now())
    then
        for v_variant in
            select v.id as variant_id
            from product_variants v
            where v.id = new.variant_id or v.product_id = new.product_id
        loop
            insert into retail_events(event_type, variant_id, current_price, metadata)
            values ('sale_started', v_variant.variant_id, get_effective_variant_price(v_variant.variant_id),
                    jsonb_build_object('promotion_id', new.id))
            on conflict (event_type, (metadata ->> 'promotion_id'), variant_id)
                where event_type = 'sale_started' and metadata ? 'promotion_id'
                do nothing
            returning id into v_event_id;

            if v_event_id is not null then
                perform process_retail_event(v_event_id);
            end if;
        end loop;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_promotion_event on promotions;
create trigger trg_promotion_event
after insert or update on promotions
for each row execute function emit_promotion_retail_event();

-- Call this from a scheduler (pg_cron every minute, or your FastAPI
-- background scheduler) so future-dated promotions still fire sale_started
-- events once their start time actually arrives.
create or replace function activate_due_promotions()
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
    r record;
    v_variant record;
    v_event_id uuid;
    n int := 0;
begin
    -- v1.10 fix: `for update of p skip locked` means two concurrent
    -- scheduler runs no longer both pick up the same promotion and race to
    -- process it — the second run simply skips a promotion the first
    -- already has locked and moves on. This is a performance/contention
    -- improvement; the uq_retail_events_promotion_variant_sale_started
    -- unique index above is what actually guarantees no duplicate event can
    -- ever be persisted even if this lock weren't here.
    for r in
        select p.id, p.variant_id, p.product_id
        from promotions p
        where p.is_active = true
          and p.starts_at <= now()
          and (p.ends_at is null or p.ends_at > now())
          and not exists (
              select 1 from retail_events e
              where e.event_type = 'sale_started'
                and e.metadata ->> 'promotion_id' = p.id::text
          )
        for update of p skip locked
    loop
        for v_variant in
            select v.id as variant_id
            from product_variants v
            where v.id = r.variant_id or v.product_id = r.product_id
        loop
            insert into retail_events(event_type, variant_id, current_price, metadata)
            values ('sale_started', v_variant.variant_id, get_effective_variant_price(v_variant.variant_id),
                    jsonb_build_object('promotion_id', r.id))
            on conflict (event_type, (metadata ->> 'promotion_id'), variant_id)
                where event_type = 'sale_started' and metadata ? 'promotion_id'
                do nothing
            returning id into v_event_id;

            if v_event_id is not null then
                perform process_retail_event(v_event_id);
                n := n + 1;
            end if;
        end loop;
    end loop;

    return n;
end;
$$;


-- ============================================================================
-- 39. AUDIT LOGGING — staff corrections, ticket changes, role changes,
-- promotion admin changes. (Purchase/reservation/inventory auditing lives
-- inline in their respective functions above, sections 31/35/35b/37.)
-- ============================================================================

create or replace function audit_feedback_staff_correction()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.staff_corrected = true
       and (old.staff_corrected is distinct from new.staff_corrected
            or old.staff_category is distinct from new.staff_category
            or old.staff_sentiment is distinct from new.staff_sentiment)
    then
        insert into audit_logs(actor_user_id, actor_type, action, entity_type, entity_id, before_data, after_data)
        values (
            current_actor_id(), 'staff', 'feedback_ai_tag_corrected', 'feedback', new.id,
            jsonb_build_object('ai_category', old.ai_category, 'ai_sentiment', old.ai_sentiment,
                                'staff_category', old.staff_category, 'staff_sentiment', old.staff_sentiment),
            jsonb_build_object('staff_category', new.staff_category, 'staff_sentiment', new.staff_sentiment)
        );
    end if;
    return new;
end;
$$;

drop trigger if exists trg_feedback_audit on feedback;
create trigger trg_feedback_audit
after update on feedback
for each row execute function audit_feedback_staff_correction();


create or replace function audit_support_status_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if old.status is distinct from new.status
       or old.assigned_staff_id is distinct from new.assigned_staff_id
       or old.priority is distinct from new.priority
       or old.sentiment is distinct from new.sentiment
    then
        insert into audit_logs(actor_user_id, actor_type, action, entity_type, entity_id, before_data, after_data)
        values (
            current_actor_id(), 'staff', 'support_ticket_updated', 'support_escalations', new.id,
            jsonb_build_object(
                'status', old.status, 'priority', old.priority,
                'sentiment', old.sentiment, 'assigned_staff_id', old.assigned_staff_id
            ),
            jsonb_build_object(
                'status', new.status, 'priority', new.priority,
                'sentiment', new.sentiment, 'assigned_staff_id', new.assigned_staff_id
            )
        );
    end if;
    return new;
end;
$$;

drop trigger if exists trg_support_audit on support_escalations;
create trigger trg_support_audit
after update on support_escalations
for each row execute function audit_support_status_change();


-- audit role grants/revokes/changes
create or replace function audit_role_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into audit_logs(actor_user_id, actor_type, action, entity_type, entity_id, before_data, after_data)
    values (
        current_actor_id(), 'staff',
        case when TG_OP = 'INSERT' then 'role_granted'
             when TG_OP = 'DELETE' then 'role_revoked'
             else 'role_updated' end,
        'user_roles',
        coalesce(new.id, old.id),
        case when TG_OP in ('UPDATE','DELETE') then jsonb_build_object('user_id', old.user_id, 'role', old.role) else null end,
        case when TG_OP in ('UPDATE','INSERT') then jsonb_build_object('user_id', new.user_id, 'role', new.role) else null end
    );
    return coalesce(new, old);
end;
$$;

drop trigger if exists trg_role_audit on user_roles;
create trigger trg_role_audit
after insert or update or delete on user_roles
for each row execute function audit_role_change();


-- audit promotion (price/sale admin) create/update
create or replace function audit_promotion_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into audit_logs(actor_user_id, actor_type, action, entity_type, entity_id, before_data, after_data)
    values (
        current_actor_id(), 'staff',
        case when TG_OP = 'INSERT' then 'promotion_created' else 'promotion_updated' end,
        'promotions', new.id,
        case when TG_OP = 'UPDATE' then
            jsonb_build_object('discount_value', old.discount_value, 'is_active', old.is_active,
                                'starts_at', old.starts_at, 'ends_at', old.ends_at)
        else null end,
        jsonb_build_object('discount_type', new.discount_type, 'discount_value', new.discount_value,
                            'is_active', new.is_active, 'starts_at', new.starts_at, 'ends_at', new.ends_at)
    );
    return new;
end;
$$;

drop trigger if exists trg_promotion_audit on promotions;
create trigger trg_promotion_audit
after insert or update on promotions
for each row execute function audit_promotion_change();


-- ============================================================================
-- 40. GUARD: customers cannot fake their own Smart Cart trigger/completion
-- ============================================================================

create or replace function guard_smart_cart_customer_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if not is_staff() and not (current_setting('role', true) = 'service_role') then
        -- v1.10 fix: the v1.x version of this guard only blocked customer
        -- transitions INTO 'triggered'/'completed'. It never blocked moving
        -- OUT of them (triggered -> active/paused/cancelled, completed ->
        -- active), so a customer could reset a rule the orchestrator had
        -- already triggered/completed back to 'active' and let it fire
        -- again on the next qualifying retail event. Both directions are
        -- system-owned now: only staff/service_role may change the status
        -- of a rule that is currently (or would become) triggered/completed.
        if new.status is distinct from old.status then
            if old.status in ('triggered','completed') then
                raise exception 'Customers cannot change the status of a % Smart Cart rule', old.status;
            end if;
            if new.status in ('triggered','completed') then
                raise exception 'Customers cannot set Smart Cart status to %', new.status;
            end if;
        end if;

        if new.customer_id is distinct from old.customer_id
           or new.variant_id is distinct from old.variant_id then
            raise exception 'Cannot change ownership/variant of an existing Smart Cart rule';
        end if;

        -- v1.10 fix: triggered_at/last_evaluated_at are written only by
        -- evaluate_smart_cart_rule()/process_retail_event(); previously a
        -- customer UPDATE could set or clear them directly, which combined
        -- with the reset above could forge a rule's evaluation history.
        if new.triggered_at is distinct from old.triggered_at
           or new.last_evaluated_at is distinct from old.last_evaluated_at then
            raise exception 'Cannot modify system-managed Smart Cart timestamps';
        end if;

        -- v1.11 fix: the v1.10 guard only froze status/timestamps/ownership
        -- once a rule triggered — it said nothing about branch_id, quantity,
        -- target_price, min_discount_percentage, or authorization_mode. A
        -- customer could still edit those after the orchestrator marked the
        -- rule 'triggered' (e.g. bump quantity from 1 to 10, or repoint
        -- branch_id) before the Purchase Agent actually acts on it, so the
        -- auto-buy could end up executing against conditions the trigger
        -- event never actually validated. execute_mock_purchase() re-checks
        -- these values against the rule at purchase time, so this was never
        -- an authorization bypass — but it did let a triggered rule's
        -- defining parameters drift away from whatever caused it to fire in
        -- the first place. The invariant now is: an evaluated Smart Cart
        -- rule is immutable from the moment it triggers. Editing any
        -- rule-defining field is customer-controlled only while the rule is
        -- still 'active' (or 'paused'); once it is 'triggered' or
        -- 'completed', none of these may change.
        if old.status in ('triggered','completed') then
            if new.branch_id is distinct from old.branch_id
               or new.quantity is distinct from old.quantity
               or new.target_price is distinct from old.target_price
               or new.min_discount_percentage is distinct from old.min_discount_percentage
               or new.authorization_mode is distinct from old.authorization_mode
            then
                raise exception 'Cannot modify the parameters of a % Smart Cart rule', old.status;
            end if;
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_smart_cart_guard on smart_cart_rules;
create trigger trg_smart_cart_guard
before update on smart_cart_rules
for each row execute function guard_smart_cart_customer_update();


-- ============================================================================
-- 40b. GUARD: customers cannot deactivate/reactivate their own account
-- ============================================================================
-- v1.8 fix: profiles.is_active sat alongside customer-editable fields
-- (full_name, phone, preferred_language) with only `id = auth.uid()` as the
-- update_own_profile check, so a customer could set their own is_active,
-- including reactivating an account staff deactivated. Only staff/the
-- trusted backend may change it now; everything else customers already own
-- (full_name, phone, preferred_language) is untouched.
create or replace function guard_profile_customer_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if not is_staff() and not (current_setting('role', true) = 'service_role') then
        if new.is_active is distinct from old.is_active then
            raise exception 'Customers cannot change their own account active status';
        end if;
        -- v1.9: created_at is a system-owned audit field; id is already
        -- implicitly protected since update_own_profile's WITH CHECK
        -- requires new.id = auth.uid().
        if new.created_at is distinct from old.created_at then
            raise exception 'Customers cannot change their own account creation timestamp';
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_profile_guard on profiles;
create trigger trg_profile_guard
before update on profiles
for each row execute function guard_profile_customer_update();


-- ============================================================================
-- 40c. GUARD: customers cannot mark their own cart 'converted'  [NEW v1.10]
-- ============================================================================
-- v1.10 fix: manage_own_cart (`for all`) let a customer freely set
-- carts.status, including 'converted' — a status meant to represent a real
-- completed checkout for conversion analytics/reporting. A customer could
-- set (or clear) it themselves with no purchase behind it. 'active' and
-- 'abandoned' remain fully customer-controlled; only staff/service_role may
-- move a cart into or out of 'converted'.
create or replace function guard_cart_customer_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if not is_staff() and not (current_setting('role', true) = 'service_role') then
        if new.customer_id is distinct from old.customer_id then
            raise exception 'Cannot change ownership of an existing cart';
        end if;

        if new.status is distinct from old.status
           and (old.status = 'converted' or new.status = 'converted') then
            raise exception 'Cart conversion status is system-managed';
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_cart_guard on carts;
create trigger trg_cart_guard
before update on carts
for each row execute function guard_cart_customer_update();


-- ============================================================================
-- 40d. GUARD: alert trigger history is system-managed
-- ============================================================================
create or replace function guard_alert_customer_update()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if not is_staff() and not (current_setting('role', true) = 'service_role') then
        if new.customer_id is distinct from old.customer_id then
            raise exception 'Cannot change ownership of an alert';
        end if;

        if new.triggered_at is distinct from old.triggered_at then
            raise exception 'Alert trigger timestamp is system-managed';
        end if;

        if old.triggered_at is not null then
            raise exception 'A triggered alert is immutable; create a new alert instead';
        end if;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_alert_guard on alerts;
create trigger trg_alert_guard
before update on alerts
for each row execute function guard_alert_customer_update();


-- ============================================================================
-- 40e. DURABLE CUSTOMER MEMORY RPCs
-- ============================================================================
-- Writes are service_role-only. Customers can view/delete their own rows via
-- RLS, while the Memory & Context Agent uses these RPCs through FastAPI.

create or replace function upsert_customer_memory(
    p_customer_id uuid,
    p_memory_type customer_memory_type,
    p_memory_key text,
    p_memory_value jsonb,
    p_confidence numeric default 1.0,
    p_source_conversation_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_id uuid;
begin
    if p_memory_key is null or btrim(p_memory_key) = '' then
        raise exception 'memory_key is required';
    end if;

    if p_confidence is null or p_confidence < 0 or p_confidence > 1 then
        raise exception 'confidence must be between 0 and 1';
    end if;

    if not exists (
        select 1 from profiles
        where id = p_customer_id and is_active = true
    ) then
        raise exception 'Customer account is not active';
    end if;

    if p_source_conversation_id is not null
       and not exists (
           select 1 from conversations
           where id = p_source_conversation_id
             and customer_id = p_customer_id
       ) then
        raise exception 'Source conversation does not belong to customer';
    end if;

    insert into customer_memory(
        customer_id, memory_type, memory_key, memory_value, confidence,
        source_conversation_id, is_active, last_confirmed_at
    )
    values(
        p_customer_id, p_memory_type, btrim(p_memory_key), p_memory_value,
        p_confidence, p_source_conversation_id, true, now()
    )
    on conflict(customer_id, memory_key) do update
    set memory_type = excluded.memory_type,
        memory_value = excluded.memory_value,
        confidence = excluded.confidence,
        source_conversation_id = excluded.source_conversation_id,
        is_active = true,
        last_confirmed_at = now(),
        updated_at = now()
    returning id into v_id;

    return v_id;
end;
$$;


create or replace function get_customer_context_snapshot(p_customer_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_snapshot jsonb;
begin
    if not exists (select 1 from profiles where id = p_customer_id) then
        return null;
    end if;

    select jsonb_build_object(
        'preferences',
            coalesce(
                (select to_jsonb(cp) - 'customer_id'
                 from customer_preferences cp
                 where cp.customer_id = p_customer_id),
                '{}'::jsonb
            ),
        'recent_orders',
            coalesce(
                (select jsonb_agg(to_jsonb(o) order by o.created_at desc)
                 from (
                     select id, branch_id, status, subtotal, discount, total,
                            currency, source, created_at
                     from orders
                     where customer_id = p_customer_id
                     order by created_at desc
                     limit 5
                 ) o),
                '[]'::jsonb
            ),
        'open_support_tickets',
            coalesce(
                (select jsonb_agg(
                     jsonb_build_object(
                         'id', s.id, 'subject', s.subject, 'status', s.status,
                         'priority', s.priority, 'sentiment', s.sentiment,
                         'assigned_staff_id', s.assigned_staff_id,
                         'created_at', s.created_at, 'updated_at', s.updated_at
                     )
                     order by s.updated_at desc
                 )
                 from support_escalations s
                 where s.customer_id = p_customer_id
                   and s.status not in ('resolved','closed')),
                '[]'::jsonb
            ),
        'active_smart_cart_rules',
            coalesce(
                (select jsonb_agg(to_jsonb(sc) order by sc.created_at desc)
                 from smart_cart_rules sc
                 where sc.customer_id = p_customer_id
                   and sc.status in ('active','triggered')),
                '[]'::jsonb
            ),
        'active_alerts',
            coalesce(
                (select jsonb_agg(to_jsonb(a) order by a.created_at desc)
                 from alerts a
                 where a.customer_id = p_customer_id
                   and a.is_active = true),
                '[]'::jsonb
            ),
        'remembered_facts',
            coalesce(
                (select jsonb_agg(
                     jsonb_build_object(
                         'id', m.id,
                         'memory_type', m.memory_type,
                         'memory_key', m.memory_key,
                         'memory_value', m.memory_value,
                         'confidence', m.confidence,
                         'effective_confidence',
                             case
                                 when m.last_confirmed_at < now() - interval '90 days'
                                     then greatest(0, m.confidence * 0.5)
                                 else m.confidence
                             end,
                         'is_stale', (m.last_confirmed_at < now() - interval '90 days'),
                         'source_conversation_id', m.source_conversation_id,
                         'last_confirmed_at', m.last_confirmed_at,
                         'created_at', m.created_at,
                         'updated_at', m.updated_at
                     )
                     order by
                         case
                             when m.last_confirmed_at < now() - interval '90 days'
                                 then m.confidence * 0.5
                             else m.confidence
                         end desc,
                         m.last_confirmed_at desc
                 )
                 from (
                     select *
                     from customer_memory
                     where customer_id = p_customer_id
                       and is_active = true
                     order by confidence desc, last_confirmed_at desc
                     limit 20
                 ) m),
                '[]'::jsonb
            )
    )
    into v_snapshot;

    return v_snapshot;
end;
$$;


-- ============================================================================
-- 41. ANALYTICS VIEWS
--
-- security_invoker = true. Without it, a view runs with the view OWNER's
-- privileges against its underlying tables (Postgres default), which for a
-- view created by the project's own role can silently bypass RLS on
-- demand_signals/branch_inventory etc. Forcing invoker security means RLS is
-- evaluated as the querying role — so a plain `authenticated` client
-- genuinely cannot read these (matches "Analytics Agent should go through a
-- backend service, not direct client access").
-- ============================================================================

create or replace view v_high_interest_low_availability
with (security_invoker = true) as
select product_id, variant_id, branch_id,
       count(*) as demand_signal_count,
       count(*) filter (where fulfilled = false) as unfulfilled_signal_count,
       max(created_at) as latest_signal_at
from demand_signals
where fulfilled = false
group by product_id, variant_id, branch_id;

create or replace view v_unavailable_searches
with (security_invoker = true) as
select signal_type, requested_size, requested_color,
       count(*) as signal_count,
       max(created_at) as latest_signal_at
from demand_signals
where fulfilled = false
group by signal_type, requested_size, requested_color;

create or replace view v_branch_inventory_summary
with (security_invoker = true) as
select branch_id,
       count(*) as total_variants,
       count(*) filter (where available_quantity > 2) as available_variants,
       count(*) filter (where available_quantity between 1 and 2) as low_stock_variants,
       count(*) filter (where available_quantity <= 0) as out_of_stock_variants
from branch_inventory
group by branch_id;

create or replace view v_product_demand_availability
with (security_invoker = true) as
select ds.product_id, ds.variant_id,
       count(*) as demand_signal_count,
       count(*) filter (where ds.fulfilled = false) as unfulfilled_signal_count,
       count(distinct ds.branch_id) as affected_branches,
       max(ds.created_at) as latest_signal_at
from demand_signals ds
group by ds.product_id, ds.variant_id;


-- ============================================================================
-- 42. INDEXES
-- ============================================================================

create index if not exists idx_categories_parent on categories(parent_id);
create index if not exists idx_products_category on products(category_id);
create index if not exists idx_products_active on products(is_active);
create index if not exists idx_products_attributes on products using gin(attributes);
create index if not exists idx_product_variants_product on product_variants(product_id);
create index if not exists idx_product_variants_color on product_variants(color_id);
create index if not exists idx_product_variants_size on product_variants(size_id);
create index if not exists idx_product_variants_attributes on product_variants using gin(attributes);
create index if not exists idx_product_images_product on product_images(product_id);
create index if not exists idx_product_images_variant on product_images(variant_id);
create index if not exists idx_inventory_branch_available on branch_inventory(branch_id, available_quantity);
create index if not exists idx_inventory_variant on branch_inventory(variant_id);
create index if not exists idx_inventory_movements on inventory_movements(inventory_id, created_at desc);
create index if not exists idx_price_history_variant on price_history(variant_id, valid_from desc);
create index if not exists idx_promotions_active on promotions(starts_at, ends_at, is_active);
create index if not exists idx_messages_conversation on messages(conversation_id, created_at);
create index if not exists idx_agent_runs_conversation on agent_runs(conversation_id, created_at desc);
create index if not exists idx_agent_tasks_run on agent_tasks(agent_run_id, created_at);
create index if not exists idx_agent_tool_calls_run on agent_tool_calls(agent_run_id, created_at);
create index if not exists idx_smart_cart_active on smart_cart_rules(variant_id, status);
create index if not exists idx_smart_cart_events_rule on smart_cart_events(smart_cart_rule_id, created_at desc);
create index if not exists idx_retail_events_unprocessed on retail_events(created_at) where processed_at is null;
create index if not exists idx_retail_events_variant on retail_events(variant_id, created_at desc);
create index if not exists idx_notifications_customer on notifications(customer_id, created_at desc);
create index if not exists idx_notification_deliveries_pending on notification_deliveries(status, created_at) where status = 'pending';
create index if not exists idx_orders_customer on orders(customer_id, created_at desc);
create index if not exists idx_orders_branch on orders(branch_id, created_at desc) where branch_id is not null;
create index if not exists idx_purchase_attempts_rule on purchase_attempts(smart_cart_rule_id, created_at desc);
create index if not exists idx_purchase_attempts_reservation on purchase_attempts(reservation_id, created_at desc);
create index if not exists idx_support_status on support_escalations(status);
create index if not exists idx_support_sentiment on support_escalations(sentiment) where sentiment is not null;
create index if not exists idx_customer_memory_active
    on customer_memory(customer_id, is_active, last_confirmed_at desc);
create index if not exists idx_customer_memory_source
    on customer_memory(source_conversation_id) where source_conversation_id is not null;
create index if not exists idx_support_messages_ticket on support_ticket_messages(ticket_id, created_at);
create index if not exists idx_feedback_customer on feedback(customer_id, created_at desc);
create index if not exists idx_demand_variant on demand_signals(variant_id);
create index if not exists idx_demand_created on demand_signals(created_at desc);
create index if not exists idx_reservations_active on reservations(variant_id, branch_id, status);
create index if not exists idx_reservations_expiry on reservations(expires_at) where status = 'active';
create index if not exists idx_audit_logs_entity on audit_logs(entity_type, entity_id, created_at desc);

create unique index if not exists uq_smart_cart_event_rule
on smart_cart_events(smart_cart_rule_id, retail_event_id, event_type)
where retail_event_id is not null;

create unique index if not exists uq_notification_delivery_channel
on notification_deliveries(notification_id, channel);


-- ============================================================================
-- 43. ROW LEVEL SECURITY
--
-- RLS is enabled on every table that holds business/customer data.
-- ============================================================================

alter table profiles enable row level security;
alter table user_roles enable row level security;
alter table branches enable row level security;
alter table customer_preferences enable row level security;
alter table categories enable row level security;
alter table colors enable row level security;
alter table sizes enable row level security;
alter table products enable row level security;
alter table product_variants enable row level security;
alter table product_images enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;
alter table conversation_state enable row level security;
alter table customer_memory enable row level security;
alter table carts enable row level security;
alter table cart_items enable row level security;
alter table wishlists enable row level security;
alter table alerts enable row level security;
alter table smart_cart_rules enable row level security;
alter table smart_cart_events enable row level security;
alter table notifications enable row level security;
alter table orders enable row level security;
alter table order_items enable row level security;
alter table payments enable row level security;
alter table reservations enable row level security;
alter table feedback enable row level security;
alter table support_escalations enable row level security;
alter table support_ticket_messages enable row level security;
alter table agent_runs enable row level security;
alter table agent_tasks enable row level security;
alter table agent_tool_calls enable row level security;
alter table branch_inventory enable row level security;
alter table inventory_movements enable row level security;
alter table price_history enable row level security;
alter table promotions enable row level security;
alter table retail_events enable row level security;
alter table purchase_attempts enable row level security;
alter table notification_deliveries enable row level security;
alter table demand_signals enable row level security;
alter table agent_registry enable row level security;
alter table audit_logs enable row level security;


-- ============================================================================
-- 44. DROP EXISTING POLICIES (Retailigent tables only)
--
-- Scoped to an explicit list of this project's own tables, so re-running
-- this never wipes another project's policies sharing the same instance.
-- ============================================================================

do $$
declare
    r record;
    retailigent_tables text[] := array[
        'profiles','user_roles','branches','customer_preferences','categories',
        'colors','sizes','products','product_variants','product_images',
        'conversations','messages','conversation_state','customer_memory','carts','cart_items',
        'wishlists','alerts','smart_cart_rules','smart_cart_events','notifications',
        'orders','order_items','payments','reservations','feedback',
        'support_escalations','support_ticket_messages','agent_runs','agent_tasks',
        'agent_tool_calls','branch_inventory','inventory_movements','price_history',
        'promotions','retail_events','purchase_attempts','notification_deliveries',
        'demand_signals','agent_registry','audit_logs'
    ];
begin
    for r in
        select schemaname, tablename, policyname
        from pg_policies
        where schemaname = 'public'
          and tablename = any(retailigent_tables)
    loop
        execute format('drop policy if exists %I on public.%I', r.policyname, r.tablename);
    end loop;
end $$;


-- ============================================================================
-- 45. PUBLIC CATALOG READ POLICIES
-- ============================================================================

create policy public_branches on branches for select using(is_active = true);
create policy public_categories on categories for select using(is_active = true);
create policy public_colors on colors for select using(is_active = true);
create policy public_sizes on sizes for select using(is_active = true);
create policy public_products on products for select using(is_active = true);
-- v1.8 fix: previously only checked the variant's own is_active, so a
-- variant left active on a product that was deactivated was still publicly
-- visible. Now requires the parent product to be active too.
create policy public_variants on product_variants for select using(
    is_active = true
    and exists (select 1 from products p where p.id = product_variants.product_id and p.is_active = true)
);

-- v1.1 FIX: previously `using(true)`, which exposed images for inactive
-- products/variants. Now mirrors the same is_active checks as
-- public_products/public_variants — an image is only publicly visible if
-- the product (and, when set, the specific variant) it belongs to is active.
create policy public_images on product_images for select using (
    exists (
        select 1
        from product_variants v
        join products p on p.id = v.product_id
        where v.id = product_images.variant_id
          and v.is_active = true
          and p.is_active = true
    )
    or (
        product_images.variant_id is null
        and exists (
            select 1
            from products p
            where p.id = product_images.product_id
              and p.is_active = true
        )
    )
);


-- ============================================================================
-- 46. CUSTOMER READ POLICIES (own data or staff)
-- ============================================================================

create policy own_profile on profiles for select to authenticated using(id = auth.uid() or is_staff());
create policy own_user_roles on user_roles for select to authenticated using(user_id = auth.uid() or is_staff());
create policy own_preferences on customer_preferences for select to authenticated using(customer_id = auth.uid() or is_staff());

create policy own_conversations on conversations for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_messages on messages for select to authenticated using(
    exists(select 1 from conversations c where c.id = messages.conversation_id and (c.customer_id = auth.uid() or is_staff()))
);
create policy own_conversation_state on conversation_state for select to authenticated using(
    exists(select 1 from conversations c where c.id = conversation_state.conversation_id and (c.customer_id = auth.uid() or is_staff()))
);

-- Memory is private customer context. Trusted backend reads it through the
-- service-role snapshot RPC; an authenticated customer can read only their own.
create policy own_customer_memory on customer_memory for select to authenticated
using(customer_id = auth.uid());


create policy own_cart on carts for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_cart_items on cart_items for select to authenticated using(
    exists(select 1 from carts c where c.id = cart_items.cart_id and (c.customer_id = auth.uid() or is_staff()))
);

create policy own_wishlist on wishlists for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_alerts on alerts for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_smart_cart on smart_cart_rules for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_smart_cart_events on smart_cart_events for select to authenticated using(
    exists(select 1 from smart_cart_rules r where r.id = smart_cart_events.smart_cart_rule_id and (r.customer_id = auth.uid() or is_staff()))
);

create policy own_notifications on notifications for select to authenticated using(customer_id = auth.uid() or is_staff());

create policy own_orders on orders for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_order_items on order_items for select to authenticated using(
    exists(select 1 from orders o where o.id = order_items.order_id and (o.customer_id = auth.uid() or is_staff()))
);
create policy own_payments on payments for select to authenticated using(customer_id = auth.uid() or is_staff());

create policy own_reservations on reservations for select to authenticated using(customer_id = auth.uid() or is_staff());

create policy own_feedback on feedback for select to authenticated using(customer_id = auth.uid() or is_staff());

create policy own_support on support_escalations for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_support_messages on support_ticket_messages for select to authenticated using(
    exists(select 1 from support_escalations s where s.id = support_ticket_messages.ticket_id and (s.customer_id = auth.uid() or is_staff()))
);

create policy own_agent_runs on agent_runs for select to authenticated using(customer_id = auth.uid() or is_staff());
create policy own_agent_tasks on agent_tasks for select to authenticated using(
    exists(select 1 from agent_runs r where r.id = agent_tasks.agent_run_id and (r.customer_id = auth.uid() or is_staff()))
);
create policy own_agent_tool_calls on agent_tool_calls for select to authenticated using(
    exists(select 1 from agent_runs r where r.id = agent_tool_calls.agent_run_id and (r.customer_id = auth.uid() or is_staff()))
);


-- ============================================================================
-- 47. STAFF READ POLICIES for the newly-protected tables
--
-- These tables still have NO client write policies at all (writes stay
-- exclusively through the SECURITY DEFINER functions / trusted backend).
-- Staff get read access for dashboard/admin convenience; ordinary customers
-- get none — branch_inventory/promotions/etc. are never exposed raw to a
-- plain `authenticated` client, only via computed fields like stock_status
-- and effective price that the backend/agents return.
-- ============================================================================

create policy staff_read_branch_inventory on branch_inventory for select to authenticated using(is_staff());
create policy staff_read_inventory_movements on inventory_movements for select to authenticated using(is_staff());
create policy staff_read_price_history on price_history for select to authenticated using(is_staff());
create policy staff_read_promotions on promotions for select to authenticated using(is_staff());
create policy staff_read_retail_events on retail_events for select to authenticated using(is_staff());
create policy staff_read_purchase_attempts on purchase_attempts for select to authenticated using(is_staff());
create policy staff_read_notification_deliveries on notification_deliveries for select to authenticated using(is_staff());
create policy staff_read_demand_signals on demand_signals for select to authenticated using(is_staff());
create policy staff_read_agent_registry on agent_registry for select to authenticated using(is_staff());
create policy staff_read_audit_logs on audit_logs for select to authenticated using(is_staff());


-- ============================================================================
-- 48. CUSTOMER WRITE POLICIES (ordinary self-service actions only —
-- everything inventory/price/purchase-adjacent stays RPC-only, called
-- via the SECURITY DEFINER functions above)
-- ============================================================================

create policy update_own_profile on profiles for update to authenticated
using (id = auth.uid()) with check (id = auth.uid());

create policy upsert_own_preferences on customer_preferences for insert to authenticated
with check (customer_id = auth.uid());
create policy update_own_preferences on customer_preferences for update to authenticated
using (customer_id = auth.uid()) with check (customer_id = auth.uid());

-- Customers may permanently delete remembered facts. Creation/update is
-- service_role-only through upsert_customer_memory().
create policy delete_own_customer_memory on customer_memory for delete to authenticated
using(customer_id = auth.uid());


-- v1.12: split cart writes by operation. A customer-created cart must start
-- active; converted carts are historical purchase artifacts and cannot be
-- deleted. Cart items are mutable only while the parent cart is active.
create policy insert_own_cart on carts for insert to authenticated
with check (customer_id = auth.uid() and status = 'active');

create policy update_own_cart on carts for update to authenticated
using (customer_id = auth.uid())
with check (customer_id = auth.uid());

create policy delete_own_cart on carts for delete to authenticated
using (customer_id = auth.uid() and status <> 'converted');

create policy insert_own_cart_items on cart_items for insert to authenticated
with check (
    exists (
        select 1 from carts c
        where c.id = cart_items.cart_id
          and c.customer_id = auth.uid()
          and c.status = 'active'
    )
);

create policy update_own_cart_items on cart_items for update to authenticated
using (
    exists (
        select 1 from carts c
        where c.id = cart_items.cart_id
          and c.customer_id = auth.uid()
          and c.status = 'active'
    )
)
with check (
    exists (
        select 1 from carts c
        where c.id = cart_items.cart_id
          and c.customer_id = auth.uid()
          and c.status = 'active'
    )
);

create policy delete_own_cart_items on cart_items for delete to authenticated
using (
    exists (
        select 1 from carts c
        where c.id = cart_items.cart_id
          and c.customer_id = auth.uid()
          and c.status = 'active'
    )
);

-- Wishlists are append/remove records; no customer UPDATE is needed.
create policy insert_own_wishlist on wishlists for insert to authenticated
with check (customer_id = auth.uid());
create policy delete_own_wishlist on wishlists for delete to authenticated
using (customer_id = auth.uid());

-- Alert trigger metadata is system-owned. Customers may create, edit, disable,
-- or delete an untriggered alert, but cannot forge/clear triggered_at.
create policy insert_own_alerts on alerts for insert to authenticated
with check (customer_id = auth.uid() and triggered_at is null);
create policy update_own_alerts on alerts for update to authenticated
using (customer_id = auth.uid())
with check (customer_id = auth.uid());
create policy delete_own_alerts on alerts for delete to authenticated
using (customer_id = auth.uid());

-- v1.4: split the old single "for all" policy on smart_cart_rules into
-- insert/update/delete, because the old policy's WITH CHECK only verified
-- ownership — a customer could INSERT a rule already status='triggered'/
-- 'completed', or with triggered_at/last_evaluated_at pre-set, bypassing
-- the fact that those are system-owned fields the orchestrator sets. The
-- existing trg_smart_cart_guard trigger already protects UPDATE
-- transitions, so the update policy here only needs to check ownership.
create policy insert_own_smart_cart on smart_cart_rules for insert to authenticated
with check (
    customer_id = auth.uid()
    and status = 'active'
    and triggered_at is null
    and last_evaluated_at is null
);
create policy update_own_smart_cart on smart_cart_rules for update to authenticated
using (customer_id = auth.uid()) with check (customer_id = auth.uid());
create policy delete_own_smart_cart on smart_cart_rules for delete to authenticated
using (
    customer_id = auth.uid()
    and status not in ('triggered','completed')
);

create policy manage_own_conversations on conversations for all to authenticated
using (customer_id = auth.uid()) with check (customer_id = auth.uid());
create policy insert_own_messages on messages for insert to authenticated
with check (
    exists (select 1 from conversations c where c.id = messages.conversation_id and c.customer_id = auth.uid())
    -- v1.4: an authenticated customer could previously insert a message
    -- with role='assistant'/'system'/'tool' into their own conversation,
    -- corrupting the agent audit trail (though not exposing anyone else's
    -- data, since the conversation ownership check still applied).
    -- Customer-authored inserts must now be plain user turns; the backend
    -- (service_role, which bypasses RLS) writes assistant/agent/tool/system
    -- messages.
    and role = 'user'
    and agent_key is null
    and tool_name is null
);

-- v1.8 fix: previously only checked ownership, so a customer INSERT could
-- also set ai_category/ai_sentiment/staff_category/staff_sentiment/
-- staff_corrected — all system-owned fields the AI classifier and staff are
-- meant to populate, not the customer submitting the feedback. Also now
-- verifies a supplied conversation_id actually belongs to this customer,
-- rather than letting them attach feedback to someone else's conversation.
create policy insert_own_feedback on feedback for insert to authenticated
with check (
    customer_id = auth.uid()
    and ai_category is null
    and ai_sentiment is null
    and staff_category is null
    and staff_sentiment is null
    and staff_corrected = false
    and (
        conversation_id is null
        or exists (select 1 from conversations c where c.id = feedback.conversation_id and c.customer_id = auth.uid())
    )
);

-- v1.8 fix: previously only checked ownership, so a customer INSERT could
-- also set status/priority/assigned_staff_id/handoff_summary/agent_context
-- — all system-owned fields the support workflow and staff are meant to
-- populate, not the customer opening the ticket. Also now verifies a
-- supplied conversation_id actually belongs to this customer.
create policy insert_own_support_ticket on support_escalations for insert to authenticated
with check (
    customer_id = auth.uid()
    and status = 'open'
    and priority = 'normal'
    and sentiment is null
    and assigned_staff_id is null
    and handoff_summary is null
    and agent_context = '{}'::jsonb
    and (
        conversation_id is null
        or exists (select 1 from conversations c where c.id = support_escalations.conversation_id and c.customer_id = auth.uid())
    )
);
create policy insert_own_support_message on support_ticket_messages for insert to authenticated
with check (
    -- v1.4: previously `... or sender_type = 'staff'` let ANY authenticated
    -- customer insert a message marked 'staff' on ANY ticket they could
    -- reference by id. Now customer-authored messages must actually be the
    -- caller, on the caller's own ticket; staff-authored messages must
    -- actually be the caller AND the caller must be staff. Agent-authored
    -- messages ('agent') are written only by the trusted backend
    -- (service_role bypasses RLS), never by an authenticated client.
    (
        sender_type = 'customer'
        and sender_id = auth.uid()
        and exists (
            select 1 from support_escalations s
            where s.id = support_ticket_messages.ticket_id
              and s.customer_id = auth.uid()
        )
    )
    or
    (
        sender_type = 'staff'
        and sender_id = auth.uid()
        and is_staff()
    )
);

-- No client write policies at all on: exact inventory, inventory movements,
-- price history, retail events, demand signals, orders/order_items/payments,
-- purchase_attempts, reservations, notification deliveries, agent registry/
-- tool registry, audit_logs, user_roles, promotions. These are written
-- exclusively by the trusted backend (service_role) and the SECURITY
-- DEFINER functions above.


-- ============================================================================
-- 49. SEED PRODUCT CATEGORIES
-- ============================================================================

insert into categories(name, slug, parent_id) values
('Women', 'women', null),
('Men', 'men', null),
('Kids', 'kids', null),
('Footwear', 'footwear', null),
('Jewellery', 'jewellery', null),
('Accessories', 'accessories', null),
('Fragrances', 'fragrances', null),
('Home', 'home', null),
('Gifting', 'gifting', null)
on conflict(slug) do nothing;

-- NOTE (data-quality, not a structural bug): Women/Men each also seed their
-- own "Accessories" sub-category below, alongside the top-level Accessories
-- tree (Bags/Scarves/Hair Accessories/Wallets). That's an intentional
-- demographic-specific vs. general split, but keep it consistent when you
-- add real seed products — decide per-product which one it belongs under.

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Ready to Wear','women-ready-to-wear'),
    ('Fabrics','women-fabrics'),
    ('Khaas','women-khaas'),
    ('Accessories','women-accessories')
) x(name,slug) join categories c on c.slug = 'women'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Ready to Wear','men-ready-to-wear'),
    ('Fabrics','men-fabrics'),
    ('Accessories','men-accessories')
) x(name,slug) join categories c on c.slug = 'men'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Girls','kids-girls'),
    ('Boys','kids-boys')
) x(name,slug) join categories c on c.slug = 'kids'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Women','footwear-women'),
    ('Men','footwear-men'),
    ('Kids','footwear-kids')
) x(name,slug) join categories c on c.slug = 'footwear'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Earrings','jewellery-earrings'),
    ('Necklaces','jewellery-necklaces'),
    ('Bracelets','jewellery-bracelets'),
    ('Rings','jewellery-rings'),
    ('Sets','jewellery-sets')
) x(name,slug) join categories c on c.slug = 'jewellery'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Bags','accessories-bags'),
    ('Hair Accessories','accessories-hair'),
    ('Scarves','accessories-scarves'),
    ('Wallets','accessories-wallets'),
    ('Other Accessories','accessories-other')
) x(name,slug) join categories c on c.slug = 'accessories'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Perfumes','fragrances-perfumes'),
    ('Body Mists','fragrances-body-mists'),
    ('Gift Sets','fragrances-gift-sets')
) x(name,slug) join categories c on c.slug = 'fragrances'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Bedroom','home-bedroom'),
    ('Dining Room','home-dining'),
    ('Living Room','home-living'),
    ('Décor','home-decor'),
    ('Home Café','home-cafe')
) x(name,slug) join categories c on c.slug = 'home'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Bedsheets','home-bedroom-bedsheets'),
    ('Duvet Covers','home-bedroom-duvet-covers'),
    ('Throws','home-bedroom-throws'),
    ('Cushions','home-bedroom-cushions'),
    ('Towels','home-bedroom-towels')
) x(name,slug) join categories c on c.slug = 'home-bedroom'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Dinner Sets','home-dining-dinner-sets'),
    ('Plates','home-dining-plates'),
    ('Bowls','home-dining-bowls'),
    ('Mugs','home-dining-mugs'),
    ('Glasses','home-dining-glasses'),
    ('Table Linen','home-dining-table-linen')
) x(name,slug) join categories c on c.slug = 'home-dining'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Cushions','home-living-cushions'),
    ('Ottomans','home-living-ottomans'),
    ('Stools','home-living-stools')
) x(name,slug) join categories c on c.slug = 'home-living'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Floor Mats','home-decor-floor-mats'),
    ('Runners','home-decor-runners'),
    ('Decorative Items','home-decor-items')
) x(name,slug) join categories c on c.slug = 'home-decor'
on conflict(slug) do nothing;

insert into categories(name, slug, parent_id)
select x.name, x.slug, c.id from (values
    ('Candles','gifting-candles'),
    ('Greeting Cards','gifting-cards'),
    ('Envelopes','gifting-envelopes'),
    ('Gift Bags','gifting-bags'),
    ('Gift Sets','gifting-sets')
) x(name,slug) join categories c on c.slug = 'gifting'
on conflict(slug) do nothing;


-- ============================================================================
-- 50. SEED BASIC SIZES
-- ============================================================================

insert into sizes(name, size_group) values
('XXS','clothing'),('XS','clothing'),('S','clothing'),('M','clothing'),
('L','clothing'),('XL','clothing'),('XXL','clothing'),('FREE-SIZE','general'),
('8','clothing'),('10','clothing'),('12','clothing'),('14','clothing'),('16','clothing'),
('36','footwear'),('37','footwear'),('38','footwear'),('39','footwear'),
('40','footwear'),('41','footwear'),('42','footwear'),('43','footwear'),
('SINGLE','home'),('DOUBLE','home'),('QUEEN','home'),('KING','home')
on conflict(name) do nothing;


-- ============================================================================
-- 51. SEED COMMON COLORS
-- ============================================================================

insert into colors(name, hex_code) values
('Black','#000000'),('White','#FFFFFF'),('Blue','#0000FF'),('Green','#008000'),
('Red','#FF0000'),('Pink','#FFC0CB'),('Purple','#800080'),('Orange','#FFA500'),
('Yellow','#FFFF00'),('Brown','#A52A2A'),('Beige','#F5F5DC'),('Grey','#808080'),
('Navy','#000080'),('Maroon','#800000'),('Gold','#D4AF37'),('Silver','#C0C0C0'),
('Multi',null)
on conflict(name) do nothing;


-- ============================================================================
-- 52. REGISTER THE 11 CORE AGENTS
-- ============================================================================

insert into agent_registry(agent_key, display_name, description, agent_type) values
('customer_interaction', 'Customer Interaction Agent',
 'Handles English, Roman Urdu and mixed-language conversation, intent detection, entity extraction, clarification and final user-facing response generation.',
 'language'),

('orchestrator', 'Orchestrator Agent',
 'Plans requests, delegates work to specialist agents, parallelizes independent tasks, validates results and coordinates the final response.',
 'orchestrator'),

('memory_context', 'Memory & Context Agent',
 'Loads durable customer context at the start of a conversation and extracts/reconfirms privacy-controlled facts for future conversations.',
 'specialist'),

('product', 'Product Agent',
 'Searches products and variants using names, SKU, category, collection, material, fabric, color, size, attributes, price and other retail attributes.',
 'specialist'),

('inventory', 'Inventory Agent',
 'Verifies exact product-variant availability at branches and reports verified stock states.',
 'specialist'),

('store_location', 'Store & Location Agent',
 'Finds branches, operating information, locations and nearest available stores.',
 'specialist'),

('recommendation', 'Recommendation Agent',
 'Provides explainable product recommendations using category, attributes, price, availability and consented customer preferences.',
 'specialist'),

('alert', 'Alert Agent',
 'Handles price-drop, restock, sale and notification workflows.',
 'specialist'),

('purchase', 'Purchase Agent',
 'Coordinates controlled Smart Cart purchase workflows while relying on deterministic purchase validation and execution.',
 'specialist'),

('support', 'Support Agent',
 'Handles policies, FAQs, feedback classification, complaints, support tickets and human handoff summaries.',
 'specialist'),

('analytics', 'Analytics Agent',
 'Answers staff analytics questions about demand, availability, searches, carts, alerts, feedback and support activity.',
 'specialist')

on conflict(agent_key) do update set
    display_name = excluded.display_name,
    description = excluded.description,
    agent_type = excluded.agent_type;


-- ============================================================================
-- 53. STORAGE: PRODUCT IMAGES BUCKET
--
-- v1.6: product_images (§8, core schema above) is only metadata — a row
-- there points at an image_url, but nothing until now actually created
-- somewhere for that URL to point to. This section creates a Supabase
-- Storage bucket named `product-images` and its access policies.
--
-- Bucket is public=true so product photos can be served directly via their
-- public URL on your storefront/chat UI without a signed URL round-trip.
-- Explicit RLS policies are still added on storage.objects (not just left
-- to the public flag) so uploads/edits/deletes are properly restricted:
-- anyone can read, only staff (or the trusted backend, which uses
-- service_role and bypasses RLS entirely) can write.
--
-- If you'd rather keep product photos private (e.g. served only through
-- your backend via signed URLs), change `public` to `false` below and
-- have FastAPI mint signed URLs with the storage API instead.
-- ============================================================================

insert into storage.buckets (id, name, public)
values ('product-images', 'product-images', true)
on conflict (id) do nothing;

do $$ begin
    create policy public_read_product_images
        on storage.objects for select
        using (bucket_id = 'product-images');
exception when duplicate_object then null; end $$;

do $$ begin
    create policy staff_upload_product_images
        on storage.objects for insert to authenticated
        with check (bucket_id = 'product-images' and is_staff());
exception when duplicate_object then null; end $$;

do $$ begin
    create policy staff_update_product_images
        on storage.objects for update to authenticated
        using (bucket_id = 'product-images' and is_staff())
        with check (bucket_id = 'product-images' and is_staff());
exception when duplicate_object then null; end $$;

do $$ begin
    create policy staff_delete_product_images
        on storage.objects for delete to authenticated
        using (bucket_id = 'product-images' and is_staff());
exception when duplicate_object then null; end $$;


-- ============================================================================
-- 54. FUNCTION EXECUTION SECURITY
--
-- Mutating RPCs (inventory, notifications, Smart Cart evaluation,
-- reservations, purchase) are service_role-ONLY — not `authenticated`.
-- The trusted FastAPI backend authenticates the caller's Supabase JWT
-- itself, then calls these as service_role with a validated customer_id.
-- This closes the gap where an `authenticated` client could otherwise call
-- execute_mock_purchase()/create_reservation() directly with an arbitrary
-- customer_id. Only pure read-only, non-sensitive helpers stay open to
-- `authenticated`.
-- ============================================================================

revoke all on function get_effective_variant_price(uuid) from public;
revoke all on function get_stock_status(integer) from public;
revoke all on function find_branch_for_purchase(uuid, integer, uuid) from public;
revoke all on function adjust_inventory(uuid, uuid, integer, integer, inventory_movement_type, text, uuid, text, jsonb) from public;
revoke all on function queue_notification_delivery(uuid, notification_channel) from public;
revoke all on function create_notification(uuid, notification_type, text, text, jsonb, boolean) from public;
revoke all on function evaluate_smart_cart_rule(uuid, uuid) from public;
revoke all on function evaluate_alerts_for_variant(uuid, retail_event_type, numeric, uuid) from public;
revoke all on function process_retail_event(uuid) from public;
revoke all on function create_reservation(uuid, uuid, uuid, integer, timestamptz) from public;
revoke all on function release_reservation(uuid, reservation_status) from public;
revoke all on function release_expired_reservations() from public;
revoke all on function execute_mock_purchase(uuid, uuid, uuid, integer, text, uuid) from public;
revoke all on function convert_reservation_to_purchase(uuid, text, integer) from public;
revoke all on function activate_due_promotions() from public;

-- Read-only, non-sensitive: safe for the client too
grant execute on function get_effective_variant_price(uuid) to authenticated, service_role;
grant execute on function get_stock_status(integer) to authenticated, service_role;

-- Durable-memory RPCs are backend/service_role-only.
revoke all on function upsert_customer_memory(uuid, customer_memory_type, text, jsonb, numeric, uuid) from public;
revoke all on function get_customer_context_snapshot(uuid) from public;
grant execute on function upsert_customer_memory(uuid, customer_memory_type, text, jsonb, numeric, uuid) to service_role;
grant execute on function get_customer_context_snapshot(uuid) to service_role;

-- Everything else: backend (service_role) only
grant execute on function find_branch_for_purchase(uuid, integer, uuid) to service_role;
grant execute on function adjust_inventory(uuid, uuid, integer, integer, inventory_movement_type, text, uuid, text, jsonb) to service_role;
grant execute on function queue_notification_delivery(uuid, notification_channel) to service_role;
grant execute on function create_notification(uuid, notification_type, text, text, jsonb, boolean) to service_role;
grant execute on function evaluate_smart_cart_rule(uuid, uuid) to service_role;
grant execute on function evaluate_alerts_for_variant(uuid, retail_event_type, numeric, uuid) to service_role;
grant execute on function process_retail_event(uuid) to service_role;
grant execute on function create_reservation(uuid, uuid, uuid, integer, timestamptz) to service_role;
grant execute on function release_reservation(uuid, reservation_status) to service_role;
grant execute on function release_expired_reservations() to service_role;
grant execute on function execute_mock_purchase(uuid, uuid, uuid, integer, text, uuid) to service_role;
grant execute on function convert_reservation_to_purchase(uuid, text, integer) to service_role;
grant execute on function activate_due_promotions() to service_role;


-- ============================================================================
-- END OF RETAILIGENT CORE SCHEMA v1.6
--
-- Deferred / future work (not required for the thesis defense MVP):
--   - Real/sandbox payment integration: add payment_events
--     (provider_event_id unique, payment_method, idempotency_key,
--     updated_at) and have the external sandbox provider confirm payment
--     asynchronously instead of SQL immediately marking it 'paid'.
--   - payment_authorizations (customer_id, provider, provider_customer_ref,
--     provider_method_ref, status, max_amount — never raw card/CVV/PIN
--     data) before wiring true auto-buy to a tokenized payment method.
--   - Finer-grained inventory ledger: split inventory_movements.
--     quantity_delta into on_hand_delta/reserved_delta so a reservation
--     conversion (which can move both at once) is auditable per-field.
--
-- Still needed outside the database (not fixable in SQL alone):
--   - A scheduled job calling activate_due_promotions() and
--     release_expired_reservations() periodically (pg_cron or your
--     FastAPI background scheduler).
--   - FastAPI backend connecting as `service_role` and independently
--     verifying each customer's Supabase JWT before calling any RPC above
--     with that customer's id — the database now assumes this and no
--     longer grants these functions to `authenticated` directly.
--   - Purchase Agent logic: call convert_reservation_to_purchase() when the
--     item being bought is coming out of an existing reservation, and
--     execute_mock_purchase() otherwise — the DB no longer silently lets a
--     reservation's reserved_quantity drift from reality. Both now return
--     jsonb ({success, order_id, purchase_attempt_id, reason_code, reason})
--     instead of a bare uuid — check result->>'success' rather than
--     assuming the call either returns an order id or throws.
--   - Notification delivery worker consuming notification_deliveries
--     (pending -> sent) for email/in-app.
--   - Agent prompts, orchestration, routing, typed tool schemas, parallel
--     execution, conversation context, Roman Urdu handling — all
--     application-layer, not database concerns.
--   - MIGRATION NOTE: this script uses `create table if not exists`. On a
--     fresh Supabase project it will build the whole schema. If you're
--     re-running it against an existing v1.0 Retailigent database, first
--     run manually:
--       alter table purchase_attempts add column if not exists
--           reservation_id uuid references reservations(id);
--     (everything else in this revision is CREATE OR REPLACE
--     functions/views/policies, which do apply cleanly on rerun.)
-- ============================================================================


-- ============================================================================
-- RETAILIGENT — MIGRATION 0003: SEMANTIC / VECTOR PRODUCT SEARCH
--
-- Appended here so this is a single, complete, run-top-to-bottom script for
-- a fresh Supabase project. It still runs logically AFTER the core schema
-- above (it references products, product_variants, colors, sizes,
-- categories), and could be split back out into its own migration file
-- later if you prefer separate migrations in your Supabase project.
-- ============================================================================


-- Adds:
--   - the `vector` extension
--   - product_embeddings (one row per variant, holding the embedding +
--     the exact text that was embedded, for debugging/re-embedding)
--   - a function to build a consistent "search document" string per
--     variant, so re-embedding is reproducible
--   - match_variants_semantic(): pure vector similarity search
--   - search_variants_hybrid(): combines keyword (trigram/plain ILIKE)
--     relevance with vector similarity, so exact SKU/name matches aren't
--     drowned out by "semantically close but wrong" results
--   - an ivfflat index on the embedding column
--
-- Embedding dimension: this migration assumes 1536-dim embeddings (e.g.
-- OpenAI text-embedding-3-small, or a Supabase-hosted equivalent). If your
-- embedding model uses a different dimension, change EMBED_DIM below
-- before running, and adjust the `vector(1536)` column type to match.
-- ============================================================================


-- ============================================================================
-- 0. EXTENSION
-- ============================================================================

create extension if not exists vector;

-- Optional but recommended: trigram support makes the keyword half of the
-- hybrid search much better at fuzzy/partial matches (typos, partial SKUs).
create extension if not exists pg_trgm;

-- v1.10 fix: search_variants_hybrid() calls similarity() against
-- products.name/brand and product_variants.sku with no trigram index behind
-- any of them, so every hybrid search did a full sequential scan + trigram
-- computation over the whole catalog. These make that keyword half of the
-- search scale the way the vector half already does via its ivfflat index.
create index if not exists idx_products_name_trgm
    on products using gin (name gin_trgm_ops);
create index if not exists idx_products_brand_trgm
    on products using gin (brand gin_trgm_ops);
create index if not exists idx_product_variants_sku_trgm
    on product_variants using gin (sku gin_trgm_ops);


-- ============================================================================
-- 1. PRODUCT EMBEDDINGS
-- ============================================================================

create table if not exists product_embeddings (
    id uuid primary key default gen_random_uuid(),
    variant_id uuid not null references product_variants(id) on delete cascade,
    -- The exact text that was embedded, kept so you can inspect/debug why a
    -- given variant matched (or didn't), and so re-embedding after a
    -- model change is reproducible without reconstructing the document.
    search_document text not null,
    embedding vector(1536) not null,
    embedding_model text not null default 'text-embedding-3-small',
    -- v1.10 fix: product/variant edits never marked an existing embedding
    -- as out of date, so semantic search could silently keep serving
    -- results built from stale text indefinitely. This doesn't refresh the
    -- embedding itself (that still requires calling out to an embedding
    -- model, which stays in FastAPI/a backfill job) — it flags which rows
    -- need that refresh, via the triggers below.
    is_stale boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(variant_id)
);

create index if not exists idx_product_embeddings_variant
    on product_embeddings(variant_id);

-- v1.10 fix: lets the backfill/refresh job cheaply find "what needs
-- re-embedding" without scanning the whole table.
create index if not exists idx_product_embeddings_stale
    on product_embeddings(variant_id)
    where is_stale = true;

-- v1.10 fix: mark an existing embedding stale when a product-level field
-- that build_variant_search_document() actually reads changes. Runs for
-- every variant of the product, since the document is built per-variant but
-- pulls in these product-level columns.
create or replace function mark_embeddings_stale_on_product_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.name is distinct from old.name
       or new.description is distinct from old.description
       or new.brand is distinct from old.brand
       or new.gender is distinct from old.gender
       or new.material is distinct from old.material
       or new.attributes is distinct from old.attributes
       or new.category_id is distinct from old.category_id
    then
        update product_embeddings pe
        set is_stale = true, updated_at = now()
        from product_variants v
        where v.id = pe.variant_id
          and v.product_id = new.id
          and pe.is_stale = false;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_product_embedding_stale on products;
create trigger trg_product_embedding_stale
after update on products
for each row execute function mark_embeddings_stale_on_product_change();

-- v1.10 fix: same idea at the variant level, for the variant-level fields
-- build_variant_search_document() reads (color/size/variant attributes).
create or replace function mark_embeddings_stale_on_variant_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.color_id is distinct from old.color_id
       or new.size_id is distinct from old.size_id
       or new.attributes is distinct from old.attributes
    then
        update product_embeddings
        set is_stale = true, updated_at = now()
        where variant_id = new.id
          and is_stale = false;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_variant_embedding_stale on product_variants;
create trigger trg_variant_embedding_stale
after update on product_variants
for each row execute function mark_embeddings_stale_on_variant_change();

-- v1.12: category/color/size names are also embedded text. Renaming one must
-- stale every affected variant embedding just like editing the product/variant.
create or replace function mark_embeddings_stale_on_category_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.name is distinct from old.name then
        update product_embeddings pe
        set is_stale = true, updated_at = now()
        from product_variants v
        join products p on p.id = v.product_id
        where pe.variant_id = v.id
          and p.category_id = new.id
          and pe.is_stale = false;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_category_embedding_stale on categories;
create trigger trg_category_embedding_stale
after update on categories
for each row execute function mark_embeddings_stale_on_category_change();

create or replace function mark_embeddings_stale_on_color_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.name is distinct from old.name then
        update product_embeddings
        set is_stale = true, updated_at = now()
        where variant_id in (
            select id from product_variants where color_id = new.id
        )
          and is_stale = false;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_color_embedding_stale on colors;
create trigger trg_color_embedding_stale
after update on colors
for each row execute function mark_embeddings_stale_on_color_change();

create or replace function mark_embeddings_stale_on_size_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.name is distinct from old.name then
        update product_embeddings
        set is_stale = true, updated_at = now()
        where variant_id in (
            select id from product_variants where size_id = new.id
        )
          and is_stale = false;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_size_embedding_stale on sizes;
create trigger trg_size_embedding_stale
after update on sizes
for each row execute function mark_embeddings_stale_on_size_change();

drop trigger if exists trg_product_embeddings_updated_at on product_embeddings;
create trigger trg_product_embeddings_updated_at
before update on product_embeddings
for each row execute function set_updated_at();

-- ivfflat index for approximate nearest-neighbor search. `lists` is a
-- reasonable default for a catalog in the thousands-of-variants range;
-- retune (roughly sqrt(row_count)) once you have real production volume.
-- Requires ANALYZE after bulk-loading embeddings for good query plans.
create index if not exists idx_product_embeddings_vector
    on product_embeddings
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100)
    where is_stale = false;


-- ============================================================================
-- 2. SEARCH DOCUMENT GENERATION
--
-- Builds a single normalized text blob per variant (product name,
-- category, brand, color, size, key attributes) that your embedding
-- pipeline should send to the embedding model. Keeping this in SQL means
-- the same document text is used whether you regenerate embeddings from
-- FastAPI or from a one-off backfill script.
-- ============================================================================

create or replace function build_variant_search_document(p_variant_id uuid)
returns text
language plpgsql
stable
as $$
declare
    v_doc text;
begin
    -- v1.8 fix: previously omitted products.attributes/material/gender —
    -- the flexible product-level metadata (fabric, occasion, collection,
    -- style, season, etc.) that queries like "elegant Eid lawn kurta" rely
    -- on. Product-level fields are included alongside the variant-level
    -- ones (color/size/variant attributes) so both contribute to the
    -- embedding.
    select concat_ws(' | ',
        p.name,
        p.description,
        c.name,
        p.brand,
        p.gender::text,
        p.material,
        p.attributes::text,
        co.name,
        sz.name,
        v.attributes::text
    )
    into v_doc
    from product_variants v
    join products p on p.id = v.product_id
    left join categories c on c.id = p.category_id
    left join colors co on co.id = v.color_id
    left join sizes sz on sz.id = v.size_id
    where v.id = p_variant_id;

    return v_doc;
end;
$$;


-- ============================================================================
-- 3. SEMANTIC SIMILARITY SEARCH
--
-- Pure vector similarity. `query_embedding` must be computed by your
-- application (FastAPI calls the embedding model, passes the resulting
-- vector in here) — this migration does not call an external embedding
-- API from inside Postgres.
-- ============================================================================

-- v1.10 fix: adding is_stale to the return shape below requires dropping
-- the old signature's return type first — `create or replace` cannot change
-- a function's OUT columns in place.
drop function if exists match_variants_semantic(vector, integer, numeric);

create or replace function match_variants_semantic(
    query_embedding vector(1536),
    match_count integer default 10,
    similarity_threshold numeric default 0.70
)
returns table (
    variant_id uuid,
    product_id uuid,
    similarity numeric,
    is_stale boolean
)
language sql
stable
as $$
    with params as (
        select
            least(greatest(match_count, 1), 100) as result_limit,
            greatest(0::numeric, least(similarity_threshold, 1::numeric)) as min_similarity
    ),
    ann_candidates as materialized (
        select
            pe.variant_id,
            pe.embedding,
            pe.is_stale
        from product_embeddings pe
        where pe.is_stale = false
        order by pe.embedding <=> query_embedding
        limit greatest((select result_limit from params) * 20, 200)
    )
    select
        ac.variant_id,
        v.product_id,
        (1 - (ac.embedding <=> query_embedding))::numeric as similarity,
        ac.is_stale
    from ann_candidates ac
    join product_variants v on v.id = ac.variant_id
    join products p on p.id = v.product_id
    where v.is_active = true
      and p.is_active = true
      and (1 - (ac.embedding <=> query_embedding))
            >= (select min_similarity from params)
    order by ac.embedding <=> query_embedding
    limit (select result_limit from params);
$$;

-- ============================================================================
-- 4. HYBRID SEARCH (keyword + semantic)
--
-- Blends trigram keyword relevance against product name/brand with vector
-- similarity, so an exact or near-exact text match (e.g. a SKU fragment or
-- an exact product name) isn't outranked by a semantically-similar but
-- wrong item. `keyword_weight` + `semantic_weight` need not sum to 1; they
-- are just relative weights.
-- ============================================================================

-- v1.10 fix: same return-type change as match_variants_semantic() above.
drop function if exists search_variants_hybrid(text, vector, integer, numeric, numeric);

-- v1.11 fix: the v1.10 version computed similarity() against every active
-- variant's name/brand/sku (a full scan + score calculation over the whole
-- catalog) and computed vector distance against every row in
-- product_embeddings (bypassing the ivfflat ANN index entirely) — the GIN
-- trigram indexes added in v1.10 sat unused, because a plain
-- similarity(column, query) call is not itself index-backed; only the `%`
-- operator (pg_trgm's indexable "is this similar enough" test) is. This
-- version narrows to a small candidate set FIRST, using operators each
-- index actually accelerates — `%` for keyword, `<=>` ordering + LIMIT for
-- an ANN semantic probe — and only computes the precise similarity()/
-- cosine-distance scores for that candidate set afterward. Functionally
-- equivalent for a normal query; the difference is what the query planner
-- can actually use an index for.
create or replace function search_variants_hybrid(
    query_text text,
    query_embedding vector(1536),
    match_count integer default 10,
    keyword_weight numeric default 0.35,
    semantic_weight numeric default 0.65
)
returns table (
    variant_id uuid,
    product_id uuid,
    combined_score numeric,
    keyword_score numeric,
    semantic_score numeric,
    is_stale boolean
)
language sql
stable
set pg_trgm.similarity_threshold = 0.05
as $$
    with params as (
        select
            least(greatest(match_count, 1), 100) as result_limit,
            greatest(least(greatest(match_count, 1), 100) * 20, 200) as candidate_limit
    ),
    name_candidates as materialized (
        select
            v.id as variant_id,
            similarity(p.name, query_text)::numeric as field_score
        from product_variants v
        join products p on p.id = v.product_id
        where v.is_active = true
          and p.is_active = true
          and p.name % query_text
        order by similarity(p.name, query_text) desc
        limit (select candidate_limit from params)
    ),
    brand_candidates as materialized (
        select
            v.id as variant_id,
            similarity(p.brand, query_text)::numeric as field_score
        from product_variants v
        join products p on p.id = v.product_id
        where v.is_active = true
          and p.is_active = true
          and p.brand % query_text
        order by similarity(p.brand, query_text) desc
        limit (select candidate_limit from params)
    ),
    sku_candidates as materialized (
        select
            v.id as variant_id,
            similarity(v.sku, query_text)::numeric as field_score
        from product_variants v
        join products p on p.id = v.product_id
        where v.is_active = true
          and p.is_active = true
          and v.sku % query_text
        order by similarity(v.sku, query_text) desc
        limit (select candidate_limit from params)
    ),
    keyword_candidates as materialized (
        select variant_id
        from (
            select variant_id, max(field_score) as best_keyword_score
            from (
                select * from name_candidates
                union all
                select * from brand_candidates
                union all
                select * from sku_candidates
            ) raw_keyword_candidates
            group by variant_id
            order by max(field_score) desc
            limit (select candidate_limit from params)
        ) bounded_keywords
    ),
    semantic_candidates as materialized (
        select pe.variant_id
        from product_embeddings pe
        where pe.is_stale = false
        order by pe.embedding <=> query_embedding
        limit (select candidate_limit from params)
    ),
    candidates as (
        select variant_id from keyword_candidates
        union
        select variant_id from semantic_candidates
    ),
    scored as (
        select
            v.id as variant_id,
            v.product_id,
            greatest(
                similarity(p.name, query_text),
                similarity(coalesce(p.brand, ''), query_text),
                similarity(coalesce(v.sku, ''), query_text)
            )::numeric as keyword_score,
            case
                when pe.id is null or pe.is_stale then null
                else (1 - (pe.embedding <=> query_embedding))::numeric
            end as semantic_score,
            (pe.id is null or pe.is_stale) as is_stale
        from candidates c
        join product_variants v on v.id = c.variant_id
        join products p on p.id = v.product_id
        left join product_embeddings pe on pe.variant_id = v.id
        where v.is_active = true
          and p.is_active = true
    )
    select
        variant_id,
        product_id,
        (
            (greatest(keyword_weight, 0) * coalesce(keyword_score, 0))
            + (greatest(semantic_weight, 0) * coalesce(semantic_score, 0))
        )::numeric as combined_score,
        coalesce(keyword_score, 0)::numeric as keyword_score,
        coalesce(semantic_score, 0)::numeric as semantic_score,
        is_stale
    from scored
    where coalesce(keyword_score, 0) > 0.05
       or coalesce(semantic_score, 0) >= 0.55
    order by combined_score desc
    limit (select result_limit from params);
$$;

-- ============================================================================
-- 5. FUNCTION EXECUTION SECURITY
--
-- v1.4: search RPCs are now service_role-only. They are plain (invoker-
-- rights) SQL functions, and product_embeddings has RLS enabled with only
-- a service_role policy — so granting these to `authenticated` directly
-- would have meant an authenticated client's call ran under RLS that hides
-- every embedding row anyway (returns nothing useful) while adding a
-- confusing extra attack surface for no benefit. Since the architecture
-- already routes everything through the trusted FastAPI backend
-- (service_role), search goes through FastAPI like every other RPC here.
-- document generation stays service_role-only too, for the backfill/
-- embedding pipeline.
-- ============================================================================

revoke all on function build_variant_search_document(uuid) from public;
grant execute on function build_variant_search_document(uuid) to service_role;

revoke all on function match_variants_semantic(vector, integer, numeric) from public;
grant execute on function match_variants_semantic(vector, integer, numeric) to service_role;

revoke all on function search_variants_hybrid(text, vector, integer, numeric, numeric) from public;
grant execute on function search_variants_hybrid(text, vector, integer, numeric, numeric) to service_role;

alter table product_embeddings enable row level security;

-- Embeddings are internal search infrastructure, not customer data — no
-- customer-facing policy is needed. Only service_role (the backend
-- embedding pipeline) writes/reads the raw table directly; clients only
-- ever go through the RPCs above.
do $$ begin
    create policy service_role_all_embeddings
        on product_embeddings
        for all
        to service_role
        using (true)
        with check (true);
exception when duplicate_object then null; end $$;


-- ============================================================================
-- END OF MIGRATION 0003
--
-- Still needed outside the database:
--   - A backfill script/endpoint that, for every active variant, calls
--     build_variant_search_document(), sends the result to your embedding
--     model, and upserts the vector into product_embeddings.
--   - A background re-embedding worker that consumes rows where is_stale=true.
--     This schema DOES flag embeddings stale automatically when embedded
--     product/variant/category/color/size fields change; it intentionally does
--     not call an external embedding model from inside PostgreSQL.
--   - FastAPI wiring: compute query_embedding for the user's message, then
--     call search_variants_hybrid() (preferred) or match_variants_semantic()
--     as service_role.
-- ============================================================================
