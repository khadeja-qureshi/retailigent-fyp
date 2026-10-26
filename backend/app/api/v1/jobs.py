from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import require_admin
from app.schemas.jobs import RequeueRequest, RequeueResponse
from app.services import job_service
from app.services.job_service import JobServiceError

# Public: for uptime monitors. Deliberately minimal: names, timestamps and
# counts only. No error text and no data (see /api/v1/admin/jobs for that).
health_router = APIRouter(tags=["health"])


@health_router.get("/health/jobs")
def jobs_health(request: Request) -> dict:
    scheduler = getattr(request.app.state, "scheduler", None)

    if scheduler is None:
        return {"status": "disabled", "scheduler_started_at": None, "jobs": []}

    return scheduler.snapshot(include_errors=False)


router = APIRouter(prefix="/api/v1/admin/jobs", tags=["jobs"])


@router.get("")
def get_jobs(request: Request, _role: str = Depends(require_admin)) -> dict:
    """
    Administrators only. Live state of this API instance's scheduler (with
    error text), heartbeats recorded in the database, and the notification
    delivery backlog including dead letters.
    """

    scheduler = getattr(request.app.state, "scheduler", None)

    try:
        recorded = job_service.get_job_overview()
    except JobServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {
        "scheduler": (
            scheduler.snapshot(include_errors=True)
            if scheduler is not None
            else {"status": "disabled", "jobs": []}
        ),
        **recorded,
    }


@router.post(
    "/notification-dead-letters/requeue",
    response_model=RequeueResponse,
)
def requeue_dead_letters(
    payload: RequeueRequest,
    _role: str = Depends(require_admin),
) -> dict:
    """Put dead-lettered notification deliveries back in the queue (audited)."""

    try:
        count = job_service.requeue_dead_letters(payload.delivery_ids)
    except JobServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"requeued": count}
