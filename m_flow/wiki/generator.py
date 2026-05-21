"""
Wiki Page Generator

Generates wiki markdown pages from source text sections.
v1 is deterministic without LLM dependency; LLM hook can be added later.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .sectioning import WikiSection, split_into_sections


@dataclass(frozen=True)
class GeneratedWikiPage:
    """A generated wiki page with metadata."""

    path: str
    title: str
    content: str
    page_type: str
    content_hash: str
    source_hash: str
    excerpt: str


def _hash(text: str) -> str:
    """Generate MD5 hash of text."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _slug(title: str) -> str:
    """Convert title to URL-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", title.strip()).strip("-").lower()
    return slug or "section"


def _excerpt(text: str, limit: int = 240) -> str:
    """Generate excerpt from text."""
    collapsed = " ".join(text.split())
    return collapsed[:limit]


def _chapter_page(section: WikiSection) -> GeneratedWikiPage:
    """Generate a chapter page from a section."""
    source_hash = _hash(section.text)
    title = section.title
    excerpt_text = _excerpt(section.text, 800)
    content = f"# {title}\n\n## 摘要\n\n{excerpt_text}\n"

    return GeneratedWikiPage(
        path=f"chapters/{_slug(title)}.md",
        title=title,
        content=content,
        page_type="chapter",
        content_hash=_hash(content),
        source_hash=source_hash,
        excerpt=_excerpt(section.text),
    )


def generate_wiki_pages(title: str, text: str) -> list[GeneratedWikiPage]:
    """
    Generate wiki pages from source text.

    Generates:
    - index.md: Table of contents with links to all chapters
    - summary.md: Summary of the entire content
    - chapters/<slug>.md: One page per section

    Args:
        title: Title of the wiki collection.
        text: Source text content.

    Returns:
        List of GeneratedWikiPage objects ready to be written to disk.
    """
    sections = split_into_sections(text)
    chapter_pages = [_chapter_page(section) for section in sections]

    # Generate table of contents
    links = "\n".join(f"- [{page.title}]({page.path})" for page in chapter_pages)
    summary = _excerpt(text, 1200)
    index_content = f"# {title}\n\n## 目录\n\n{links}\n"
    summary_content = f"# {title} 摘要\n\n{summary}\n"

    return [
        GeneratedWikiPage(
            path="index.md",
            title=title,
            content=index_content,
            page_type="index",
            content_hash=_hash(index_content),
            source_hash=_hash(text),
            excerpt=_excerpt(index_content),
        ),
        GeneratedWikiPage(
            path="summary.md",
            title=f"{title} 摘要",
            content=summary_content,
            page_type="summary",
            content_hash=_hash(summary_content),
            source_hash=_hash(text),
            excerpt=_excerpt(summary),
        ),
        *chapter_pages,
    ]