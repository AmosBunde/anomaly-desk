"""Event ingestion: normalization, offset assignment, production, and replay.

Normalizes source-specific records into the single event envelope defined in README.md
section 5, so no agent ever sees source-specific shape. Assigns the ``offset`` that the
replayer later uses to reproduce an exact event sequence.

Replay determinism as defined in README.md section 10 is implemented here, including its
limit: the pinned model rejects sampling parameters, so this package guarantees an
identical event sequence rather than identical model output.

Implemented by A9 (envelope and normalization) and A16 (producer and replayer).
"""
