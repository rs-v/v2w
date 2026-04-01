"""Word document generation service."""

from __future__ import annotations

import io
import logging
import tempfile
from typing import List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

# Content block types
TEXT_BLOCK = "text"
FORMULA_BLOCK = "formula"


def _render_latex_to_image(latex: str, dpi: int = 150) -> Optional[bytes]:
    """Render a LaTeX formula string to a PNG image using Matplotlib.

    Returns PNG bytes, or ``None`` if rendering fails.
    """
    try:
        import matplotlib  # noqa: PLC0415

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415

        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f"${latex}$", fontsize=14)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.1)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        logger.exception("Failed to render LaTeX '%s' to image.", latex)
        return None


class WordGeneratorService:
    """Assembles text and formula blocks into a .docx document."""

    def generate(
        self,
        blocks: List[Tuple[str, str]],
        title: Optional[str] = None,
    ) -> bytes:
        """Build a Word document from *blocks* and return the raw bytes.

        Parameters
        ----------
        blocks:
            A list of ``(block_type, content)`` tuples where *block_type* is
            either ``"text"`` or ``"formula"``, and *content* is the
            recognised text or LaTeX string.
        title:
            Optional document title inserted as a heading.

        Returns
        -------
        Raw ``.docx`` bytes.
        """
        from docx import Document  # noqa: PLC0415
        from docx.shared import Inches, Pt  # noqa: PLC0415

        doc = Document()

        if title:
            heading = doc.add_heading(title, level=1)
            heading.runs[0].font.size = Pt(16)

        for block_type, content in blocks:
            if block_type == TEXT_BLOCK:
                doc.add_paragraph(content)
            elif block_type == FORMULA_BLOCK:
                png_bytes = _render_latex_to_image(content)
                if png_bytes:
                    img_stream = io.BytesIO(png_bytes)
                    doc.add_picture(img_stream, width=Inches(4))
                    doc.add_paragraph(f"[LaTeX: {content}]").italic = True
                else:
                    doc.add_paragraph(f"[Formula: {content}]")

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()
