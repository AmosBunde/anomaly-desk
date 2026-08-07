"""Workflow orchestration: step budgets, degraded fallback, and tool scoping.

Holds the invariant that no event is ever silently dropped. Every path that fails, times
out, or exhausts its step budget ends in an operator queue entry carrying its partial
trace.

Escalation is decided here by reading ``configs/escalation.yaml``, never by an agent
deciding for itself. The operator confirmation gate for any side-effecting action is code
in this package rather than an instruction in a prompt, because a prompt instruction is
exactly what injected event text attempts to overwrite.

Implemented by A25 (budgets and fallback) and A26 (tool scoping and confirmation gate).
"""
