"""Observability: OpenTelemetry spans and the token and cost ledger.

Spans are emitted at two granularities: one per event covering the whole triage, and one
child span per agent hop. The ledger stores token counts rather than money and resolves
per-token rates at report time, so a price change does not require reprocessing history.

Cost is a metric rather than a footnote, per hard rule 8, and appears next to quality in
every report.

Implemented by A12 (ledger) and A33 (spans).
"""
