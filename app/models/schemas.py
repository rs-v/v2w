from typing import List, Literal, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    services: dict


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str
    error_type: Optional[str] = None


class PredictResponse(BaseModel):
    """Response model for the /predict endpoint."""

    latex: Optional[str]
    message: str


class Block(BaseModel):
    """A single recognised content block."""

    block_type: Literal["formula", "text"]
    content: str


class RecognizeResponse(BaseModel):
    """Response model for the /recognize endpoint."""

    blocks: List[Block]
    message: str
