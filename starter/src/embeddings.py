"""Real local embedding model via Sentence Transformers (no API key, cost 0)."""
from typing import Protocol

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    """Query và document dùng chung một cách encode, vector được chuẩn hóa độ dài 1.

    Nếu model không tải/chạy được thì báo lỗi, không fallback sang vector giả.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimensions = len(self.model.encode(["kiểm tra số chiều"])[0])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, batch_size=32, normalize_embeddings=True,
                                    show_progress_bar=len(texts) > 64)
        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        return self.model.encode([question], normalize_embeddings=True)[0].tolist()
