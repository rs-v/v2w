"""Tests for the v2w cloud service API.

All tests use dependency injection / mocking so that heavy ML models
(EasyOCR, pix2tex) are not required during CI runs.
"""

from __future__ import annotations

import io
import unittest
from typing import List, Tuple
from unittest.mock import MagicMock, patch

from PIL import Image

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes(width: int = 100, height: int = 50, color: str = "white") -> bytes:
    """Return a minimal in-memory PNG image as bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unit tests – services
# ---------------------------------------------------------------------------


class TestWordGeneratorService(unittest.TestCase):
    """Word generator can build a .docx from text and formula blocks."""

    def setUp(self):
        from app.services.word_gen import WordGeneratorService

        self.service = WordGeneratorService()

    def test_generate_text_blocks(self):
        blocks: List[Tuple[str, str]] = [
            ("text", "Hello world"),
            ("text", "Second paragraph"),
        ]
        docx_bytes = self.service.generate(blocks, title="Test Doc")
        # A valid .docx starts with the ZIP PK header
        self.assertTrue(docx_bytes[:2] == b"PK")

    def test_generate_empty_blocks(self):
        docx_bytes = self.service.generate([], title="Empty")
        self.assertTrue(docx_bytes[:2] == b"PK")

    @patch("app.services.word_gen._render_latex_to_image")
    def test_generate_formula_block_fallback(self, mock_render):
        """When LaTeX rendering fails the formula is inserted as plain text."""
        mock_render.return_value = None  # rendering failure
        blocks = [("formula", r"\frac{a}{b}")]
        docx_bytes = self.service.generate(blocks)
        self.assertTrue(docx_bytes[:2] == b"PK")
        mock_render.assert_called_once_with(r"\frac{a}{b}")

    @patch("app.services.word_gen._render_latex_to_image")
    def test_generate_formula_block_with_image(self, mock_render):
        """When LaTeX rendering succeeds a picture is embedded."""
        mock_render.return_value = _make_png_bytes()
        blocks = [("formula", r"E = mc^2")]
        docx_bytes = self.service.generate(blocks, title="Physics")
        self.assertTrue(docx_bytes[:2] == b"PK")


class TestImageProcessorHeuristic(unittest.TestCase):
    """_is_likely_formula correctly classifies strings."""

    def test_plain_text_not_formula(self):
        from app.services.image_processor import _is_likely_formula

        self.assertFalse(_is_likely_formula("Hello, world!"))

    def test_math_symbols_detected(self):
        from app.services.image_processor import _is_likely_formula

        # String is dominated by Greek / math characters
        self.assertTrue(_is_likely_formula("αβγδεζηθ"))

    def test_empty_string_not_formula(self):
        from app.services.image_processor import _is_likely_formula

        self.assertFalse(_is_likely_formula(""))


class TestImageProcessor(unittest.TestCase):
    """ImageProcessor correctly orchestrates OCR and formula services."""

    def _make_processor(self, ocr_results, formula_result=None):
        from app.services.image_processor import ImageProcessor

        mock_ocr = MagicMock()
        mock_ocr.recognise.return_value = ocr_results

        mock_formula = MagicMock()
        mock_formula.recognise.return_value = formula_result

        return ImageProcessor(ocr_service=mock_ocr, formula_service=mock_formula)

    # Helper: a dummy bounding box (four [x, y] corners)
    _BBOX = [[0, 0], [100, 0], [100, 20], [0, 20]]

    def test_plain_text_image(self):
        processor = self._make_processor(ocr_results=[(self._BBOX, "Hello world", 0.99)])
        blocks, text_count, formula_count = processor.process(_make_png_bytes())
        self.assertEqual(text_count, 1)
        self.assertEqual(formula_count, 0)
        self.assertEqual(blocks[0], ("text", "Hello world"))

    def test_no_text_falls_back_to_formula(self):
        processor = self._make_processor(
            ocr_results=[],
            formula_result=r"\int_0^\infty e^{-x}\,dx",
        )
        blocks, text_count, formula_count = processor.process(_make_png_bytes())
        self.assertEqual(formula_count, 1)
        self.assertEqual(text_count, 0)

    def test_no_text_no_formula(self):
        processor = self._make_processor(ocr_results=[], formula_result=None)
        blocks, text_count, formula_count = processor.process(_make_png_bytes())
        self.assertEqual(len(blocks), 0)

    def test_math_block_routed_to_formula_service(self):
        # "αβγδεζηθ" is math-heavy, should trigger formula recognition
        processor = self._make_processor(
            ocr_results=[(self._BBOX, "αβγδεζηθ", 0.75)],
            formula_result=r"\alpha\beta\gamma",
        )
        blocks, text_count, formula_count = processor.process(_make_png_bytes())
        self.assertEqual(formula_count, 1)
        self.assertEqual(text_count, 0)


# ---------------------------------------------------------------------------
# Unit tests – image cropping helper
# ---------------------------------------------------------------------------


class TestCropToBbox(unittest.TestCase):
    """_crop_to_bbox returns an image subset without crashing."""

    def test_basic_crop(self):
        from app.services.image_processor import _crop_to_bbox

        img = Image.new("RGB", (200, 200), color="white")
        bbox = [[10, 10], [100, 10], [100, 50], [10, 50]]
        cropped = _crop_to_bbox(img, bbox)
        # Result should be smaller than the original (with padding)
        self.assertLess(cropped.width, 200)
        self.assertLess(cropped.height, 200)

    def test_crop_clamps_to_image_bounds(self):
        from app.services.image_processor import _crop_to_bbox

        img = Image.new("RGB", (50, 50), color="white")
        # bbox extends beyond image boundaries
        bbox = [[0, 0], [200, 0], [200, 200], [0, 200]]
        cropped = _crop_to_bbox(img, bbox)
        self.assertLessEqual(cropped.width, 50)
        self.assertLessEqual(cropped.height, 50)


class TestAPIRoutes(unittest.TestCase):
    """FastAPI endpoints respond correctly with mocked services."""

    def _make_client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    def test_root_redirect(self):
        client = self._make_client()
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("v2w", resp.json()["message"])

    def test_health_endpoint(self):
        client = self._make_client()
        resp = client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("ocr", data["services"])
        self.assertIn("formula", data["services"])

    @patch("app.api.routes._image_processor")
    @patch("app.api.routes._word_generator")
    def test_convert_valid_png(self, mock_gen, mock_proc):
        mock_proc.process.return_value = ([("text", "Hello")], 1, 0)
        mock_gen.generate.return_value = b"PK\x03\x04"  # fake docx bytes

        client = self._make_client()
        png_bytes = _make_png_bytes()
        resp = client.post(
            "/api/v1/convert",
            files={"file": ("test.png", png_bytes, "image/png")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_convert_unsupported_type(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/convert",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        self.assertEqual(resp.status_code, 400)

    def test_convert_empty_file(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/convert",
            files={"file": ("empty.png", b"", "image/png")},
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
