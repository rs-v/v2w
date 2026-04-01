"""Image processing pipeline: orchestrates OCR + formula recognition."""

from __future__ import annotations

import io
import logging
from typing import List, Tuple

from PIL import Image

from app.services.formula import FormulaRecognitionService
from app.services.ocr import BBox, TextOCRService
from app.services.word_gen import FORMULA_BLOCK, TEXT_BLOCK

logger = logging.getLogger(__name__)

# Heuristic: if more than this fraction of detected characters look like math
# symbols we treat the whole block as a formula region.
_MATH_CHARS = set(
    # Greek letters and special math symbols
    "∑∏∫∂∇αβγδεζηθικλμνξοπρσςτυφχψωΩ±×÷√∞∈∉⊂⊃∪∩≤≥≠≈→←↑↓"
    # Common ASCII math operators and punctuation that rarely appear in plain text
    "^_{}\\|"
)
_MATH_THRESHOLD = 0.05

# Patterns that strongly indicate a mathematical expression even without
# special Unicode math characters.  We check these as secondary signals.
import re as _re

_MATH_PATTERN = _re.compile(
    r"""
    # Fraction-like: digit/digit or variable/variable
    [A-Za-z0-9]\s*/\s*[A-Za-z0-9]
    # Exponent notation: x^2, e^{...}
    |[A-Za-z0-9]\^
    # Subscript notation: x_i, a_{ij}
    |[A-Za-z0-9]_
    # Common operators surrounded by operands
    |[A-Za-z0-9]\s*[+\-=<>]\s*[A-Za-z0-9]
    # Lone equals sign between math-ish tokens
    |=\s*[A-Za-z0-9]
    """,
    _re.VERBOSE,
)


def _is_likely_formula(text: str) -> bool:
    """Return ``True`` if *text* looks like it contains a mathematical formula."""
    if not text:
        return False
    math_count = sum(1 for ch in text if ch in _MATH_CHARS)
    ratio = math_count / len(text)
    if ratio >= _MATH_THRESHOLD:
        return True
    # Secondary check: look for ASCII math expression patterns
    if _MATH_PATTERN.search(text):
        return True
    return False


def _crop_to_bbox(image: Image.Image, bbox: BBox) -> Image.Image:
    """Crop *image* to the axis-aligned rectangle enclosing *bbox*.

    *bbox* is a list of four ``[x, y]`` corner points as returned by EasyOCR.
    A small padding is added so that formula edges are not clipped.
    """
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    padding = 10
    left = max(0, int(min(xs)) - padding)
    upper = max(0, int(min(ys)) - padding)
    right = min(image.width, int(max(xs)) + padding)
    lower = min(image.height, int(max(ys)) + padding)
    return image.crop((left, upper, right, lower))


class ImageProcessor:
    """High-level pipeline that converts an image to content blocks.

    Content blocks are ``(block_type, content)`` tuples where *block_type* is
    ``"text"`` or ``"formula"``.
    """

    def __init__(
        self,
        ocr_service: TextOCRService | None = None,
        formula_service: FormulaRecognitionService | None = None,
    ) -> None:
        self._ocr = ocr_service or TextOCRService()
        self._formula = formula_service or FormulaRecognitionService()

    def process(self, image_bytes: bytes) -> Tuple[List[Tuple[str, str]], int, int]:
        """Process raw image bytes and return content blocks.

        Returns
        -------
        blocks:
            List of ``(block_type, content)`` tuples.
        text_count:
            Number of text blocks found.
        formula_count:
            Number of formula blocks found.
        """
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # 1. Run text OCR on the whole image
        ocr_results = self._ocr.recognise(image)

        blocks: List[Tuple[str, str]] = []
        text_count = 0
        formula_count = 0

        if not ocr_results:
            # No text detected – try treating the whole image as a formula
            logger.info("No text detected; attempting full-image formula recognition.")
            latex = self._formula.recognise(image)
            if latex:
                blocks.append((FORMULA_BLOCK, latex))
                formula_count += 1
            else:
                logger.warning("No content could be recognised from image.")
            return blocks, text_count, formula_count

        for bbox, text, _confidence in ocr_results:
            if _is_likely_formula(text):
                # Crop to the bounding box of this specific block so pix2tex
                # processes only the relevant region rather than the full image.
                region = _crop_to_bbox(image, bbox)
                latex = self._formula.recognise(region)
                if latex:
                    blocks.append((FORMULA_BLOCK, latex))
                    formula_count += 1
                else:
                    # Fall back to plain text
                    blocks.append((TEXT_BLOCK, text))
                    text_count += 1
            else:
                blocks.append((TEXT_BLOCK, text))
                text_count += 1

        logger.info(
            "Image processed: %d text block(s), %d formula block(s).",
            text_count,
            formula_count,
        )
        return blocks, text_count, formula_count
