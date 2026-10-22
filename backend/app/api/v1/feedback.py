from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    get_current_user_id,
    require_customer,
    require_staff,
)
from app.schemas.feedback import (
    FeedbackClassificationCorrection,
    FeedbackCreate,
)
from app.services import feedback_service
from app.services.feedback_service import FeedbackServiceError

router = APIRouter(
    prefix="/api/v1/feedback",
    tags=["feedback"],
)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_feedback(
    request: FeedbackCreate,
    customer_id: str = Depends(get_current_user_id),
    _role: str = Depends(require_customer),
) -> dict:
    try:
        return feedback_service.submit_feedback(
            customer_id=customer_id,
            feedback_type=request.feedback_type,
            rating=request.rating,
            message=request.message,
            conversation_id=(
                str(request.conversation_id)
                if request.conversation_id
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FeedbackServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/mine")
def get_my_feedback(
    limit: int = Query(default=50, ge=1, le=100),
    customer_id: str = Depends(get_current_user_id),
    _role: str = Depends(require_customer),
) -> dict:
    try:
        rows = feedback_service.list_customer_feedback(
            customer_id,
            limit=limit,
        )
        return {"feedback": rows, "count": len(rows)}
    except FeedbackServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/review-queue")
def get_feedback_review_queue(
    limit: int = Query(default=100, ge=1, le=200),
    _role: str = Depends(require_staff),
) -> dict:
    try:
        rows = feedback_service.list_feedback_review_queue(
            limit=limit,
        )
        return {"feedback": rows, "count": len(rows)}
    except FeedbackServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.patch("/{feedback_id}/classification")
def update_feedback_classification(
    feedback_id: UUID,
    request: FeedbackClassificationCorrection,
    _role: str = Depends(require_staff),
) -> dict:
    try:
        return feedback_service.correct_feedback_classification(
            feedback_id=str(feedback_id),
            staff_category=request.staff_category,
            staff_sentiment=request.staff_sentiment,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback record not found.",
        ) from exc
    except FeedbackServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
