"""Content chunking helpers.

Mohammad owns the ingestion shape for FAQs, docs, policies, and services.
"""

import re
from typing import List, Dict, Any


class Chunk:
    def __init__(self, text: str, metadata: Dict[str, Any]):
        self.text = text
        self.metadata = metadata

    def to_dict(self):
        return {"text": self.text, "metadata": self.metadata}


def chunk_faq(text: str, tenant_id: str, content_id: str) -> List[Chunk]:
    """
    Split FAQ text into Q&A pairs using delimiter positions.
    Assumes FAQ text is formatted with Q: and A: or Question: and Answer:
    """
    # Locate all question delimiters at line starts
    pattern = re.compile(r'(?im)^\s*(Q:|Question:)\s*')
    matches = list(pattern.finditer(text))

    # No Q&A pattern → fall back to general chunking
    if not matches:
        return chunk_text(text, tenant_id, content_id, "faq")

    chunks = []
    chunk_idx = 0

    # Optional: capture preamble before the first question
    first_start = matches[0].start()
    if first_start > 0:
        preamble = text[:first_start].strip()
        if preamble:
            chunks.append(
                Chunk(
                    text=preamble,
                    metadata={
                        "tenant_id": tenant_id,
                        "content_id": content_id,
                        "chunk_index": chunk_idx,
                        "content_type": "faq",
                    },
                )
            )
            chunk_idx += 1

    # Extract each Q&A pair using start/end positions
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pair_text = text[start:end].strip()

        if pair_text:
            chunks.append(
                Chunk(
                    text=pair_text,
                    metadata={
                        "tenant_id": tenant_id,
                        "content_id": content_id,
                        "chunk_index": chunk_idx,
                        "content_type": "faq",
                    },
                )
            )
            chunk_idx += 1

    return chunks


def _split_text_with_separators(text: str, separators: List[str]) -> List[str]:
    """
    Recursively split text using the most appropriate separator,
    returning pieces no larger than 2000 chars.
    """
    final_pieces = []
    # Pick the first separator that actually appears
    chosen_sep = separators[-1]  # fallback: space
    for sep in separators:
        if sep in text:
            chosen_sep = sep
            break

    splits = text.split(chosen_sep)
    # Add separator back except for the last piece
    splits = [s + chosen_sep for s in splits[:-1]] + [splits[-1]]

    for s in splits:
        if not s:
            continue
        if len(s) > 2000:
            # Recurse with remaining separators
            next_seps = [sp for sp in separators if sp != chosen_sep]
            if next_seps:
                final_pieces.extend(_split_text_with_separators(s, next_seps))
            else:
                final_pieces.append(s)
        else:
            final_pieces.append(s)
    return final_pieces


def _merge_pieces_with_overlap(
    pieces: List[str], chunk_size: int, chunk_overlap: int
) -> List[str]:
    """
    Merge fine pieces into chunks of roughly chunk_size,
    maintaining the requested overlap.
    """
    if not pieces:
        return []

    chunks = []
    i = 0
    while i < len(pieces):
        current = pieces[i]
        # If a single piece exceeds chunk_size, split it with overlap
        if len(current) > chunk_size:
            for start in range(0, len(current), chunk_size - chunk_overlap):
                chunk = current[start : start + chunk_size]
                if chunk:
                    chunks.append(chunk)
            i += 1
            continue

        # Accumulate pieces until adding the next one would exceed chunk_size
        j = i + 1
        while j < len(pieces) and len(current) + len(pieces[j]) <= chunk_size - chunk_overlap:
            current += pieces[j]
            j += 1

        chunks.append(current)

        # Step back to create overlap
        if j < len(pieces):
            overlap_len = 0
            rollback = 0
            # Only rollback down to i + 1 to guarantee progress (i will always increase)
            for k in range(j - 1, i, -1):
                overlap_len += len(pieces[k])
                rollback += 1
                if overlap_len >= chunk_overlap:
                    break
            i = j - rollback
        else:
            i = j  # done

    return chunks


def chunk_text(
    text: str,
    tenant_id: str,
    content_id: str,
    content_type: str,
    chunk_size: int = 2000,
    chunk_overlap: int = 250,
) -> List[Chunk]:
    """
    Recursive character text splitter equivalent.
    chunk_size ~2000 chars roughly equals ~512 tokens.
    """
    separators = ["\n\n", "\n", ". ", " "]

    # 1. Break into fine pieces
    pieces = _split_text_with_separators(text, separators)

    # 2. Merge into overlapping chunks
    merged = _merge_pieces_with_overlap(pieces, chunk_size, chunk_overlap)

    # 3. Build Chunk objects with consecutive indices
    chunks = []
    chunk_idx = 0
    for c in merged:
        if not c.strip():
            continue
        chunks.append(
            Chunk(
                text=c,
                metadata={
                    "tenant_id": tenant_id,
                    "content_id": content_id,
                    "chunk_index": chunk_idx,
                    "content_type": content_type,
                },
            )
        )
        chunk_idx += 1

    return chunks


def process_document(
    text: str, tenant_id: str, content_id: str, content_type: str
) -> List[Chunk]:
    """
    Main entrypoint for chunking a document based on its type.
    content_types: faq, doc, policy, service
    """
    if content_type.lower() == "faq":
        return chunk_faq(text, tenant_id, content_id)
    else:
        return chunk_text(text, tenant_id, content_id, content_type)