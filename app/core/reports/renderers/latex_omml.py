"""
LaTeX → OMML Converter — UAV-CD-APP
======================================
Convert LaTeX math source into Office Math Markup Language (OMML) elements
that Word renders as real, editable math objects.

Pipeline:
    LaTeX string
        ↓  latex2mathml.converter.convert()       (PyPI dep)
    MathML XML
        ↓  this module's MathML→OMML recursive emitter
    <m:oMath> lxml element

The OMML output uses real structural elements — <m:f> for fractions,
<m:rad> for square roots, <m:sSub>/<m:sSup>/<m:sSubSup> for sub/superscripts,
<m:d> for delimiters — so Word's equation editor sees proper math, not just
italic text.

Why no external XSLT?
  Microsoft's MML2OMML.xsl ships with Office and is not redistributable.
  Open-source XSL ports exist but add complexity (~1k lines of XSL plus an
  XSLT engine on the critical path). A small recursive Python transform
  covers every construct the report sections actually use.
"""

from __future__ import annotations

from typing import Iterable

from lxml import etree

import latex2mathml.converter

_OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_MML_NS = "http://www.w3.org/1998/Math/MathML"
_M = f"{{{_OMML_NS}}}"


# ── Public API ──────────────────────────────────────────────────────────────


def latex_to_omml(latex_src: str) -> etree._Element:
    """Convert a LaTeX math string into an ``<m:oMath>`` lxml element.

    The returned element can be appended directly to a python-docx
    paragraph's ``<w:p>`` to produce a real Word equation object.
    """
    mml_str = latex2mathml.converter.convert(latex_src)
    mml_root = etree.fromstring(mml_str.encode("utf-8"))
    omath = etree.Element(f"{_M}oMath")
    for child in mml_root:
        omath.extend(_convert(child))
    return omath


# ── Internal recursive transform ────────────────────────────────────────────


