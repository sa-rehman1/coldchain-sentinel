# Retrieval ingestion

Ingestion is explicit and never runs at startup:

```powershell
uv run python scripts/ingest_sop.py --qdrant-url http://localhost:6333 --collection coldchain_sop_v1
```

The loader verifies checksums, chunks deterministically, assigns stable content-derived IDs, and upserts idempotently. Default embeddings are deterministic and download nothing. To evaluate FastEmbed, install the optional extra and review ADR 0009 before allowing its first model download. Search caps top-k at 10, applies a score threshold, filters future content, and excludes superseded content after retrieval as defense in depth.
