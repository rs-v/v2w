from typing import Optional

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
