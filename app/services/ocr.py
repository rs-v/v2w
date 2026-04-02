"""Text OCR service using EasyOCR."""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Bounding box returned by EasyOCR: list of four [x, y] corner points (pixels)
BBox = List[List[float]]


class TextOCRService:
    """Recognises plain text regions in an image using EasyOCR."""

    def __init__(self, languages: List[str] | None = None) -> None:
        self._languages = languages or ["ch_sim", "en"]
        self._reader = None

    def _get_reader(self):
        """Lazily initialise the EasyOCR reader to speed up import time."""
        if self._reader is None:
            try:
                import easyocr  # noqa: PLC0415
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "EasyOCR is not installed. "
                    "Run `pip install easyocr>=1.7.1` (or `pip install -r requirements.txt`) "
                    "and restart the server."
                ) from exc

            self._reader = easyocr.Reader(self._languages, gpu=False, verbose=False)
        return self._reader

    def recognise(self, image: Image.Image) -> List[Tuple[BBox, str, float]]:
        """Return a list of ``(bbox, text, confidence)`` tuples from *image*.

        Parameters
        ----------
        image:
            A PIL ``Image`` object (any mode accepted).

        Returns
        -------
        List of ``(bbox, text, confidence)`` tuples ordered top-to-bottom,
        where *bbox* is the list of four ``[x, y]`` corner points returned by
        EasyOCR (top-left → top-right → bottom-right → bottom-left).
        """
        img_array = np.array(image.convert("RGB"))
        reader = self._get_reader()
        results = reader.readtext(img_array, detail=1, paragraph=False)
        output: List[Tuple[BBox, str, float]] = []
        for bbox, text, confidence in results:
            if text.strip():
                output.append((bbox, text.strip(), float(confidence)))
        logger.debug("OCR found %d text block(s).", len(output))
        return output
