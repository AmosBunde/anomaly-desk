# Anomaly Desk: issue breakdown

This document is the issue-level plan. It is the contract for what gets built, in what order, on which
branch, and how large each pull request is allowed to be. `README.md` is the technical specification; this
document is the execution plan against it.

## How to read this

- **Issue** is the GitHub issue number, assigned in the order below.
- **Branch** is the exact name passed to `gh issue develop <n> --name <branch> --checkout`.
- **Depends** lists issues that must be merged first. An issue with no dependency inside its milestone may be
  worked in parallel with its siblings, but a milestone never starts before the previous milestone is fully
  merged with continuous integration green.
- **Lines** is the reviewable-changed-line budget, excluding lockfiles, user interface build artifacts, and
  evaluation run outputs. An issue projected past roughly 400 lines is split before work starts, not merged
  large.
- **Body** is the issue template: `P` for Problem, Design, Acceptance criteria, Risks, Out of scope;
  `H` for Hypothesis, Design, Acceptance criteria, Risks, Out of scope.

Every issue, without exception, carries: a label, a milestone, a linked development branch, at least one
commit comment recording a measurement or a decision a reviewer would otherwise have to guess, a substantive
self-review comment before merge, and a closing comment with post-merge evidence.

## Milestone M0: Scaffold

Goal: a stack that comes up on a clean machine, a continuous integration pipeline that enforces the house
style, and a Kubernetes path that exists before it is needed at M5. No product logic.

| Issue | Title | Branch | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Author the technical specification and the issue breakdown | `chore/1-contract` | `type:infra` | none | 400 | P |
| 2 | Python package skeleton, pyproject, and Makefile targets | `chore/2-skeleton` | `type:infra` | 1 | 220 | P |
| 3 | Docker Compose stack: Kafka in KRaft mode, PostgreSQL with pgvector, API, console, OpenTelemetry collector | `chore/3-compose` | `type:infra` | 2 | 300 | P |
| 4 | Continuous integration: ruff, pytest, and the prose linter | `chore/4-ci` | `type:infra` | 2 | 200 | P |
| 5 | Kubernetes path on kind, with tool install targets | `chore/5-kind` | `type:infra` | 3 | 260 | P |
| 6 | Rendered architecture page and diagram synchronization check | `chore/6-architecture-page` | `type:infra` | 3 | 380 | P |

Notes that shape these six issues:

- Issue 3 uses a single-broker Kafka in KRaft mode with no ZooKeeper container, and puts the vector store
  inside PostgreSQL using pgvector rather than running a separate vector service. Both choices are driven by
  the memory budget of the development machine and both are recorded in a commit comment with the measured
  resident set size of the running stack.
- Issue 4 includes the prose linter because principle 9 and the definition of done both require the absence of
  contractions, em dashes, and unfilled placeholders. Enforcing that by hand across more than thirty pull
  requests is not credible; enforcing it with a grep-based check in continuous integration is.
- Issue 5 installs `kind`, `kubectl`, and `helm`, none of which are present on the development machine. This
  lands at M0 rather than M5 so the gap is discovered now rather than at the deployment milestone.
- Issue 6 carries a check that fails continuous integration when the Mermaid source in `README.md` and
  `docs/architecture.html` drift apart, so the synchronization requirement is mechanical rather than
  aspirational.

## Milestone M1: Labeled set and judge first

Goal: the labeled set, the red-team set, the judge, and the dual scoreboard, all working and all scored,
before any agent exists. Hard rule 1 makes this milestone the gate for everything after it. No file under
`anomalydesk/agents/` is created in M1.

| Issue | Title | Branch | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | Pin event sources and record licensing in docs/sources.md | `data/7-sources` | `phase:evalset` | 4 | 240 | P |
| 8 | PostgreSQL schema and migrations | `feat/8-schema` | `phase:evalset` | 3 | 300 | P |
| 9 | Event envelope, normalization, and offset assignment | `feat/9-envelope` | `phase:evalset` | 7, 8 | 280 | P |
| 10 | Label 100 or more operational events with rubrics | `data/10-labeled-set` | `phase:evalset` | 9 | 260 | P |
| 11 | Red-team set: contradiction, missing data, injection, must-escalate | `data/11-redteam` | `safety` | 10 | 300 | P |
| 12 | Model interface and token ledger | `feat/12-model-interface` | `phase:evalset` | 8 | 280 | P |
| 13 | Judge harness: rubric scoring and citation span verification | `feat/13-judge` | `phase:evalset` | 10, 12 | 380 | P |
| 14 | Dual scoreboard and the continuous integration smoke slice | `feat/14-scoreboard` | `phase:evalset` | 13 | 320 | P |
| 15 | Finding: judge-to-human agreement on the M1 subsample | `docs/15-m1-finding` | `finding` | 14 | 200 | P |

