from fastapi import APIRouter, Query

from app.services.search_service import search_variants


router = APIRouter(
    prefix="/api/v1/search",
    tags=["Search"],
)


@router.get("")
def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    results = search_variants(
        query=q,
        match_count=limit,
    )

    return {
        "query": q,
        "count": len(results),
        "results": results,
    }