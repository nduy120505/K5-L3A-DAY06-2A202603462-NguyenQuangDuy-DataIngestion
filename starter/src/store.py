"""Vector store: Chroma PersistentClient (lưu trên đĩa), cosine, metadata filter."""
from typing import Any

import chromadb

from .models import Chunk

BATCH = 1000


class ChromaStore:
    def __init__(self, path: str, dimensions: int) -> None:
        self.client = chromadb.PersistentClient(path=path)
        self.dimensions = dimensions

    def _collection(self, name: str):
        # HNSW (approximate search) với khoảng cách cosine
        return self.client.get_or_create_collection(name=name,
                                                    metadata={"hnsw:space": "cosine"})

    def count(self, name: str) -> int:
        return self._collection(name).count()

    def upsert(self, name: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict[str, int]:
        """Ghi theo chunk_id ổn định (nạp lại không nhân đôi) và xóa chunk không còn tồn tại."""
        if len(chunks) != len(vectors):
            raise ValueError("Số chunk và số vector không khớp")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"Vector không đúng {self.dimensions} chiều")
        collection = self._collection(name)
        new_ids = [c.chunk_id for c in chunks]
        if len(set(new_ids)) != len(new_ids):
            raise ValueError("chunk_id bị trùng")
        obsolete = sorted(set(collection.get(include=[])["ids"]) - set(new_ids))
        for i in range(0, len(obsolete), BATCH):
            collection.delete(ids=obsolete[i:i + BATCH])
        for i in range(0, len(chunks), BATCH):
            part = chunks[i:i + BATCH]
            collection.upsert(
                ids=[c.chunk_id for c in part],
                embeddings=vectors[i:i + BATCH],
                documents=[c.text for c in part],
                metadatas=[{"document_id": c.document_id, "source": c.source,
                            "page": c.page, **c.metadata} for c in part],
            )
        return {"written": len(chunks), "deleted_obsolete": len(obsolete),
                "count_after": collection.count()}

    def search(self, name: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Top-k theo cosine. `filters` dạng {"section": "..."}; nhiều trường thì AND."""
        where: dict[str, Any] | None = None
        if filters:
            conditions = [{key: value} for key, value in filters.items()]
            where = conditions[0] if len(conditions) == 1 else {"$and": conditions}
        result = self._collection(name).query(query_embeddings=[query_vector],
                                              n_results=top_k, where=where)
        return [
            {"chunk_id": chunk_id, "text": text, "score": round(1 - distance, 4),
             "metadata": metadata}
            for chunk_id, text, distance, metadata in zip(
                result["ids"][0], result["documents"][0],
                result["distances"][0], result["metadatas"][0])
        ]