Notes:

- Issue 12 lands before the judge because the judge is itself a model caller and must record its own tokens
  and cost through the same ledger. Building the ledger twice is how cost accounting becomes a footnote.
- Issue 13 implements the three mechanical grounding checks from specification section 7 before any quality
  scoring, so a fabricated citation cannot be rescued by fluent prose.
- Issue 14 prints both scoreboards from the first run. The override-rate column reads zero at M1 because no
  operator has dispositioned anything yet, and that zero is labeled as not-yet-measured rather than as a good
  result.
- Issue 15 is the audit from specification section 8.4. A judge nobody has checked against a human is an
  opinion, so this finding is a milestone deliverable rather than optional documentation.

## Milestone M2: Ingestion and single-agent baseline

Goal: a real stream, a real index, and the first scored number. Everything after M2 is measured against what
lands here.

| Issue | Title | Branch | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| 16 | Producer and deterministic replayer over a fixed offset list | `feat/16-producer-replayer` | `phase:ingest` | 9, 14 | 320 | P |
| 17 | Consumer with idempotency, bounded retry, and a dead letter queue | `feat/17-consumer` | `phase:ingest` | 16 | 360 | P |
| 18 | Structure-aware chunking with per-chunk provenance | `feat/18-chunking` | `phase:ingest` | 8 | 300 | P |
| 19 | Embeddings and pgvector index build | `feat/19-index` | `phase:ingest` | 18 | 280 | P |
| 20 | Single-agent classifier with structured output | `feat/20-baseline-agent` | `phase:ingest` | 12, 17 | 300 | P |
| 21 | Experiment: record the single-agent baseline as the number to beat | `exp/21-baseline-run` | `exp` | 19, 20 | 200 | H |

Notes:

- Issue 16 is where replay determinism becomes real, and it is also where the honest limit in specification
  section 10 is implemented: the run harness executes each scored configuration three times and reports the
  mean with the range, because the pinned model rejects sampling parameters and output variance cannot be
  configured away.
- Issue 20 is the first agent in the repository, and it may not be started until issue 14 is merged. That
  ordering is hard rule 1 and it is checked at review time.
- Issue 21 fills the first row of specification section 13 and is the first experiment pull request, so it is
  the first to lead with the dual scoreboard table.

## Milestone M3: Multi-agent orchestration

Goal: three agents behind typed schemas, an orchestrator that cannot silently drop an event, and a scored
delta against M2 that reports latency and cost honestly alongside quality.

| Issue | Title | Branch | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| 22 | Shared agent schemas and the schema violation counter | `feat/22-schemas` | `phase:agents` | 20 | 300 | P |
| 23 | Classifier and retrieval agents behind typed contracts | `feat/23-classifier-retrieval` | `phase:agents` | 22 | 340 | P |
| 24 | Drafting agent with structural citations | `feat/24-drafting` | `phase:agents` | 23 | 320 | P |
| 25 | Orchestrator with step budgets and a degraded fallback to the queue | `feat/25-orchestrator` | `phase:agents` | 24 | 380 | P |
| 26 | Tool scoping and the operator confirmation gate | `feat/26-tool-scope` | `safety` | 25 | 300 | P |
| 27 | Experiment: multi-agent workflow versus the M2 baseline | `exp/27-multiagent-run` | `exp` | 26 | 220 | H |

Notes:

- Issue 22 lands the violation counter with the schemas rather than after them, because hard rule 2 requires a
  violation to be counted and reported rather than reinterpreted, and a counter added later always misses the
  paths written before it.
- Issue 25 carries the invariant that every failure, timeout, and budget exhaustion ends in an operator queue
  entry. The acceptance criteria include a test that injects a failure at each hop and asserts a queue entry
  exists in every case.
- Issue 26 implements specification section 12 as code: no tools on the classifier or drafting agents, one
  read-only tool on the retrieval agent, and a confirmation gate in the orchestrator rather than in a prompt.
  It is labeled `safety` and its red-team assertions run in continuous integration.

## Milestone M4: Human loop and the second scoreboard

Goal: the second scoreboard becomes real, measured from operator behavior rather than from the judge, and the
first written analysis of the two disagreeing.

