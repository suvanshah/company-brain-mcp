"""
Markdown-aware chunking for Company Brain documents.

Creates self-contained chunks that carry their own heading context so they remain
meaningful even when split at boundaries. Splits first by headings, then by
paragraphs, then by sentences, with overlap to preserve context.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from document_loader import Document


@dataclass
class Chunk:
    """A searchable chunk of a document."""
    id: str
    document: Document
    section: Optional[str]
    content: str


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences without dropping the delimiters."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p for p in parts if p.strip()]


def _split_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs by blank lines."""
    return [p for p in re.split(r'\n\s*\n', text) if p.strip()]


def _chunk_section(
    section_body: str,
    header: str,
    max_chunk_chars: int,
    overlap_chars: int,
) -> List[str]:
    """Split a section body into pieces that fit within max_chunk_chars."""
    # Available body chars after the header is prepended.
    body_budget = max(1, max_chunk_chars - len(header))
    pieces: List[str] = []

    def add_piece(body: str):
        # Add the previous piece's tail as overlap, except for the first piece.
        overlap = ""
        if pieces:
            tail = pieces[-1][len(header):]  # strip the previous header
            overlap = tail[-overlap_chars:] if len(tail) > overlap_chars else tail
        piece = header + overlap + body
        if len(piece) > max_chunk_chars:
            piece = piece[:max_chunk_chars]
        pieces.append(piece)

    if len(section_body) <= body_budget:
        add_piece(section_body)
        return pieces

    # Try paragraph-level splitting first.
    paragraphs = _split_paragraphs(section_body)
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= body_budget:
            current = current + "\n\n" + para if current else para
            continue
        if current:
            add_piece(current)
        current = para
    if current:
        add_piece(current)

    # If any piece is still too long (rare), split by sentences within it.
    final_pieces: List[str] = []
    for piece in pieces:
        body = piece[len(header):]
        if len(body) <= body_budget:
            final_pieces.append(piece)
            continue
        sentences = _split_sentences(body)
        current = ""
        for sent in sentences:
            if len(current) + len(sent) + 1 <= body_budget:
                current = current + " " + sent if current else sent
                continue
            if current:
                final_pieces.append(header + current)
            current = sent
        if current:
            final_pieces.append(header + current)

    return final_pieces if final_pieces else [header + section_body[:body_budget]]


def chunk_document(
    doc: Document,
    max_chunk_tokens: int = 500,
    overlap_tokens: int = 75,
) -> List[Chunk]:
    """Split a document into independent, context-carrying chunks."""
    max_chunk_chars = max_chunk_tokens * 4
    overlap_chars = overlap_tokens * 4
    chunk_index = 0

    def next_id() -> str:
        nonlocal chunk_index
        cid = f"{doc.id}#chunk-{chunk_index}"
        chunk_index += 1
        return cid

    # Use the document title as the first line of every chunk.
    doc_header = f"Document: {doc.title}\n"

    # Find markdown headings (##, ###, etc.). We do not split on the top-level #
    # because that is the document title.
    heading_re = re.compile(r'^(#{2,6})\s+(.+)$', re.MULTILINE)
    matches = list(heading_re.finditer(doc.content))

    chunks: List[Chunk] = []

    if not matches:
        # No subheadings: treat the whole document body as one section.
        pieces = _chunk_section(doc.content, doc_header, max_chunk_chars, overlap_chars)
        for piece in pieces:
            chunks.append(Chunk(
                id=next_id(),
                document=doc,
                section=None,
                content=piece,
            ))
        return chunks

    # Intro section: from the start of the content up to the first heading.
    intro_end = matches[0].start()
    intro_body = doc.content[:intro_end].strip()
    # Drop the leading # title line if it is duplicated in the header.
    intro_body = re.sub(r'^#\s+.+\n*', '', intro_body, count=1, flags=re.MULTILINE).strip()
    if intro_body:
        pieces = _chunk_section(intro_body, doc_header, max_chunk_chars, overlap_chars)
        for piece in pieces:
            chunks.append(Chunk(
                id=next_id(),
                document=doc,
                section=None,
                content=piece,
            ))

    # One section per heading.
    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        section_start = match.end()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(doc.content)
        section_body = doc.content[section_start:section_end].strip()
        section_header = doc_header + f"Section: {heading}\n\n"

        if not section_body:
            # Empty heading: still create a tiny chunk carrying the heading.
            chunks.append(Chunk(
                id=next_id(),
                document=doc,
                section=heading,
                content=section_header.rstrip(),
            ))
            continue

        pieces = _chunk_section(section_body, section_header, max_chunk_chars, overlap_chars)
        for piece in pieces:
            chunks.append(Chunk(
                id=next_id(),
                document=doc,
                section=heading,
                content=piece,
            ))

    return chunks
