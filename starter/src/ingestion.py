"""Read and normalize source data (PDF -> one DocumentPage per physical page)."""
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace, keeping paragraph breaks (blank lines)."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)      # nối từ bị ngắt dòng bằng gạch nối
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)            # dòng trống = ranh giới đoạn
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)      # xuống dòng đơn = cùng một đoạn
    return text.strip()


def load_pdf(path: Path, document_id: str, source: str, errors: list[dict] | None = None,
             only_pages: set[int] | None = None) -> list[DocumentPage]:
    """Extract physical pages (1-based). Empty/failed pages are logged in `errors`.

    `only_pages`: chỉ trích các trang này (sách dày thì không cần đọc cả cuốn).
    """
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for number, pdf_page in enumerate(reader.pages, start=1):
        if only_pages is not None and number not in only_pages:
            continue
        try:
            text = normalize_text(pdf_page.extract_text() or "")
        except Exception as exc:  # trang hỏng: ghi lỗi, không dừng cả pipeline
            text = ""
            if errors is not None:
                errors.append({"document_id": document_id, "page": number,
                               "error": f"extract_failed: {exc}"})
        if not text and errors is not None:
            errors.append({"document_id": document_id, "page": number,
                           "error": "empty_page (trang trống hoặc scan cần OCR)"})
        pages.append(DocumentPage(document_id, source, number, text))
    return pages
