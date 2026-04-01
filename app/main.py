"""FastAPI application entry point for the v2w cloud service."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

# Allow callers to restrict CORS origins via an environment variable.
# In development the default is "*"; in production set CORS_ORIGINS to a
# comma-separated list of trusted origins, e.g.
#   CORS_ORIGINS=https://app.example.com,https://admin.example.com
_cors_origins_env = os.getenv("CORS_ORIGINS", "*")
_cors_origins = (
    ["*"] if _cors_origins_env == "*" else [o.strip() for o in _cors_origins_env.split(",")]
)

app = FastAPI(
    title="v2w – Screenshot to Word",
    description=(
        "A cloud service that recognises text and mathematical formulas from "
        "screenshots and converts them to Microsoft Word (.docx) documents."
    ),
    version="1.0.0",
    contact={
        "name": "v2w project",
        "url": "https://github.com/rs-v/v2w",
    },
    license_info={
        "name": "MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "v2w service is running. Visit /docs for the API documentation."}
