"""Tests for the v2w formula recognition service.

All API-route tests use FastAPI dependency overrides so that the pix2tex model
is never actually loaded during CI runs.
"""

from __future__ import annotations

import io
import unittest
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
# Unit tests – FormulaRecognitionService
# ---------------------------------------------------------------------------


class TestFormulaRecognitionService(unittest.TestCase):
    """FormulaRecognitionService delegates to pix2tex LatexOCR."""

    @patch("app.services.formula.LatexOCR", create=True)
    def test_recognise_calls_model(self, MockLatexOCR):
        # Patch inside the module's namespace after import
        import app.services.formula as fm

        mock_model = MagicMock(return_value=r"\frac{a}{b}")
        with patch.object(fm.FormulaRecognitionService, "_load_model", return_value=mock_model):
            service = fm.FormulaRecognitionService()
            result = service.recognise(Image.new("RGB", (50, 50)))

        self.assertEqual(result, r"\frac{a}{b}")

    def test_recognise_returns_none_on_failure(self):
        import app.services.formula as fm

        service = fm.FormulaRecognitionService()
        with patch.object(service, "_load_model", side_effect=RuntimeError("no model")):
            result = service.recognise(Image.new("RGB", (50, 50)))

        self.assertIsNone(result)

    def test_recognise_from_bytes(self):
        import app.services.formula as fm

        service = fm.FormulaRecognitionService()
        mock_model = MagicMock(return_value=r"x^2")
        with patch.object(service, "_load_model", return_value=mock_model):
            result = service.recognise_from_bytes(_make_png_bytes())

        self.assertEqual(result, r"x^2")


# ---------------------------------------------------------------------------
# Unit tests – API routes
# ---------------------------------------------------------------------------


class TestAPIRoutes(unittest.TestCase):
    """FastAPI endpoints respond correctly with mocked formula service."""

    def setUp(self):
        from unittest.mock import MagicMock

        from app.api.routes import get_formula_service
        from app.main import app

        self.app = app
        self.app.dependency_overrides.clear()
        # Provide a default no-op service so that tests which only exercise
        # request validation (and therefore never call the model) don't fail
        # because the lifespan hasn't run and app.state is unpopulated.
        self.app.dependency_overrides[get_formula_service] = lambda: MagicMock()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _make_client(self):
        from fastapi.testclient import TestClient

        return TestClient(self.app)

    def _override_formula_service(self, latex_result=None):
        """Register a dependency override that returns a mock formula service."""
        from app.api.routes import get_formula_service

        mock_service = MagicMock()
        mock_service.recognise_from_bytes.return_value = latex_result
        self.app.dependency_overrides[get_formula_service] = lambda: mock_service
        return mock_service

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def test_health_endpoint(self):
        client = self._make_client()
        resp = client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("formula", data["services"])
        self.assertNotIn("ocr", data["services"])
        self.assertNotIn("word", data["services"])

    # ------------------------------------------------------------------
    # Root
    # ------------------------------------------------------------------

    def test_root_serves_html(self):
        client = self._make_client()
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("v2w", resp.text)

    # ------------------------------------------------------------------
    # /predict
    # ------------------------------------------------------------------

    def test_predict_returns_latex(self):
        self._override_formula_service(latex_result=r"\frac{a}{b}")
        client = self._make_client()
        resp = client.post(
            "/api/v1/predict",
            files={"file": ("formula.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["latex"], r"\frac{a}{b}")
        self.assertIn("message", data)

    def test_predict_no_result(self):
        self._override_formula_service(latex_result=None)
        client = self._make_client()
        resp = client.post(
            "/api/v1/predict",
            files={"file": ("formula.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["latex"])

    def test_predict_unsupported_type(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/predict",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        self.assertEqual(resp.status_code, 400)

    def test_predict_empty_file(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/predict",
            files={"file": ("empty.png", b"", "image/png")},
        )
        self.assertEqual(resp.status_code, 400)

    def test_predict_service_error_returns_500(self):
        from app.api.routes import get_formula_service

        mock_service = MagicMock()
        mock_service.recognise_from_bytes.side_effect = RuntimeError("model exploded")
        self.app.dependency_overrides[get_formula_service] = lambda: mock_service

        client = self._make_client()
        resp = client.post(
            "/api/v1/predict",
            files={"file": ("formula.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(resp.status_code, 500)

    # ------------------------------------------------------------------
    # Removed endpoints must no longer exist
    # ------------------------------------------------------------------

    def test_convert_endpoint_gone(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/convert",
            files={"file": ("test.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(resp.status_code, 404)

    def test_recognize_endpoint_gone(self):
        client = self._make_client()
        resp = client.post(
            "/api/v1/recognize",
            files={"file": ("test.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(resp.status_code, 404)

    def test_generate_word_endpoint_gone(self):
        client = self._make_client()
        resp = client.post("/api/v1/generate-word", json={"blocks": []})
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()

