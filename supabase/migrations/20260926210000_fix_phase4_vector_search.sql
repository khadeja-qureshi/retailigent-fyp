-- ============================================================================
-- RETAILIGENT
-- Phase 4: Fix Semantic + Hybrid Vector Search
-- ============================================================================
--
-- Fix:
-- Materialize the query embedding before ANN/vector ordering.
--
-- The previous implementation used the function parameter directly inside
-- the candidate CTE's ORDER BY. PostgreSQL returned no rows for query
-- embeddings in that form. Materializing the query vector resolves this.
--
-- No schema changes.
-- No data changes.
-- ============================================================================


-- ============================================================================
-- 1. FIX SEMANTIC SEARCH
-- ============================================================================

CREATE OR REPLACE FUNCTION public.match_variants_semantic(
    query_embedding vector(1536),
    match_count integer DEFAULT 10,
    similarity_threshold numeric DEFAULT 0.70
)
RETURNS TABLE (
    variant_id uuid,
    product_id uuid,
    similarity numeric,
    is_stale boolean
)
LANGUAGE sql
STABLE
AS $function$
    WITH
    params AS MATERIALIZED (
        SELECT
            least(greatest(match_count, 1), 100) AS result_limit,
            greatest(
                0::numeric,
                least(similarity_threshold, 1::numeric)
            ) AS min_similarity
    ),

    query AS MATERIALIZED (
        SELECT query_embedding AS embedding
    ),

    ann_candidates AS MATERIALIZED (
        SELECT
            pe.variant_id,
            pe.embedding,
            pe.is_stale
        FROM public.product_embeddings pe
        CROSS JOIN query q
        WHERE pe.is_stale = false
        ORDER BY pe.embedding <=> q.embedding
        LIMIT greatest(
            (SELECT result_limit FROM params) * 20,
            200
        )
    )

    SELECT
        ac.variant_id,
        v.product_id,
        (
            1 - (ac.embedding <=> q.embedding)
        )::numeric AS similarity,
        ac.is_stale

    FROM ann_candidates ac

    JOIN public.product_variants v
        ON v.id = ac.variant_id

    JOIN public.products p
        ON p.id = v.product_id

    CROSS JOIN query q

    WHERE v.is_active = true
      AND p.is_active = true
      AND (
          1 - (ac.embedding <=> q.embedding)
      ) >= (SELECT min_similarity FROM params)

    ORDER BY ac.embedding <=> q.embedding

    LIMIT (SELECT result_limit FROM params);
$function$;


-- ============================================================================
-- 2. FIX HYBRID SEARCH
-- ============================================================================

CREATE OR REPLACE FUNCTION public.search_variants_hybrid(
    query_text text,
    query_embedding vector(1536),
    match_count integer DEFAULT 10,
    keyword_weight numeric DEFAULT 0.35,
    semantic_weight numeric DEFAULT 0.65
)
RETURNS TABLE (
    variant_id uuid,
    product_id uuid,
    combined_score numeric,
    keyword_score numeric,
    semantic_score numeric,
    is_stale boolean
)
LANGUAGE sql
STABLE
AS $function$
    WITH
    params AS MATERIALIZED (
        SELECT
            least(greatest(match_count, 1), 100) AS result_limit,
            greatest(0::numeric, keyword_weight) AS kw_weight,
            greatest(0::numeric, semantic_weight) AS sem_weight
    ),

    query AS MATERIALIZED (
        SELECT
            query_text AS text,
            query_embedding AS embedding
    ),

    keyword_candidates AS MATERIALIZED (
        SELECT
            v.id AS variant_id,
            v.product_id,
            greatest(
                similarity(coalesce(p.name, ''), q.text),
                similarity(coalesce(p.brand, ''), q.text),
                similarity(coalesce(v.sku, ''), q.text)
            )::numeric AS keyword_score

        FROM public.product_variants v

        JOIN public.products p
            ON p.id = v.product_id

        CROSS JOIN query q

        WHERE v.is_active = true
          AND p.is_active = true

        ORDER BY keyword_score DESC

        LIMIT 200
    ),

    semantic_candidates AS MATERIALIZED (
        SELECT
            pe.variant_id,
            v.product_id,
            (
                1 - (pe.embedding <=> q.embedding)
            )::numeric AS semantic_score,
            pe.is_stale

        FROM public.product_embeddings pe

        JOIN public.product_variants v
            ON v.id = pe.variant_id

        JOIN public.products p
            ON p.id = v.product_id

        CROSS JOIN query q

        WHERE pe.is_stale = false
          AND v.is_active = true
          AND p.is_active = true

        ORDER BY pe.embedding <=> q.embedding

        LIMIT 200
    ),

    candidates AS MATERIALIZED (
        SELECT
            variant_id,
            product_id
        FROM keyword_candidates

        UNION

        SELECT
            variant_id,
            product_id
        FROM semantic_candidates
    ),

    scored AS (
        SELECT
            c.variant_id,
            c.product_id,

            greatest(
                coalesce(k.keyword_score, 0::numeric),
                0::numeric
            ) AS keyword_score,

            coalesce(
                s.semantic_score,
                0::numeric
            ) AS semantic_score,

            coalesce(
                s.is_stale,
                false
            ) AS is_stale

        FROM candidates c

        LEFT JOIN keyword_candidates k
            ON k.variant_id = c.variant_id

        LEFT JOIN semantic_candidates s
            ON s.variant_id = c.variant_id
    )

    SELECT
        sc.variant_id,
        sc.product_id,

        (
            (SELECT kw_weight FROM params)
            * sc.keyword_score

            +

            (SELECT sem_weight FROM params)
            * sc.semantic_score

        )::numeric AS combined_score,

        sc.keyword_score,
        sc.semantic_score,
        sc.is_stale

    FROM scored sc

    WHERE
        sc.keyword_score > 0.05
        OR sc.semantic_score >= 0.55

    ORDER BY combined_score DESC

    LIMIT (SELECT result_limit FROM params);
$function$;