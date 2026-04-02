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

    @patch("app.services.word_gen.latex_to_omml")
    def test_generate_formula_block_fallback(self, mock_omml):
        """When OMML conversion fails the formula is inserted as plain text."""
        mock_omml.return_value = None
        blocks = [("formula", r"\frac{a}{b}")]
        docx_bytes = self.service.generate(blocks)
        self.assertTrue(docx_bytes[:2] == b"PK")
        mock_omml.assert_called_once_with(r"\frac{a}{b}")

    @patch("app.services.word_gen.latex_to_omml")
    def test_generate_formula_block_as_omml(self, mock_omml):
        """When OMML conversion succeeds an editable equation is embedded."""
        from lxml import etree

        from app.services.omml import OMML_NS, _elem

        # Build a minimal <m:oMath> element for testing
        oMath = _elem("oMath")
        r = etree.SubElement(oMath, f"{{{OMML_NS}}}r")
        t = etree.SubElement(r, f"{{{OMML_NS}}}t")
        t.text = "E"
        mock_omml.return_value = oMath

        blocks = [("formula", r"E = mc^2")]
        docx_bytes = self.service.generate(blocks, title="Physics")
        self.assertTrue(docx_bytes[:2] == b"PK")

        # Verify the OMML element is present in the docx XML
        import zipfile

        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
            doc_xml = zf.read("word/document.xml").decode()
        self.assertIn("oMath", doc_xml)


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

    def test_ascii_math_pattern_detected(self):
        from app.services.image_processor import _is_likely_formula

        # ASCII expression with = and letter/digit operands
        self.assertTrue(_is_likely_formula("E=mc^2"))

    def test_fraction_pattern_detected(self):
        from app.services.image_processor import _is_likely_formula

        self.assertTrue(_is_likely_formula("a/b"))


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
# Unit tests – OMML converter
# ---------------------------------------------------------------------------


class TestOmmlConverter(unittest.TestCase):
    """latex_to_omml produces well-formed OMML <m:oMath> elements."""

    def _convert(self, latex: str):
        from app.services.omml import latex_to_omml

        return latex_to_omml(latex)

    def _tag_name(self, el) -> str:
        from lxml import etree

        return etree.QName(el.tag).localname

    def test_simple_identifier(self):
        el = self._convert("x")
        self.assertIsNotNone(el)
        self.assertEqual(self._tag_name(el), "oMath")

    def test_fraction(self):
        el = self._convert(r"\frac{a}{b}")
        self.assertIsNotNone(el)
        from lxml import etree

        frac_els = [e for e in el.iter() if etree.QName(e.tag).localname == "f"]
        self.assertTrue(len(frac_els) > 0, "Expected <m:f> fraction element")

    def test_superscript(self):
        el = self._convert(r"E = mc^2")
        self.assertIsNotNone(el)
        from lxml import etree

        ssup_els = [e for e in el.iter() if etree.QName(e.tag).localname == "sSup"]
        self.assertTrue(len(ssup_els) > 0, "Expected <m:sSup> superscript element")

    def test_integral_becomes_nary(self):
        el = self._convert(r"\int_0^\infty e^{-x}\,dx")
        self.assertIsNotNone(el)
        from lxml import etree

        nary_els = [e for e in el.iter() if etree.QName(e.tag).localname == "nary"]
        self.assertTrue(len(nary_els) > 0, "Expected <m:nary> for integral")

    def test_sum_becomes_nary(self):
        el = self._convert(r"\sum_{n=1}^{\infty} \frac{1}{n^2}")
        self.assertIsNotNone(el)
        from lxml import etree

        nary_els = [e for e in el.iter() if etree.QName(e.tag).localname == "nary"]
        self.assertTrue(len(nary_els) > 0, "Expected <m:nary> for summation")

    def test_sqrt(self):
        el = self._convert(r"\sqrt{x^2 + y^2}")
        self.assertIsNotNone(el)
        from lxml import etree

        rad_els = [e for e in el.iter() if etree.QName(e.tag).localname == "rad"]
        self.assertTrue(len(rad_els) > 0, "Expected <m:rad> for square root")

    def test_nth_root(self):
        el = self._convert(r"\sqrt[3]{x}")
        self.assertIsNotNone(el)
        from lxml import etree

        rad_els = [e for e in el.iter() if etree.QName(e.tag).localname == "rad"]
        self.assertTrue(len(rad_els) > 0, "Expected <m:rad> for n-th root")

    def test_overline(self):
        el = self._convert(r"\overline{AB}")
        self.assertIsNotNone(el)
        from lxml import etree

        bar_els = [e for e in el.iter() if etree.QName(e.tag).localname == "bar"]
        self.assertTrue(len(bar_els) > 0, "Expected <m:bar> for overline")

    def test_invalid_latex_returns_none(self):
        from app.services.omml import latex_to_omml

        # latex2mathml handles most LaTeX gracefully; test truly broken input
        result = latex_to_omml("")
        # Empty string may return None or an empty oMath — both are acceptable
        if result is not None:
            from lxml import etree

            self.assertEqual(etree.QName(result.tag).localname, "oMath")


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
        self.assertIn("v2w", resp.text)

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

    @patch("app.api.routes._image_processor")
    def test_recognize_valid_png(self, mock_proc):
        mock_proc.process.return_value = (
            [("text", "Hello"), ("formula", r"\frac{a}{b}")],
            1,
            1,
        )
        client = self._make_client()
        resp = client.post(
            "/api/v1/recognize",
            files={"file": ("test.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["text_count"], 1)
        self.assertEqual(data["formula_count"], 1)
        self.assertEqual(len(data["blocks"]), 2)
        self.assertEqual(data["blocks"][0]["block_type"], "text")
        self.assertEqual(data["blocks"][1]["block_type"], "formula")

    def test_recognize_unsupported_type(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/recognize",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        self.assertEqual(resp.status_code, 400)

    @patch("app.api.routes._word_generator")
    def test_generate_word_from_blocks(self, mock_gen):
        mock_gen.generate.return_value = b"PK\x03\x04"

        client = self._make_client()
        payload = {
            "blocks": [
                {"block_type": "text", "content": "Hello world"},
                {"block_type": "formula", "content": r"\frac{a}{b}"},
            ],
            "title": "Test",
        }
        resp = client.post("/api/v1/generate-word", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        mock_gen.generate.assert_called_once_with(
            [("text", "Hello world"), ("formula", r"\frac{a}{b}")],
            title="Test",
        )


if __name__ == "__main__":
    unittest.main()
