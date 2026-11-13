"""Fixed-size and paragraph-based chunking. Chunk IDs are stable across re-runs."""
import re

from .models import Chunk, DocumentPage


def _make(page: DocumentPage, tag: str, texts: list[str]) -> list[Chunk]:
    return [
        Chunk(f"{page.document_id}-p{page.page:04d}-{tag}-{i:03d}", page.document_id,
              page.source, page.page, text, dict(page.metadata))
        for i, text in enumerate(texts)
    ]


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Cắt cửa sổ `size` ký tự, mỗi cửa sổ lùi lại `overlap` ký tự so với cửa sổ trước."""
    if not 0 <= overlap < size:
        raise ValueError("overlap phải nhỏ hơn size")
    text, step = page.text, size - overlap
    texts = [text[start:start + size].strip() for start in range(0, len(text), step)
             if start == 0 or start + overlap < len(text)]
    return _make(page, "fix", [t for t in texts if t])


def _split_long(paragraph: str, max_size: int) -> list[str]:
    """Đoạn dài hơn max_size: tách theo câu; câu vẫn quá dài thì cắt cứng."""
    pieces: list[str] = []
    for sentence in re.split(r"(?<=[.!?…:;])\s+", paragraph):
        while len(sentence) > max_size:
            pieces.append(sentence[:max_size])
            sentence = sentence[max_size:]
        if sentence:
            pieces.append(sentence)
    return pieces


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Gom các đoạn liền nhau cho tới khi gần chạm max_size; không cắt giữa câu."""
    units: list[tuple[str, str]] = []            # (text, dấu nối với đơn vị trước)
    for paragraph in (p.strip() for p in page.text.split("\n\n")):
        if not paragraph:
            continue
        if len(paragraph) <= max_size:
            units.append((paragraph, "\n\n"))
        else:
            units.extend((piece, " " if i else "\n\n")
                         for i, piece in enumerate(_split_long(paragraph, max_size)))
    texts: list[str] = []
    current = ""
    for text, joiner in units:
        if current and len(current) + len(joiner) + len(text) > max_size:
            texts.append(current)
            current = text
        else:
            current = current + joiner + text if current else text
    if current:
        texts.append(current)
    return _make(page, "par", texts)
