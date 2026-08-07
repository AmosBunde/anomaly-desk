"""Kafka consumption with idempotency, bounded retry, and a dead letter queue.

An event is claimed by idempotency key before triage begins, so a redelivery does not
produce a second triage. A schema violation at the envelope boundary routes to the dead
letter queue and is counted, per hard rule 2, rather than being passed downstream as text.

Implemented by A17.
"""