| Issue | Title | Branch | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| 28 | Versioned escalation policy loader and evaluator | `feat/28-escalation-policy` | `phase:human` | 25 | 300 | P |
| 29 | Operator queue API and disposition persistence | `feat/29-queue-api` | `phase:human` | 28 | 320 | P |
| 30 | React operator console: queue and detail views | `feat/30-console` | `phase:human` | 29 | 400 | P |
| 31 | Override-rate scoreboard with field-level edit capture | `feat/31-override-rate` | `phase:human` | 30 | 300 | P |
| 32 | Finding: judge versus operator disagreement analysis | `docs/32-disagreement` | `finding` | 31 | 240 | P |

Notes:

- Issue 28 moves thresholds out of code and into `configs/escalation.yaml` under version control, and adds the
  must-escalate subset to the continuous integration gate so a weakened policy fails the build rather than
  quietly improving the aggregate score.
- Issue 30 is the largest single pull request in the plan at a 400-line budget. If the queue and detail views
  together exceed that, the detail view splits into its own issue rather than merging over budget.
- Issue 31 captures edits at field granularity, so an override of severity is distinguishable from an override
  of the action list. A single boolean would make the second scoreboard far less useful than the effort it
  costs to build.
- Issue 32 is the deliverable hard rule 5 exists for. It reports both numbers first and proposes
  interpretations second, and it does not adjust a rubric or a threshold to make the two agree.

## Milestone M5: Observability, red-teaming, and the deploy gate

Goal: answer where the latency and the money went, prove the safety properties rather than assert them, and
gate deployment on evaluation regression.

| Issue | Title | Branch | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| 33 | OpenTelemetry spans per event and per agent hop | `feat/33-spans` | `phase:obs` | 25 | 320 | P |
| 34 | Trace report: per-hop latency and cost per triage | `feat/34-trace-report` | `phase:obs` | 33 | 300 | P |
| 35 | Red-team runner and the safety report | `feat/35-redteam-runner` | `safety` | 11, 26 | 340 | P |
| 36 | A/B harness scored against override rate | `exp/36-ab-harness` | `exp` | 31, 34 | 320 | H |
| 37 | Evaluation-regression deploy gate in continuous integration | `feat/37-deploy-gate` | `phase:obs` | 35, 36 | 280 | P |
| 38 | Kubernetes deployment on kind and deploy/runbook.md | `chore/38-deploy` | `phase:obs` | 5, 37 | 380 | P |
| 39 | Final results report and the filled section 13 table | `docs/39-results` | `finding` | 38 | 300 | P |

Notes:

- Issue 35 turns specification section 12 from a claim into a measurement. Compliance with an injected
  instruction is a scored safety failure, and the report covers contradictory events, missing data, injected
  text, and must-escalate cases as four separate sections.
- Issue 36 scores against override rate rather than against the judge, which is the point of building a second
  scoreboard at all. Where the two disagree, the finding is written rather than resolved by preference.
- Issue 37 blocks a merge on must-escalate regression regardless of aggregate quality gains, per hard rule 4.
- Issue 39 fills the results table in specification section 13 from real runs and closes the definition of
  done.

## Issue count and coverage

Thirty-nine issues, which satisfies the definition-of-done requirement of thirty or more, each linked to a
merged pull request through a development branch.

| Milestone | Issues | Count |
| --- | --- | --- |
| M0 Scaffold | 1 to 6 | 6 |
| M1 Labeled set and judge | 7 to 15 | 9 |
| M2 Ingestion and baseline | 16 to 21 | 6 |
| M3 Multi-agent orchestration | 22 to 27 | 6 |
| M4 Human loop | 28 to 32 | 5 |
| M5 Observability and deploy gate | 33 to 39 | 7 |

## Ordering constraints that are not negotiable

1. **Issue 14 before issue 20.** The scoreboard prints before the first agent exists. This is hard rule 1 and
   it is the single ordering constraint most likely to be violated under time pressure.
2. **Issue 22 before issues 23, 24, and 25.** Schemas and the violation counter precede the agents that must
   satisfy them.
3. **Issue 26 before issue 27.** Tool scoping lands before the experiment that reports the multi-agent
   workflow as a result, so no scored number is produced by a configuration with unscoped tools.
4. **Issue 28 before issue 31.** The policy is versioned before the override rate is measured against it,
   otherwise the second scoreboard has no fixed policy to measure.
5. **Issues 35 and 36 before issue 37.** The gate cannot enforce checks that do not exist.

## Deviations from this plan

A deviation is raised with the owner before it is made, never discovered in a pull request. The three
categories that always require a conversation first are: a change that breaks replay determinism as defined in
specification section 10, a change that weakens the escalation policy or the must-escalate gate, and a change
that widens tool scope. Adding a dependency not implied by the specification, and changing the judge model,
are also owner decisions rather than implementation details.
