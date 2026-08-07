"""Versioned escalation policy: loading, validation, and evaluation.

Thresholds and must-escalate rules live in ``configs/escalation.yaml`` under version
control, per hard rule 4. The must-escalate rules are unconditional and are not overridden
by a high confidence score.

Implemented by A28.
"""
