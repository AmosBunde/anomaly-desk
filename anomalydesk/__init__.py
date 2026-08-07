"""Anomaly Desk: agentic triage of a continuous operational event stream.

The package layout mirrors README.md section 3. Two scoreboards score this system and
they are allowed to disagree: an automated judge harness in ``evals`` and the operator
override rate derived from dispositions captured through ``serve``.

Note that ``anomalydesk.agents`` is deliberately absent. Hard rule 1 forbids agent code
until the labeled set exists, the judge harness runs, and the scoreboard prints, which is
milestone M1. The subpackage is created by A22 along with the shared schemas that every
agent must satisfy.
"""

__version__ = "0.1.0"
