from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.analytics_agent import analytics_agent
from app.core.auth import require_staff
from app.schemas.analytics import AnalyticsQuestion
from app.services import analytics_service
from app.services.analytics_service import AnalyticsServiceError

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"],
)


@router.get("/demand")
def get_demand_analytics(
    limit: int = Query(default=50, ge=1, le=100),
    _role: str = Depends(require_staff),
) -> dict:
    try:
        result = analytics_service.get_demand_analytics(
            limit=limit,
        )
        return {
            **result,
            "count": {
                key: len(rows)
                for key, rows in result.items()
            },
        }
    except AnalyticsServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.get("/inventory")
def get_inventory_analytics(
    limit: int = Query(default=50, ge=1, le=100),
    _role: str = Depends(require_staff),
) -> dict:
    try:
        result = analytics_service.get_inventory_analytics(
            limit=limit,
        )
        return {
            **result,
            "count": {
                key: len(rows)
                for key, rows in result.items()
            },
        }
    except AnalyticsServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.post("/ask")
def ask_analytics(
    payload: AnalyticsQuestion,
    _role: str = Depends(require_staff),
) -> dict:
    try:
        return analytics_agent.answer(payload.question)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
