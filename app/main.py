"""FastAPI application entry point for the v2w formula recognition service."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router
from app.services.formula import FormulaRecognitionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

logger = logging.getLogger(__name__)

_cors_origins_env = os.getenv("CORS_ORIGINS", "*")
_cors_origins = (
    ["*"] if _cors_origins_env == "*" else [o.strip() for o in _cors_origins_env.split(",")]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: eagerly load the formula model at startup.

    This mirrors the pattern used by the pix2tex reference API, which calls
    ``LatexOCR()`` inside ``@app.on_event('startup')`` so the model is warm
    and ready before the first prediction request arrives.
    """
    formula_service = FormulaRecognitionService()
    try:
        await asyncio.to_thread(formula_service.initialize)
    except Exception:
        logger.warning(
            "Formula model pre-loading failed; the model will be retried on each request.",
            exc_info=True,
        )

    app.state.formula_service = formula_service
    logger.info("Application startup complete.")

    yield

    logger.info("Application shutting down.")


app = FastAPI(
    title="v2w – Formula Recognition",
    description=(
        "A service that recognises mathematical formulas from images and returns "
        "the corresponding LaTeX code, powered by pix2tex (LaTeX-OCR)."
    ),
    version="1.0.0",
    contact={
        "name": "v2w project",
        "url": "https://github.com/rs-v/v2w",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# Mount static files directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Serve the web interface homepage."""
    return FileResponse("app/static/index.html")
