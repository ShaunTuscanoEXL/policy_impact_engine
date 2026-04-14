"""Document parser — extracts clean, faithful text from BRD files.

The parser's ONLY job is to get the text out of the file accurately.
It preserves document order, interleaves tables inline, and marks headings.
ALL intelligence (understanding, rule finding) is done by the LLM.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from app.pipeline.schemas import DocumentSection, SectionType

logger = logging.getLogger(__name__)


def parse_document(content: bytes, filename: str) -> list[DocumentSection]:
    """Extract text from a BRD file and return it as document sections.

    The parser does minimal processing — just faithful text extraction.
    For the LLM extraction path, the full document text is what matters.

    Args:
        content: Raw file bytes.
        filename: Original filename (used to detect format via extension).

    Returns:
        List of DocumentSection objects. Always returns at least one section
        containing the full document text.

    Raises:
        ValueError: If the file extension is not supported.
    """
    ext = Path(filename).suffix.lower()
    if ext == ".docx":
        text = _extract_docx_text(content)
    elif ext == ".pdf":
        text = _extract_pdf_text(content)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if not text or len(text.strip()) < 20:
        logger.warning("Extracted text is too short (%d chars)", len(text.strip()) if text else 0)
        return []

    # Always include one section with the FULL document text.
    # This is what the extractor actually uses — the complete context.
    sections = [
        DocumentSection(
            section_id="full",
            title=Path(filename).stem,
            content=text.strip(),
            section_type=SectionType.RULES,
        )
    ]

    logger.info("Parsed '%s': %d chars of text extracted", filename, len(text))
    return sections


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_docx_text(content: bytes) -> str:
    """Extract text from a DOCX file, preserving paragraph and table structure.

    Interleaves paragraphs and tables in document order so table content
    appears under the correct heading.
    """
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(io.BytesIO(content))
    output: list[str] = []

    # Walk document body in order to interleave paragraphs and tables
    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            full_text = ""
            for node in element.iter():
                if node.tag.endswith("}t") or node.tag == "t":
                    full_text += (node.text or "")
            full_text = full_text.strip()
            if not full_text:
                continue

            # Check if it's a heading style
            style_elem = element.find(qn("w:pPr"))
            is_heading = False
            if style_elem is not None:
                style_name = style_elem.find(qn("w:pStyle"))
                if style_name is not None:
                    style_val = style_name.get(qn("w:val"), "")
                    if style_val.startswith("Heading"):
                        is_heading = True

            if is_heading:
                output.append(f"\n## {full_text}\n")
            else:
                output.append(full_text)

        elif tag == "tbl":
            rows_text = []
            for row_idx, tr in enumerate(element.findall(qn("w:tr"))):
                cells = []
                for tc in tr.findall(qn("w:tc")):
                    cell_text = ""
                    for p in tc.findall(qn("w:p")):
                        for node in p.iter():
                            if node.tag.endswith("}t") or node.tag == "t":
                                cell_text += (node.text or "")
                    cells.append(cell_text.strip())
                rows_text.append(" | ".join(cells))
                if row_idx == 0:
                    rows_text.append(" | ".join(["---"] * len(cells)))
            if rows_text:
                output.append("\n" + "\n".join(rows_text) + "\n")

    return "\n".join(output)


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF file."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(text)
    return "\n\n".join(pages)
