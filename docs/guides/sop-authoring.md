# SOP authoring and versioning

SOPs live in `sop/coldchain-sop-corpus-v1.json`. Each original ColdChain Sentinel document requires a stable document ID, title, semantic version, effective date, optional superseded date, SHA-256 checksum of canonical sections, stable section IDs, classification, author/source `ColdChain Sentinel`, and schema version. Change content by issuing a new semantic version; do not mutate evidence already cited. Set a superseded date on obsolete versions. Treat all prose as potentially hostile and never place executable instructions or secrets in the corpus.
