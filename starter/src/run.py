"""Day 06 pipeline. Chạy từ thư mục starter/:

    python -m src.run check    # kiểm tra corpus (>=30 trang) và benchmark (evidence có thật)
    python -m src.run ingest   # chunk + embed + lưu Chroma cho cấu hình A và B (C dùng chung B)
    python -m src.run eval     # top-3 cho mọi câu hỏi, trace, Hit@1/Hit@3, file chấm tay
"""
import csv
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .chunking import by_paragraph, fixed_size
from .evaluation import evaluate_query, norm, summarize
from .ingestion import load_pdf
from .models import Chunk, DocumentPage

ROOT = Path(__file__).resolve().parents[2]          # thư mục gốc của repo
MANIFEST = ROOT / "data" / "manifest.json"
QUESTIONS = ROOT / "benchmark" / "questions.json"
RESULTS = ROOT / "results"
CHROMA_DIR = ROOT / "chroma_db"

MIN_PAGE_CHARS = 200        # trang có ít hơn số ký tự này không tính là trang nội dung
TOP_K = 3
# A và B chỉ khác cách chunk; B và C chỉ khác việc áp dụng metadata filter.
STRATEGIES: dict[str, dict[str, Any]] = {
    "A": {"collection": "day06_fixed", "chunking": "fixed_size", "size": 500, "overlap": 50,
          "use_filter": False},
    "B": {"collection": "day06_paragraph", "chunking": "by_paragraph", "max_size": 500,
          "use_filter": False},
    "C": {"collection": "day06_paragraph", "chunking": "by_paragraph", "max_size": 500,
          "use_filter": True},
}


def save_json(name: str, data: Any) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_csv(name: str, header: list[str], rows: list[list[Any]]) -> None:
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / name).open("w", newline="", encoding="utf-8-sig") as file:   # mở được bằng Excel
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def load_corpus() -> tuple[list[DocumentPage], list[dict]]:
    """Đọc các PDF trong manifest; chỉ giữ trang thuộc `sections` và đủ nội dung."""
    if not MANIFEST.exists():
        sys.exit(f"Thiếu {MANIFEST}. Copy data/manifest.example.json thành manifest.json rồi sửa.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pages: list[DocumentPage] = []
    errors: list[dict] = []
    for document in manifest["documents"]:
        path = ROOT / "data" / document["file"]
        if not path.exists():
            sys.exit(f"Không thấy file {path}")
        wanted = {number for section in document["sections"]
                  for number in range(section["pages"][0], section["pages"][1] + 1)}
        by_number = {page.page: page for page in load_pdf(
            path, document["source_id"], document["file"], errors, only_pages=wanted)}
        for section in document["sections"]:
            first, last = section["pages"]
            for page in (by_number[n] for n in range(first, last + 1) if n in by_number):
                if len(page.text) < MIN_PAGE_CHARS:
                    errors.append({"document_id": page.document_id, "page": page.page,
                                   "error": f"skipped: <{MIN_PAGE_CHARS} ký tự ({len(page.text)})"})
                    continue
                page.metadata = {"section": section["section"], "title": document["title"]}
                pages.append(page)
    keys = [(page.document_id, page.page) for page in pages]
    if len(set(keys)) != len(keys):
        sys.exit("Manifest có khoảng trang bị chồng lấn giữa các section.")
    return pages, errors


def load_questions() -> list[dict]:
    if not QUESTIONS.exists():
        sys.exit(f"Thiếu {QUESTIONS}. Copy benchmark/questions.example.json rồi viết câu hỏi của bạn.")
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def build_chunks(name: str, pages: list[DocumentPage]) -> list[Chunk]:
    config = STRATEGIES[name]
    chunks: list[Chunk] = []
    for page in pages:
        if config["chunking"] == "fixed_size":
            chunks += fixed_size(page, config["size"], config["overlap"])
        else:
            chunks += by_paragraph(page, config["max_size"])
    return chunks


def check() -> bool:
    pages, errors = load_corpus()
    ok = True
    print(f"Trang nội dung hợp lệ: {len(pages)} (yêu cầu >= 30)")
    for section in sorted({page.metadata["section"] for page in pages}):
        count = sum(page.metadata["section"] == section for page in pages)
        print(f"  section={section}: {count} trang")
    print(f"Trang lỗi/bỏ qua: {len(errors)} (xem results/ingest_errors.json)")
    save_json("ingest_errors.json", errors)
    save_csv("content_pages.csv", ["document_id", "page", "section", "chars"],
             [[p.document_id, p.page, p.metadata["section"], len(p.text)] for p in pages])
    if len(pages) < 30:
        print("LỖI: chưa đủ 30 trang nội dung."); ok = False

    questions = load_questions()
    by_key = {(page.document_id, page.page): page for page in pages}
    dev = [q for q in questions if q["split"] == "dev"]
    test = [q for q in questions if q["split"] == "test"]
    filtered = [q for q in questions if q.get("filter")]
    print(f"Câu hỏi: {len(questions)} (dev {len(dev)}, test {len(test)}, có filter {len(filtered)})")
    problems: list[str] = []
    if len(questions) < 20 or len(dev) < 15 or len(test) < 5:
        problems.append("Cần >= 20 câu, >= 15 dev và >= 5 test.")
    if len(filtered) < 3 or not any(q["split"] == "test" for q in filtered):
        problems.append("Cần >= 3 câu có filter, trong đó >= 1 câu test.")
    if len({q["id"] for q in questions}) != len(questions):
        problems.append("Có id câu hỏi bị trùng.")
    for question in questions:
        page = by_key.get((question["gold_source_id"], question["gold_page"]))
        if page is None:
            problems.append(f"{question['id']}: gold_source_id/gold_page không nằm trong corpus.")
            continue
        if norm(question["evidence_quote"]) not in norm(page.text):
            problems.append(f"{question['id']}: evidence_quote không có ở trang {page.page} sau chuẩn hóa.")
        for key, value in (question.get("filter") or {}).items():
            if page.metadata.get(key) != value:
                problems.append(f"{question['id']}: filter {key}={value} loại mất trang gold "
                                f"(trang gold có {key}={page.metadata.get(key)}).")
    for problem in problems:
        print("LỖI:", problem)
    ok = ok and not problems
    print("CHECK OK" if ok else "CHECK CHƯA ĐẠT: sửa các lỗi trên rồi chạy lại.")
    return ok


def ingest() -> None:
    from .embeddings import MyEmbedder
    from .store import ChromaStore

    pages, errors = load_corpus()
    if len(pages) < 30:
        sys.exit("Chưa đủ 30 trang nội dung; chạy `python -m src.run check` để xem chi tiết.")
    save_json("ingest_errors.json", errors)
    embedder = MyEmbedder()
    store = ChromaStore(str(CHROMA_DIR), embedder.dimensions)
    stats: dict[str, Any] = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "embedding_model": embedder.model_name, "dimensions": embedder.dimensions,
        "vector_store": "chroma PersistentClient, HNSW cosine", "cost_usd": 0, "strategies": {},
    }
    for name in ("A", "B"):                          # C dùng chung collection của B
        config = STRATEGIES[name]
        started = time.perf_counter()
        chunks = build_chunks(name, pages)
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        written = store.upsert(config["collection"], chunks, vectors)
        lengths = [len(chunk.text) for chunk in chunks]
        stats["strategies"][name] = {
            **config, **written, "chunk_count": len(chunks), "total_chars": sum(lengths),
            "len_min": min(lengths), "len_median": statistics.median(lengths),
            "len_max": max(lengths), "ingest_seconds": round(time.perf_counter() - started, 2),
        }
        print(f"{name}: {len(chunks)} chunk, collection có {written['count_after']} bản ghi, "
              f"xóa {written['deleted_obsolete']} chunk cũ")
    stats["strategies"]["C"] = {**STRATEGIES["C"], "note": "dùng chung collection và chunk của B"}
    save_json("ingest_stats.json", stats)

    # Mẫu chấm coherence: 10 trang đầu (đã sắp xếp), chunk đầu tiên của mỗi trang, A và B.
    sample = sorted(pages, key=lambda p: (p.document_id, p.page))[:10]
    rows = []
    for name in ("A", "B"):
        for page in sample:
            first = build_chunks(name, [page])[0]
            rows.append([name, page.document_id, page.page, first.chunk_id, first.text, "", ""])
    save_csv("audit_coherence.csv",
             ["strategy", "document_id", "page", "chunk_id", "text", "label_0_1_2", "reason"], rows)
    print("Đã ghi results/ingest_stats.json và results/audit_coherence.csv")


