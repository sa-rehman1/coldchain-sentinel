# ADR 0009: Qdrant and embedding strategy

Status: accepted, 2026-09-19.

Use local `qdrant/qdrant:v1.19.1` behind a provider-neutral vector-store port with persistent named storage and localhost-only host binding. Tests use deterministic 64-dimensional hash embeddings. The optional demonstration provider is FastEmbed with `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, Apache-2.0, approximately 0.09 GB download and 0.1–0.2 GB cache, CPU-only supported, no GPU required). Its normal cache is `~/.cache/fastembed`; set `FASTEMBED_CACHE_PATH` to relocate it. Installation or model download is never automatic.
