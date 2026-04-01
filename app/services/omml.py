"""Convert LaTeX to OMML (Office Math Markup Language) for Word equations.

Pipeline:
  LaTeX  →  MathML  (via latex2mathml)
         →  OMML    (via recursive Python converter using lxml)

The resulting ``<m:oMath>`` element can be inserted directly into a
python-docx paragraph to produce an editable equation that is fully
compatible with Word's built-in equation editor and MathType.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from lxml import etree

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Namespace constants
# ──────────────────────────────────────────────

MML_NS = "http://www.w3.org/1998/Math/MathML"
OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

# nsmap used when creating root OMML elements so that lxml uses "m:" prefix
_NSMAP = {"m": OMML_NS}


def _omml(tag: str) -> str:
    """Return the Clark-notation OMML tag name for *tag*."""
    return f"{{{OMML_NS}}}{tag}"


def _attr(name: str) -> str:
    """Return the Clark-notation OMML attribute name for *name*."""
    return f"{{{OMML_NS}}}{name}"


# ──────────────────────────────────────────────
# N-ary operator set
# ──────────────────────────────────────────────

# Operators that become <m:nary> elements in OMML (with their limits as body).
_NARY_OPS: frozenset[str] = frozenset(
    [
        "∑",  # U+2211  summation
        "∏",  # U+220F  product
        "∐",  # U+2210  coproduct
        "∫",  # U+222B  integral
        "∬",  # U+222C  double integral
        "∭",  # U+222D  triple integral
        "∮",  # U+222E  contour integral
        "∯",  # U+222F  surface integral
        "∰",  # U+2230  volume integral
        "⋃",  # U+22C3  big union
        "⋂",  # U+22C2  big intersection
        "⋁",  # U+22C1  big logical-or
        "⋀",  # U+22C0  big logical-and
        "⊕",  # U+2295  circled-plus (direct sum)
        "⊗",  # U+2297  circled-times (tensor product)
        "⨁",  # U+2A01  n-ary circled plus
        "⨂",  # U+2A02  n-ary circled times
        "⨀",  # U+2A00  n-ary circled dot
    ]
)

# Characters that map to an overline bar when used as the accent in <mover>
_OVERLINE_CHARS: frozenset[str] = frozenset(["―", "‾", "¯", "‐"])


# ──────────────────────────────────────────────
# Element builders
# ──────────────────────────────────────────────


def _elem(tag: str) -> etree._Element:
    """Create an OMML element with the m: namespace map."""
    return etree.Element(_omml(tag), nsmap=_NSMAP)


def _sub(parent: etree._Element, tag: str) -> etree._Element:
    return etree.SubElement(parent, _omml(tag))


def _make_run(text: str, style: Optional[str] = None) -> etree._Element:
    """Return ``<m:r>[<m:rPr><m:sty m:val="…"/>]<m:t>text</m:t></m:r>``."""
    r = _elem("r")
    if style is not None:
        rPr = _sub(r, "rPr")
        sty = _sub(rPr, "sty")
        sty.set(_attr("val"), style)
    t = _sub(r, "t")
    t.text = text
    # Preserve leading/trailing spaces so Word renders them correctly
    if text and (text[0] == " " or text[-1] == " "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


def _get_text(el: etree._Element) -> str:
    """Return all text content of *el* (and its descendants) concatenated."""
    return "".join(el.itertext())


# ──────────────────────────────────────────────
# Conversion helpers
# ──────────────────────────────────────────────


def _as_omml_list(el: etree._Element) -> List[etree._Element]:
    """Convert *el* itself to OMML and return the result as a flat list.

    This is the correct function to use when you need the OMML representation
    of a specific MathML element (e.g., the base of ``<msup>``).  Unlike
    ``_convert_mrow_children``, it converts the *element itself*, not its
    children, so it works correctly for leaf nodes such as ``<mi>`` or ``<mn>``.
    """
    result = _convert_element(el)
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


# ──────────────────────────────────────────────
# N-ary helper
# ──────────────────────────────────────────────


def _make_nary(
    op: str,
    sub_el: Optional[etree._Element],
    sup_el: Optional[etree._Element],
    body_els: List[etree._Element],
) -> etree._Element:
    """Build ``<m:nary>`` for an N-ary operator with optional limits and body."""
    nary = _elem("nary")
    naryPr = _sub(nary, "naryPr")
    chr_el = _sub(naryPr, "chr")
    chr_el.set(_attr("val"), op)
    limLoc = _sub(naryPr, "limLoc")
    limLoc.set(_attr("val"), "subSup")

    sub_omml = _sub(nary, "sub")
    if sub_el is not None:
        for c in _as_omml_list(sub_el):
            sub_omml.append(c)

    sup_omml = _sub(nary, "sup")
    if sup_el is not None:
        for c in _as_omml_list(sup_el):
            sup_omml.append(c)

    e = _sub(nary, "e")
    for body_el in body_els:
        converted = _convert_element(body_el)
        if converted is None:
            continue
        if isinstance(converted, list):
            for c in converted:
                e.append(c)
        else:
            e.append(converted)

    return nary


# ──────────────────────────────────────────────
# Core conversion
# ──────────────────────────────────────────────


def _convert_mrow_children(
    children: List[etree._Element],
) -> List[etree._Element]:
    """Convert a list of MathML sibling elements to OMML.

    N-ary operators (∑, ∏, ∫ …) are handled contextually: when such an
    operator is encountered (either bare or as the base of ``msubsup`` /
    ``munderover``), all remaining siblings are collected and used as the
    operator's body inside ``<m:nary>``.
    """
    result: List[etree._Element] = []
    i = 0
    while i < len(children):
        el = children[i]
        tag = etree.QName(el.tag).localname
        el_children = list(el)

        # ── N-ary via msubsup / munderover ──────────────────────────────────
        if tag in ("msubsup", "munderover") and el_children:
            base_text = _get_text(el_children[0]).strip()
            if base_text in _NARY_OPS:
                result.append(
                    _make_nary(
                        base_text,
                        el_children[1] if len(el_children) > 1 else None,
                        el_children[2] if len(el_children) > 2 else None,
                        children[i + 1 :],
                    )
                )
                break  # remaining siblings consumed by the nary body

        # ── N-ary via msub / munder ─────────────────────────────────────────
        elif tag in ("msub", "munder") and el_children:
            base_text = _get_text(el_children[0]).strip()
            if base_text in _NARY_OPS:
                result.append(
                    _make_nary(
                        base_text,
                        el_children[1] if len(el_children) > 1 else None,
                        None,
                        children[i + 1 :],
                    )
                )
                break

        # ── Bare N-ary operator (no sub/superscript) ────────────────────────
        elif tag == "mo" and (el.text or "").strip() in _NARY_OPS:
            result.append(
                _make_nary((el.text or "").strip(), None, None, children[i + 1 :])
            )
            break

        # ── Ordinary element ────────────────────────────────────────────────
        else:
            converted = _convert_element(el)
            if converted is None:
                pass
            elif isinstance(converted, list):
                result.extend(converted)
            else:
                result.append(converted)

        i += 1
    return result


def _convert_element(
    el: etree._Element,
) -> "etree._Element | List[etree._Element] | None":
    """Recursively convert a single MathML element to its OMML equivalent."""
    tag = etree.QName(el.tag).localname
    el_children = list(el)

    # ── <math> root ─────────────────────────────────────────────────────────
    if tag == "math":
        oMath = _elem("oMath")
        for c in _convert_mrow_children(el_children):
            oMath.append(c)
        return oMath

    # ── Transparent grouping ─────────────────────────────────────────────────
    if tag in ("mrow", "mstyle", "mpadded", "mphantom", "menclose"):
        return _convert_mrow_children(el_children)

    # ── Leaf tokens ──────────────────────────────────────────────────────────
    if tag == "mi":
        text = el.text or ""
        # Single-char identifiers → italic (math default);
        # multi-char identifiers (sin, cos, …) → upright
        style: Optional[str] = None if len(text) == 1 else "p"
        return _make_run(text, style)

    if tag == "mn":
        return _make_run(el.text or "", "p")

    if tag == "mo":
        return _make_run(el.text or "", "p")

    if tag == "mtext":
        r = _elem("r")
        rPr = _sub(r, "rPr")
        sty = _sub(rPr, "sty")
        sty.set(_attr("val"), "p")
        t = _sub(r, "t")
        t.text = el.text or ""
        return r

    if tag == "mspace":
        return _make_run("\u2009", "p")  # thin space

    # ── Fraction ─────────────────────────────────────────────────────────────
    if tag == "mfrac":
        f = _elem("f")
        num = _sub(f, "num")
        den = _sub(f, "den")
        if el_children:
            for c in _as_omml_list(el_children[0]):
                num.append(c)
        if len(el_children) >= 2:
            for c in _as_omml_list(el_children[1]):
                den.append(c)
        return f

    # ── Superscript ──────────────────────────────────────────────────────────
    if tag == "msup":
        sSup = _elem("sSup")
        e = _sub(sSup, "e")
        sup = _sub(sSup, "sup")
        if el_children:
            for c in _as_omml_list(el_children[0]):
                e.append(c)
        if len(el_children) >= 2:
            for c in _as_omml_list(el_children[1]):
                sup.append(c)
        return sSup

    # ── Subscript ────────────────────────────────────────────────────────────
    if tag == "msub":
        sSub = _elem("sSub")
        e = _sub(sSub, "e")
        sub = _sub(sSub, "sub")
        if el_children:
            for c in _as_omml_list(el_children[0]):
                e.append(c)
        if len(el_children) >= 2:
            for c in _as_omml_list(el_children[1]):
                sub.append(c)
        return sSub

    # ── Sub + superscript ────────────────────────────────────────────────────
    if tag == "msubsup":
        # N-ary case already intercepted in _convert_mrow_children
        sSubSup = _elem("sSubSup")
        e = _sub(sSubSup, "e")
        sub = _sub(sSubSup, "sub")
        sup = _sub(sSubSup, "sup")
        if el_children:
            for c in _as_omml_list(el_children[0]):
                e.append(c)
        if len(el_children) >= 2:
            for c in _as_omml_list(el_children[1]):
                sub.append(c)
        if len(el_children) >= 3:
            for c in _as_omml_list(el_children[2]):
                sup.append(c)
        return sSubSup

    # ── Under + over ─────────────────────────────────────────────────────────
    if tag == "munderover":
        # N-ary case already intercepted; fall back to limLow inside limUpp
        limLow = _elem("limLow")
        e_low = _sub(limLow, "e")
        lim_low = _sub(limLow, "lim")
        if el_children:
            for c in _as_omml_list(el_children[0]):
                e_low.append(c)
        if len(el_children) >= 2:
            for c in _as_omml_list(el_children[1]):
                lim_low.append(c)

        limUpp = _elem("limUpp")
        e_upp = _sub(limUpp, "e")
        lim_upp = _sub(limUpp, "lim")
        e_upp.append(limLow)
        if len(el_children) >= 3:
            for c in _as_omml_list(el_children[2]):
                lim_upp.append(c)
        return limUpp

    # ── Under ────────────────────────────────────────────────────────────────
    if tag == "munder":
        # N-ary case already intercepted
        limLow = _elem("limLow")
        e = _sub(limLow, "e")
        lim = _sub(limLow, "lim")
        if el_children:
            for c in _as_omml_list(el_children[0]):
                e.append(c)
        if len(el_children) >= 2:
            for c in _as_omml_list(el_children[1]):
                lim.append(c)
        return limLow

    # ── Over (accent / overline) ─────────────────────────────────────────────
    if tag == "mover":
        over_text = _get_text(el_children[1]).strip() if len(el_children) >= 2 else ""
        if over_text in _OVERLINE_CHARS:
            bar = _elem("bar")
            barPr = _sub(bar, "barPr")
            pos = _sub(barPr, "pos")
            pos.set(_attr("val"), "top")
            e = _sub(bar, "e")
            if el_children:
                for c in _as_omml_list(el_children[0]):
                    e.append(c)
            return bar

        acc = _elem("acc")
        accPr = _sub(acc, "accPr")
        if over_text:
            chr_el = _sub(accPr, "chr")
            chr_el.set(_attr("val"), over_text)
        e = _sub(acc, "e")
        if el_children:
            for c in _as_omml_list(el_children[0]):
                e.append(c)
        return acc

    # ── Square root ──────────────────────────────────────────────────────────
    if tag == "msqrt":
        rad = _elem("rad")
        radPr = _sub(rad, "radPr")
        degHide = _sub(radPr, "degHide")
        degHide.set(_attr("val"), "1")
        _sub(rad, "deg")  # empty degree element required by OMML schema
        e = _sub(rad, "e")
        for c in _convert_mrow_children(el_children):
            e.append(c)
        return rad

    # ── N-th root ────────────────────────────────────────────────────────────
    if tag == "mroot":
        rad = _elem("rad")
        deg = _sub(rad, "deg")
        e = _sub(rad, "e")
        # mroot child order: [base, index]
        if el_children:
            for c in _as_omml_list(el_children[0]):
                e.append(c)
        if len(el_children) >= 2:
            for c in _as_omml_list(el_children[1]):
                deg.append(c)
        return rad

    # ── Matrix ───────────────────────────────────────────────────────────────
    if tag == "mtable":
        m = _elem("m")
        for row in el_children:
            if etree.QName(row.tag).localname == "mtr":
                mr = _sub(m, "mr")
                for cell in row:
                    if etree.QName(cell.tag).localname == "mtd":
                        cell_e = _sub(mr, "e")
                        for c in _convert_mrow_children(list(cell)):
                            cell_e.append(c)
        return m

    # ── Fallback ─────────────────────────────────────────────────────────────
    text = "".join(el.itertext())
    if text.strip():
        return _make_run(text.strip())
    return _convert_mrow_children(el_children) if el_children else None


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────


def latex_to_omml(latex: str) -> Optional[etree._Element]:
    """Convert a LaTeX math string to an OMML ``<m:oMath>`` element.

    Parameters
    ----------
    latex:
        LaTeX math string **without** surrounding ``$`` signs.

    Returns
    -------
    An ``<m:oMath>`` lxml element ready to embed in a Word paragraph,
    or ``None`` if conversion fails at any stage.
    """
    try:
        import latex2mathml.converter as conv  # noqa: PLC0415

        mml_str = conv.convert(latex)
        mml_root = etree.fromstring(mml_str.encode())
    except Exception:
        logger.exception("latex2mathml conversion failed for: %s", latex)
        return None

    try:
        result = _convert_element(mml_root)
    except Exception:
        logger.exception("MathML→OMML conversion failed for: %s", latex)
        return None

    if result is None:
        return None

    # _convert_element("math") always returns a single <m:oMath> element
    if isinstance(result, list):
        oMath = _elem("oMath")
        for c in result:
            oMath.append(c)
        return oMath

    return result
