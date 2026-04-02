"""API routes for v2w – formula recognition service."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.models.schemas import HealthResponse, PredictResponse
from app.services.formula import FormulaRecognitionService

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


# ---------------------------------------------------------------------------
# Dependency providers – read pre-loaded services from application state.
# Following the same pattern as pix2tex's API, where the model is loaded
# once at startup and reused for every request.
# ---------------------------------------------------------------------------


def get_formula_service(request: Request) -> FormulaRecognitionService:
    """Return the FormulaRecognitionService stored in application state."""
    return request.app.state.formula_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check() -> HealthResponse:
    """Return service health information."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        services={"formula": "pix2tex"},
    )


def _validate_image_upload(file: UploadFile) -> None:
    """Raise HTTPException if *file* is not a supported image type."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type '{file.content_type}'. "
            f"Accepted types: {sorted(_ALLOWED_CONTENT_TYPES)}",
        )


@router.post(
    "/predict",
    response_model=PredictResponse,
    tags=["formula"],
    summary="Predict LaTeX from a formula image",
    responses={
        400: {"description": "Invalid or unsupported image format."},
        422: {"description": "Validation error."},
        500: {"description": "Internal processing error."},
    },
)
async def predict(
    file: Annotated[UploadFile, File(description="Formula image (PNG / JPEG / WebP / BMP / TIFF)")],
    formula_service: FormulaRecognitionService = Depends(get_formula_service),
) -> PredictResponse:
    """Upload an image of a mathematical formula and receive the corresponding LaTeX string.

    Mirrors the ``/predict/`` endpoint of the pix2tex reference API.
    """
    _validate_image_upload(file)

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        latex = formula_service.recognise_from_bytes(image_bytes)
    except Exception as exc:
        logger.exception("Error processing image '%s'.", file.filename)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc

    if latex:
        return PredictResponse(latex=latex, message="公式识别成功。")
    return PredictResponse(latex=None, message="未能从图片中识别出公式。")
