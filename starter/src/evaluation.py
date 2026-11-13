"""Automatic retrieval metrics (Hit@1, Evidence Hit@3) with per-query traces.

Coherence, metadata và grounding KHÔNG được suy ra ở đây: phải chấm tay.
"""
import re
import unicodedata
from typing import Any


def norm(text: str) -> str:
    """Chuẩn hóa để so khớp evidence: NFC, chữ thường, gộp khoảng trắng."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().casefold()


def gold_options(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Gold chính + các nguồn thay thế hợp lệ trong `gold_alternatives` (nếu có)."""
    main = {key: question[key] for key in ("gold_source_id", "gold_page", "evidence_quote")}
    return [main, *question.get("gold_alternatives", [])]


def is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    """Hit = chunk đúng tài liệu, đúng trang gold và chứa ĐỦ evidence_quote."""
    metadata = hit["metadata"]
    return any(
        metadata["document_id"] == gold["gold_source_id"]
        and metadata["page"] == gold["gold_page"]
        and norm(gold["evidence_quote"]) in norm(hit["text"])
        for gold in gold_options(question)
    )


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]],
                   applied_filter: dict[str, Any] | None = None) -> dict[str, Any]:
    flags = [is_hit(question, hit) for hit in hits]
    obeys = None                                   # None = câu này không áp dụng filter
    if applied_filter:
        obeys = all(hit["metadata"].get(key) == value
                    for hit in hits for key, value in applied_filter.items())
    return {
        "id": question["id"], "split": question["split"], "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold": gold_options(question),
        "applied_filter": applied_filter,
        "top3": [{"rank": rank, **hit, "is_hit": flag}
                 for rank, (hit, flag) in enumerate(zip(hits, flags), start=1)],
        "hit_at_1": bool(flags[:1] and flags[0]),
        "hit_at_3": any(flags[:3]),
        "top3_obeys_filter": obeys,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Tổng hợp theo split, báo dạng n/N."""
    summary: dict[str, Any] = {}
    for split in sorted({trace["split"] for trace in traces}):
        rows = [trace for trace in traces if trace["split"] == split]
        filtered = [trace for trace in rows if trace["top3_obeys_filter"] is not None]
        summary[split] = {
            "n_questions": len(rows),
            "hit_at_1": f"{sum(t['hit_at_1'] for t in rows)}/{len(rows)}",
            "evidence_hit_at_3": f"{sum(t['hit_at_3'] for t in rows)}/{len(rows)}",
            "filter_obeyed": (f"{sum(t['top3_obeys_filter'] for t in filtered)}/{len(filtered)}"
                              if filtered else "N/A"),
        }
    return summary
