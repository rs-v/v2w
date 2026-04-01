"""API routes for v2w cloud service."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.schemas import ConvertResponse, HealthResponse
from app.services.image_processor import ImageProcessor
from app.services.word_gen import WordGeneratorService

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared service instances (initialised once, models loaded lazily)
_image_processor = ImageProcessor()
_word_generator = WordGeneratorService()

_ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health_check() -> HealthResponse:
    """Return service health information."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        services={
            "ocr": "easyocr",
            "formula": "pix2tex",
            "word": "python-docx",
        },
    )


@router.post(
    "/convert",
    response_class=Response,
    tags=["conversion"],
    summary="Convert a screenshot to a Word document",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
            "description": "Word document (.docx) containing the recognised content.",
        },
        400: {"description": "Invalid or unsupported image format."},
        422: {"description": "Validation error."},
        500: {"description": "Internal processing error."},
    },
)
async def convert_image_to_word(
    file: Annotated[UploadFile, File(description="Screenshot image (PNG / JPEG / WebP / BMP / TIFF)")],
) -> Response:
    """Upload a screenshot and receive a Word document with recognised text and formulas.

    - **Text** regions are inserted as paragraphs.
    - **Formula** regions are rendered as images (with their LaTeX source).

    The endpoint returns the `.docx` file as a binary download.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type '{file.content_type}'. "
            f"Accepted types: {sorted(_ALLOWED_CONTENT_TYPES)}",
        )

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        blocks, text_count, formula_count = _image_processor.process(image_bytes)
        docx_bytes = _word_generator.generate(
            blocks,
            title=file.filename or "Converted Document",
        )
    except Exception as exc:
        logger.exception("Error processing image '%s'.", file.filename)
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    safe_name = (file.filename or "output").rsplit(".", 1)[0] + ".docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
