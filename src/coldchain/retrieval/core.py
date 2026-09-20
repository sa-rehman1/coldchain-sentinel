"""Provider-neutral embeddings, stable chunking, and vector stores."""

import hashlib
import importlib
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, uuid5

import httpx


@dataclass(frozen=True, slots=True)
class SopDocument:
    document_id: str
    title: str
    semantic_version: str
    effective_date: date
    superseded_date: date | None
    checksum: str
    classification: str
    author: str
    source: str
    schema_version: str
    sections: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class SopChunk:
    chunk_id: str
    document_id: str
    section_id: str
    text: str
    document_hash: str
    chunk_hash: str
    effective_date: date
    superseded_date: date | None
    classification: str
    schema_version: str


class EmbeddingProvider(Protocol):
    identity: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    def upsert(self, chunks: list[SopChunk], vectors: list[list[float]]) -> None: ...

    def search(
        self, vector: list[float], *, as_of: date, top_k: int, threshold: float
    ) -> list[tuple[SopChunk, float]]: ...

    def ready(self) -> bool: ...


class DeterministicEmbeddingProvider:
    identity = "deterministic-hash-v1"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            values[index] += -1.0 if digest[4] & 1 else 1.0
        norm = math.sqrt(sum(item * item for item in values)) or 1.0
        return [item / norm for item in values]


class FastEmbedProvider:
    """Optional CPU ONNX provider; importing it never downloads a model."""

    identity = "fastembed"
    dimensions = 384

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        try:
            module = importlib.import_module("fastembed")
        except ModuleNotFoundError as exc:
            raise RuntimeError("install the semantic-embeddings extra to use FastEmbed") from exc
        embedding_type = cast(Any, module).TextEmbedding
        self._model = embedding_type(model_name=model_name, cache_dir=cache_dir)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, value)) for value in self._model.embed(texts)]


def chunk_document(document: SopDocument, max_chars: int = 1200) -> list[SopChunk]:
    chunks: list[SopChunk] = []
    for section_id, text in document.sections:
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        current = ""
        ordinal = 0
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(_chunk(document, section_id, ordinal, current))
                ordinal += 1
                current = paragraph
            else:
                current = candidate
        if current:
            chunks.append(_chunk(document, section_id, ordinal, current))
    return chunks


def _chunk(document: SopDocument, section_id: str, ordinal: int, text: str) -> SopChunk:
    chunk_hash = hashlib.sha256(text.encode()).hexdigest()
    stable = (
        f"{document.document_id}:{document.semantic_version}:{section_id}:{ordinal}:{chunk_hash}"
    )
    return SopChunk(
        chunk_id="sopch_" + hashlib.sha256(stable.encode()).hexdigest()[:24],
        document_id=document.document_id,
        section_id=section_id,
        text=text,
        document_hash=document.checksum,
        chunk_hash=chunk_hash,
        effective_date=document.effective_date,
        superseded_date=document.superseded_date,
        classification=document.classification,
        schema_version=document.schema_version,
    )


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._items: dict[str, tuple[SopChunk, list[float]]] = {}

    def upsert(self, chunks: list[SopChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunk/vector count mismatch")
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._items[chunk.chunk_id] = (chunk, vector)

    def search(
        self, vector: list[float], *, as_of: date, top_k: int, threshold: float
    ) -> list[tuple[SopChunk, float]]:
        top_k = min(max(top_k, 1), 10)
        candidates = []
        for chunk, stored in self._items.values():
            if chunk.effective_date > as_of:
                continue
            if chunk.superseded_date is not None and chunk.superseded_date <= as_of:
                continue
            score = sum(left * right for left, right in zip(vector, stored, strict=True))
            if score >= threshold:
                candidates.append((chunk, score))
        return sorted(candidates, key=lambda item: item[1], reverse=True)[:top_k]

    def ready(self) -> bool:
        return True


class QdrantVectorStore:
    """Small REST adapter keeping Qdrant out of domain and application layers."""

    def __init__(
        self, base_url: str, collection: str, dimensions: int, client: httpx.Client | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._collection = collection
        self._dimensions = dimensions
        self._client = client or httpx.Client(timeout=httpx.Timeout(10, connect=3))

    def ensure_collection(self) -> None:
        response = self._client.get(f"{self._base_url}/collections/{self._collection}")
        if response.status_code == 404:
            response = self._client.put(
                f"{self._base_url}/collections/{self._collection}",
                json={"vectors": {"size": self._dimensions, "distance": "Cosine"}},
            )
        response.raise_for_status()

    def upsert(self, chunks: list[SopChunk], vectors: list[list[float]]) -> None:
        self.ensure_collection()
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            payload = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "section_id": chunk.section_id,
                "text": chunk.text,
                "document_hash": chunk.document_hash,
                "chunk_hash": chunk.chunk_hash,
                "effective_date": chunk.effective_date.isoformat(),
                "superseded_date": chunk.superseded_date.isoformat()
                if chunk.superseded_date
                else None,
                "classification": chunk.classification,
                "schema_version": chunk.schema_version,
            }
            points.append(
                {
                    "id": str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                    "vector": vector,
                    "payload": payload,
                }
            )
        response = self._client.put(
            f"{self._base_url}/collections/{self._collection}/points?wait=true",
            json={"points": points},
        )
        response.raise_for_status()

    def search(
        self, vector: list[float], *, as_of: date, top_k: int, threshold: float
    ) -> list[tuple[SopChunk, float]]:
        filters: dict[str, Any] = {
            "must": [{"key": "effective_date", "range": {"lte": as_of.isoformat()}}]
        }
        response = self._client.post(
            f"{self._base_url}/collections/{self._collection}/points/query",
            json={
                "query": vector,
                "filter": filters,
                "limit": min(max(top_k, 1), 10),
                "score_threshold": threshold,
                "with_payload": True,
            },
        )
        response.raise_for_status()
        results = []
        for point in response.json()["result"]["points"]:
            payload = point["payload"]
            superseded = payload.get("superseded_date")
            if superseded and date.fromisoformat(superseded) <= as_of:
                continue
            chunk = SopChunk(
                chunk_id=payload["chunk_id"],
                document_id=payload["document_id"],
                section_id=payload["section_id"],
                text=payload["text"],
                document_hash=payload["document_hash"],
                chunk_hash=payload["chunk_hash"],
                effective_date=date.fromisoformat(payload["effective_date"]),
                superseded_date=date.fromisoformat(superseded) if superseded else None,
                classification=payload["classification"],
                schema_version=payload["schema_version"],
            )
            results.append((chunk, float(point["score"])))
        return results

    def ready(self) -> bool:
        try:
            return self._client.get(f"{self._base_url}/readyz").status_code == 200
        except httpx.HTTPError:
            return False
