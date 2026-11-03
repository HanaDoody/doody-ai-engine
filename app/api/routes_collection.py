"""POST /collection/capture."""
from fastapi import APIRouter, HTTPException

from app.core import collection_handler
from app.schemas.collection import CaptureRequest, CaptureResponse

router = APIRouter(prefix="/collection", tags=["collection"])


@router.post("/capture", response_model=CaptureResponse)
def capture(req: CaptureRequest) -> CaptureResponse:
    try:
        return collection_handler.capture(
            req.pin_id,
            current_ari=req.current_ari,
            energy=req.energy,
            current_collection_count=req.current_collection_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
