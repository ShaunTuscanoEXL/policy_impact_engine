"""Document parser node for extracting structured sections from BRD files.

Supports DOCX and PDF formats. Splits documents into sections based on
numbered heading patterns (e.g. "1.0 Executive Summary") and classifies
each section by type using keyword matching.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from app.pipeline.schemas import DocumentSection, SectionType

# Keywords used to classify sections by type.
SECTION_KEYWORDS: dict[SectionType, list[str]] = {
    SectionType.EXECUTIVE_SUMMARY: ["executive summary", "overview"],
    SectionType.BACKGROUND: ["background", "rationale", "context"],
    SectionType.CURRENT_STATE: [
        "current state",
        "current rules",
        "existing",
        "as-is",
    ],
    SectionType.RULES: [
        "rule",
        "proposed",
        "change",
        "modification",
        "criteria",
        "requirement",
        "threshold",
        "eligibility",
    ],
    SectionType.IMPACT: ["impact", "assessment", "expected outcome", "effect"],
    SectionType.TIMELINE: ["timeline", "implementation", "schedule", "rollout"],
    SectionType.APPROVAL: ["approval", "sign-off", "authorization"],
}


def parse_document(content: bytes, filename: str) -> list[DocumentSection]:
    """Parse a BRD document into structured sections.

    Args:
        content: Raw file bytes.
        filename: Original filename (used to detect format via extension).

    Returns:
        List of DocumentSection objects extracted from the document.

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

    return _split_into_sections(text)


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_docx_text(content: bytes) -> str:
    """Extract text from a DOCX file, preserving paragraph structure."""
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs: list[str] = []

    for para in doc.paragraphs:
        if para.text.strip():
            # Mark headings so the section splitter can find them.
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                paragraphs.append(f"\n## {para.text.strip()}\n")
            else:
                paragraphs.append(para.text.strip())

    # Also extract table content so rule details are not lost.
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            paragraphs.append(" | ".join(cells))

    return "\n".join(paragraphs)


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF file, annotating page boundaries."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(f"[Page {i + 1}]\n{text}")
    return "\n\n".join(pages)


# ---------------------------------------------------------------------------
# Section splitting and classification
# ---------------------------------------------------------------------------

# Matches numbered headings like "1.0 Executive Summary" or markdown "## Heading"
_SECTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:(\d+\.\d+)\s+(.+?)(?:\n|$)|##\s+(.+?)(?:\n|$))"
)


def _split_into_sections(text: str) -> list[DocumentSection]:
    """Split extracted text into sections based on numbered headings."""
    matches = list(_SECTION_PATTERN.finditer(text))

    if not matches:
        # No section headers found -- treat entire text as one section.
        return [
            DocumentSection(
                section_id="s0",
                title="Full Document",
                content=text.strip(),
                section_type=_classify_section("Full Document", text),
            )
        ]

    sections: list[DocumentSection] = []
    for i, match in enumerate(matches):
        raw_title = (match.group(2) or match.group(3) or "").strip()
        # Strip leading section number (e.g. "1.0 ") if present in markdown headings
        title = re.sub(r"^\d+\.\d+\s+", "", raw_title)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        section_type = _classify_section(title, content)

        sections.append(
            DocumentSection(
                section_id=f"s{i}",
                title=title,
                content=content,
                section_type=section_type,
            )
        )

    return sections


def _classify_section(title: str, content: str) -> SectionType:
    """Classify a section type based on title and content keywords.

    Title matches are weighted heavily (10x) over content matches so that
    a heading like "Executive Summary" is not overridden by rule-related
    keywords that happen to appear in the body text.
    """
    title_lower = title.lower()
    content_lower = content[:300].lower()

    best_type = SectionType.OTHER
    best_score = 0

    for section_type, keywords in SECTION_KEYWORDS.items():
        score = sum(10 for kw in keywords if kw in title_lower)
        score += sum(1 for kw in keywords if kw in content_lower)
        if score > best_score:
            best_score = score
            best_type = section_type

    return best_type
