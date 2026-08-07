# Prose linter fixture

This file deliberately violates the house style so scripts/prose_lint.py can be tested
against known input. It is excluded from the linter's default file set by the
EXCLUDED_PREFIXES constant. Line numbers are asserted in tests/test_prose_lint.py, so
inserting or removing lines here will fail those tests, which is intended.

## Violations, one per rule

An em dash appears in this sentence — right there.
An en dash appears in this sentence – right there.
This sentence isn't using a full form.
TODO: this placeholder should be reported.
This sentence contains an grounding failure of the article rule.

## Exemptions that must not be reported

The following fenced block contains a contraction and an article error. Both are data
rather than prose, so neither is reported.

```console
$ ./deploy.sh
error: can't reach the broker, retrying
note: this is an bad article inside a transcript
```

The following fenced block contains a placeholder, which is reported even inside code,
because unfinished work is unfinished wherever it appears.

```python
def triage(event):
    # TODO: implement in A20
    return None
```

Inline code such as `if (!x) { don't(); }` is stripped before the prose rules run.

## Correct usage that must not be reported

The gate enforces an SLA on must-escalate recall.
The judge reads an HTTP endpoint and an XML document.
A one-row ledger update is bookkeeping.
The run takes an hour on eight cores.
This is a unique identifier and a user-facing field.
The console shows a URL and an offset.
