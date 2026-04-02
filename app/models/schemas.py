from typing import List, Optional

from pydantic import BaseModel


class ConvertResponse(BaseModel):
    """Response model for image-to-Word conversion."""

    filename: str
    text_blocks: int
    formula_blocks: int
    message: str


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    services: dict


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str
    error_type: Optional[str] = None


class ContentBlock(BaseModel):
    """A single recognised content block (text or LaTeX formula)."""

    block_type: str  # "text" or "formula"
    content: str


class RecognizeResponse(BaseModel):
    """Response model for the /recognize endpoint."""

    blocks: List[ContentBlock]
    text_count: int
    formula_count: int
    message: str


class GenerateWordRequest(BaseModel):
    """Request body for the /generate-word endpoint."""

    blocks: List[ContentBlock]
    title: Optional[str] = None
