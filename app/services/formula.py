"""Formula recognition service using pix2tex (LaTeX OCR)."""

from __future__ import annotations

import io
import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


class FormulaRecognitionService:
    """Converts an image containing a mathematical formula into LaTeX markup.

    The underlying model is pix2tex (https://github.com/lukas-blecher/LaTeX-OCR).
    The model is loaded lazily on first use.
    """

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        """Lazily initialise the pix2tex LatexOCR model."""
        if self._model is None:
            from pix2tex.cli import LatexOCR  # noqa: PLC0415

            self._model = LatexOCR()
        return self._model

    def recognise(self, image: Image.Image) -> Optional[str]:
        """Convert *image* to a LaTeX string.

        Parameters
        ----------
        image:
            A PIL ``Image`` containing a formula.

        Returns
        -------
        LaTeX string, or ``None`` if recognition fails.
        """
        try:
            model = self._get_model()
            latex = model(image)
            logger.debug("Formula recognised: %s", latex)
            return latex
        except Exception:
            logger.exception("Formula recognition failed.")
            return None

    def recognise_from_bytes(self, data: bytes) -> Optional[str]:
        """Convenience wrapper that accepts raw image bytes."""
        image = Image.open(io.BytesIO(data)).convert("RGB")
        return self.recognise(image)