def _local(tag: str) -> str:
    """Strip namespace from an lxml tag — '{http://...}mfrac' → 'mfrac'."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _r(text: str, *, normal: bool = False) -> etree._Element:
    """Build a math run ``<m:r><m:t>text</m:t></m:r>``.

    If ``normal=True``, the run is styled as upright (operator/text) via
    ``<m:rPr><m:sty m:val="p"/></m:rPr>``.
    """
    r = etree.Element(f"{_M}r")
    if normal:
        rpr = etree.SubElement(r, f"{_M}rPr")
        sty = etree.SubElement(rpr, f"{_M}sty")
        sty.set(f"{_M}val", "p")
    t = etree.SubElement(r, f"{_M}t")
    t.text = text
    return r


def _wrap(tag: str, children: Iterable[etree._Element]) -> etree._Element:
    """Wrap an iterable of OMML elements in a single ``<m:tag>`` parent."""
    el = etree.Element(f"{_M}{tag}")
    for c in children:
        el.append(c)
    return el


def _convert(node: etree._Element) -> list[etree._Element]:
    """Recursively transform a MathML node to a list of OMML elements.

    Returns a *list* because some MathML constructs (notably ``<mrow>`` and
    ``<mstyle>``) have no direct OMML wrapper — their children are inlined
    into the containing slot (``<m:e>``, ``<m:num>``, ``<m:den>``, …).
    """
    tag = _local(node.tag)
    text = (node.text or "").strip()

    # Atomic content nodes
    if tag in ("mi", "mn"):
        return [_r(text)]
    if tag == "mo":
        # Operators / punctuation: render upright (non-italic) by convention
        return [_r(text, normal=True)] if text else []
    if tag == "mtext":
        return [_r(text, normal=True)]
    if tag == "mspace":
        return []

    # Row-like nodes: inline children into the parent slot
    if tag in ("mrow", "mstyle"):
        # Special case: an mrow containing only fence operators around content
        # → emit a delimiter <m:d> for proper Word rendering of "(x)" "[x]" etc.
        fenced = _try_extract_fence(node)
        if fenced is not None:
            return [fenced]
        out: list[etree._Element] = []
        for c in node:
            out.extend(_convert(c))
        return out

    # Fractions
    if tag == "mfrac":
        kids = list(node)
        if len(kids) >= 2:
            f = etree.Element(f"{_M}f")
            etree.SubElement(f, f"{_M}fPr")
            num = etree.SubElement(f, f"{_M}num")
            for c in _convert(kids[0]):
                num.append(c)
            den = etree.SubElement(f, f"{_M}den")
            for c in _convert(kids[1]):
                den.append(c)
            return [f]
        return []

    # Square roots / radicals
    if tag == "msqrt":
        rad = etree.Element(f"{_M}rad")
        rpr = etree.SubElement(rad, f"{_M}radPr")
        deghide = etree.SubElement(rpr, f"{_M}degHide")
        deghide.set(f"{_M}val", "1")
        etree.SubElement(rad, f"{_M}deg")
        e = etree.SubElement(rad, f"{_M}e")
        for child in node:
            for c in _convert(child):
                e.append(c)
        return [rad]

    if tag == "mroot":
        kids = list(node)
        if len(kids) >= 2:
            rad = etree.Element(f"{_M}rad")
            etree.SubElement(rad, f"{_M}radPr")
            deg = etree.SubElement(rad, f"{_M}deg")
            for c in _convert(kids[1]):
                deg.append(c)
            e = etree.SubElement(rad, f"{_M}e")
            for c in _convert(kids[0]):
                e.append(c)
            return [rad]
        return []

    # Subscript / superscript
    if tag == "msub":
        return _build_script(node, "sSub", ["e", "sub"])
    if tag == "msup":
        return _build_script(node, "sSup", ["e", "sup"])
    if tag == "msubsup":
        return _build_script(node, "sSubSup", ["e", "sub", "sup"])

    if tag in ("munder", "mover", "munderover"):
        # Approximate under/over as plain content + the script content
        # (full <m:limLow>/<m:limUpp> would be richer but is overkill here)
        out: list[etree._Element] = []
        for c in node:
            out.extend(_convert(c))
        return out

    # Explicit delimited groups <mfenced open="(" close=")">
    if tag == "mfenced":
        open_char = node.get("open", "(")
        close_char = node.get("close", ")")
        return [_make_delim(node, open_char, close_char)]

    # Unknown / unhandled: inline children so we degrade gracefully
    out: list[etree._Element] = []
    for c in node:
        out.extend(_convert(c))
    return out


def _build_script(
    node: etree._Element,
    omml_tag: str,
    slot_names: list[str],
) -> list[etree._Element]:
    """Build <m:sSub>/<m:sSup>/<m:sSubSup> from MathML <msub>/<msup>/<msubsup>."""
    kids = list(node)
    if len(kids) < len(slot_names):
        return []
    script = etree.Element(f"{_M}{omml_tag}")
    etree.SubElement(script, f"{_M}{omml_tag}Pr")
    for slot, kid in zip(slot_names, kids):
        slot_el = etree.SubElement(script, f"{_M}{slot}")
        for c in _convert(kid):
            slot_el.append(c)
    return [script]


def _try_extract_fence(mrow: etree._Element) -> etree._Element | None:
    """If ``mrow`` is exactly ``<mo fence>(</mo> ... <mo fence>)</mo>``,
    return a single ``<m:d>`` delimiter element. Otherwise return None."""
    kids = list(mrow)
    if len(kids) < 2:
        return None
    first, last = kids[0], kids[-1]
    if _local(first.tag) != "mo" or _local(last.tag) != "mo":
        return None
    if not first.get("fence") and not last.get("fence"):
        return None
    open_char = (first.text or "").strip()
    close_char = (last.text or "").strip()
    if not open_char or not close_char:
        return None
    return _make_delim(mrow, open_char, close_char, skip_first_last=True)


def _make_delim(
    parent: etree._Element,
    open_char: str,
    close_char: str,
    *,
    skip_first_last: bool = False,
) -> etree._Element:
    """Build an <m:d> delimiter wrapping the (inner) children of ``parent``."""
    d = etree.Element(f"{_M}d")
    dpr = etree.SubElement(d, f"{_M}dPr")
    begin = etree.SubElement(dpr, f"{_M}begChr")
    begin.set(f"{_M}val", open_char)
    end = etree.SubElement(dpr, f"{_M}endChr")
    end.set(f"{_M}val", close_char)
    e = etree.SubElement(d, f"{_M}e")
    kids = list(parent)
    if skip_first_last:
        kids = kids[1:-1]
    for kid in kids:
        for c in _convert(kid):
            e.append(c)
    return e.getparent()  # the <m:d>
