"""The evaluation plane: judge, rubrics, scoreboard, red-team runner, A/B harness.

This package exists before any agent does. Hard rule 1 requires the labeled set, the judge,
and the scoreboard to work before agent code is written, which makes milestone M1 the gate
for everything after it.

The judge performs three mechanical grounding checks from README.md section 7 before it
performs any quality scoring, so a fluent draft built on a fabricated citation cannot score
well. The scoreboard never prints the judge score alone, per hard rule 5.

Implemented by A13 (judge), A14 (scoreboard), A35 (red-team runner), A36 (A/B harness).
"""
