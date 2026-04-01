from typing import Optional

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
