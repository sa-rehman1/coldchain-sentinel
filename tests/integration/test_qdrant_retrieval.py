import os
from datetime import date

import pytest

from coldchain.retrieval.core import (
    DeterministicEmbeddingProvider,
    QdrantVectorStore,
    chunk_document,
)
from coldchain.retrieval.corpus import load_corpus


@pytest.mark.integration
def test_qdrant_idempotent_ingestion_and_retrieval() -> None:
    url = os.getenv("COLDCHAIN_TEST_QDRANT_URL")
    if not url:
        pytest.skip("COLDCHAIN_TEST_QDRANT_URL is not configured")
    embeddings = DeterministicEmbeddingProvider()
    store = QdrantVectorStore(url, "coldchain_sop_integration_v1", embeddings.dimensions)
    chunks = [chunk for document in load_corpus() for chunk in chunk_document(document)]
    vectors = embeddings.embed([item.text for item in chunks])
    store.upsert(chunks, vectors)
    store.upsert(chunks, vectors)
    query = embeddings.embed(["temperature excursion shipment hold dispatcher"])[0]
    results = store.search(query, as_of=date(2026, 9, 20), top_k=5, threshold=0.0)
    assert store.ready()
    assert results
    assert all(item.chunk_id.startswith("sopch_") for item, _ in results)
