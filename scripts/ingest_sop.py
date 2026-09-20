"""Explicit, idempotent SOP ingestion; never runs at startup."""

import argparse

from coldchain.retrieval.core import (
    DeterministicEmbeddingProvider,
    QdrantVectorStore,
    chunk_document,
)
from coldchain.retrieval.corpus import load_corpus


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--collection", default="coldchain_sop_v1")
    args = parser.parse_args()
    embeddings = DeterministicEmbeddingProvider()
    chunks = [chunk for document in load_corpus() for chunk in chunk_document(document)]
    vectors = embeddings.embed([chunk.text for chunk in chunks])
    QdrantVectorStore(args.qdrant_url, args.collection, embeddings.dimensions).upsert(
        chunks, vectors
    )
    print(f"Ingested {len(chunks)} stable SOP chunks into {args.collection}.")


if __name__ == "__main__":
    main()