def evaluate() -> None:
    from .embeddings import MyEmbedder
    from .store import ChromaStore

    questions = load_questions()
    embedder = MyEmbedder()
    store = ChromaStore(str(CHROMA_DIR), embedder.dimensions)
    query_vectors = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    summary: dict[str, Any] = {}
    metadata_rows, grounding_rows = [], []
    for name, config in STRATEGIES.items():
        if store.count(config["collection"]) == 0:
            sys.exit("Collection rỗng: chạy `python -m src.run ingest` trước.")
        traces = []
        for question in questions:
            applied = question.get("filter") if config["use_filter"] else None
            hits = store.search(config["collection"], query_vectors[question["id"]], TOP_K,
                                applied or None)
            traces.append(evaluate_query(question, hits, applied or None))
        save_json(f"trace_{name}.json", traces)
        summary[name] = summarize(traces)
        for trace in (t for t in traces if t["split"] == "test"):
            grounding_rows.append([name, trace["id"], trace["question"],
                                   trace["expected_answer"], "", ""])
            for hit in trace["top3"]:
                meta = hit["metadata"]
                metadata_rows.append([name, trace["id"], hit["rank"], hit["chunk_id"],
                                      meta["source"], meta["page"], meta.get("section"),
                                      hit["text"][:200], "", ""])
    save_json("summary.json", summary)
    save_csv("audit_metadata.csv",
             ["strategy", "question_id", "rank", "chunk_id", "source", "page", "section",
              "text_preview", "metadata_correct_yes_no", "note"], metadata_rows)
    save_csv("audit_grounding.csv",
             ["strategy", "question_id", "question", "expected_answer", "label_0_1_2", "reason"],
             grounding_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Đã ghi results/trace_*.json, summary.json, audit_metadata.csv, audit_grounding.csv")


def main() -> None:
    commands = {"check": check, "ingest": ingest, "eval": evaluate}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    if commands[sys.argv[1]]() is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
