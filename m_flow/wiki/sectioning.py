"""
Wiki Sectioning

Splits source text into sections for wiki page generation.
Supports markdown heading-based splitting and fallback character-based chunking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WikiSection:
    """A section extracted from source text."""

    title: str
    text: str
    source_hash: str = ""


def split_into_sections(text: str, max_chars: int = 12000) -> list[WikiSection]:
    """
    Split text into sections for wiki page generation.

    First attempts to split by markdown headings (# to ###).
    If no headings found, falls back to character-based chunking.

    Args:
        text: Source text to split.
        max_chars: Maximum characters per section (used in fallback chunking).

    Returns:
        List of WikiSection objects with titles and text content.
    """
    # Pattern for markdown headings H1-H3
    heading_pattern = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if matches:
        sections: list[WikiSection] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append(WikiSection(title=match.group(1).strip(), text=body))

        if sections:
            return sections

    # Fallback: chunk by max_chars
    chunks = [text[i : i + max_chars].strip() for i in range(0, len(text), max_chars)]
    return [
        WikiSection(title=f"Section {i + 1}", text=chunk) for i, chunk in enumerate(chunks) if chunk
    ]