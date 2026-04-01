"""API routes for v2w cloud service."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.schemas import (
    ConvertResponse,
    ContentBlock,
    GenerateWordRequest,
    HealthResponse,
    RecognizeResponse,
)
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


def _validate_image_upload(file: UploadFile) -> None:
    """Raise HTTPException if *file* is not a supported image type."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type '{file.content_type}'. "
            f"Accepted types: {sorted(_ALLOWED_CONTENT_TYPES)}",
        )


@router.post(
    "/recognize",
    response_model=RecognizeResponse,
    tags=["conversion"],
    summary="Recognise text and formulas from a screenshot",
    responses={
        400: {"description": "Invalid or unsupported image format."},
        422: {"description": "Validation error."},
        500: {"description": "Internal processing error."},
    },
)
async def recognize_image(
    file: Annotated[UploadFile, File(description="Screenshot image (PNG / JPEG / WebP / BMP / TIFF)")],
) -> RecognizeResponse:
    """Upload a screenshot and receive a JSON list of recognised text and LaTeX formula blocks.

    - **text** blocks contain the plain text recognised by OCR.
    - **formula** blocks contain the LaTeX string recognised by pix2tex.

    Use the returned blocks to preview the content before generating a Word document.
    """
    _validate_image_upload(file)

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        raw_blocks, text_count, formula_count = _image_processor.process(image_bytes)
    except Exception as exc:
        logger.exception("Error recognising image '%s'.", file.filename)
        raise HTTPException(status_code=500, detail=f"Recognition failed: {exc}") from exc

    blocks = [ContentBlock(block_type=bt, content=c) for bt, c in raw_blocks]
    total = text_count + formula_count
    message = (
        f"识别完成：{text_count} 段文字，{formula_count} 个公式。"
        if total > 0
        else "未能从图片中识别出任何内容。"
    )
    return RecognizeResponse(
        blocks=blocks,
        text_count=text_count,
        formula_count=formula_count,
        message=message,
    )


@router.post(
    "/generate-word",
    response_class=Response,
    tags=["conversion"],
    summary="Generate a Word document from recognised blocks",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            },
            "description": "Word document (.docx).",
        },
        422: {"description": "Validation error."},
        500: {"description": "Internal processing error."},
    },
)
async def generate_word(request: GenerateWordRequest) -> Response:
    """Convert a list of recognised content blocks into a Word document.

    Accepts the JSON payload returned by the ``/recognize`` endpoint (after
    optional user edits) and returns the binary ``.docx`` file.
    """
    try:
        raw_blocks = [(b.block_type, b.content) for b in request.blocks]
        docx_bytes = _word_generator.generate(
            raw_blocks,
            title=request.title,
        )
    except Exception as exc:
        logger.exception("Error generating Word document.")
        raise HTTPException(status_code=500, detail=f"Word generation failed: {exc}") from exc

    safe_name = (request.title or "output").rsplit(".", 1)[0] + ".docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
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

    - **Text** regions are inserted as editable paragraphs.
    - **Formula** regions are converted to editable OMML equations (Word native
      math format, fully compatible with Word's equation editor and MathType).

    The endpoint returns the `.docx` file as a binary download.
    """
    _validate_image_upload(file)

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
