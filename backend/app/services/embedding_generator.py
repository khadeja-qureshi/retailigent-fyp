from app.core.supabase_client import supabase_admin
from app.services.embedding_service import generate_embedding


EMBEDDING_MODEL = "qwen3-embedding:4b"


def generate_product_embeddings() -> int:
    """
    Generate and store embeddings for all active product variants.

    Existing fresh embeddings are skipped.
    """

    # Get all active variants
    variant_response = (
        supabase_admin
        .table("product_variants")
        .select("id")
        .eq("is_active", True)
        .execute()
    )

    variants = variant_response.data

    if not variants:
        print("No active product variants found.")
        return 0

    generated_count = 0

    for variant in variants:
        variant_id = variant["id"]

        # Get the canonical search document from the database
        document_response = supabase_admin.rpc(
            "build_variant_search_document",
            {
                "p_variant_id": variant_id
            },
        ).execute()

        search_document = document_response.data

        if not search_document:
            print(
                f"Skipping {variant_id}: "
                "no search document returned."
            )
            continue

        # Check whether a fresh embedding already exists
        existing_response = (
            supabase_admin
            .table("product_embeddings")
            .select("id, is_stale")
            .eq("variant_id", variant_id)
            .eq("is_stale", False)
            .limit(1)
            .execute()
        )

        if existing_response.data:
            print(
                f"Skipping {variant_id}: "
                "fresh embedding already exists."
            )
            continue

        print(f"Generating embedding for {variant_id}...")

        embedding = generate_embedding(search_document)

        # Insert embedding
        supabase_admin.table("product_embeddings").insert(
            {
                "variant_id": variant_id,
                "search_document": search_document,
                "embedding": embedding,
                "embedding_model": EMBEDDING_MODEL,
                "is_stale": False,
            }
        ).execute()

        generated_count += 1

        print(
            f"Stored embedding for {variant_id} "
            f"({len(embedding)} dimensions)"
        )

    return generated_count