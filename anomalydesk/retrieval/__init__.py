"""Structure-aware chunking, embeddings, and vector search inside PostgreSQL.

Every chunk carries provenance: document identifier, section slug, character span, and the
source snapshot hash. Chunk identifiers take the form ``DOCID:chunk-N`` and resolve to an
exact span, which is what allows the judge to verify a cited span rather than trust it.

Vectors live in PostgreSQL via pgvector rather than in a separate service. That keeps the
citation-to-chunk join inside a single query. The decision was confirmed by the owner and
is recorded in the deviation section of BREAKDOWN.md.

Implemented by A18 (chunking) and A19 (embeddings and index).
"""
