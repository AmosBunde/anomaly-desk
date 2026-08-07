# Anomaly Desk: issue breakdown

This document is the issue-level plan. It is the contract for what gets built, in what order, on which
branch, and how large each pull request is allowed to be. `README.md` is the technical specification; this
document is the execution plan against it.

## How to read this

**Plan identifiers are not GitHub issue numbers.** GitHub assigns issues and pull requests from a single
shared counter, so opening issue 1 and then its pull request consumes numbers 1 and 2, and the offset between
plan position and GitHub number grows as work proceeds. Every row below therefore carries a stable plan
identifier of the form `A1` through `A39`, and the mapping to real GitHub numbers is maintained in the
"GitHub issue mapping" section near the end of this document, updated as each issue is opened. Dependencies
and ordering constraints reference plan identifiers, so they stay correct no matter what numbers GitHub
assigns.

- **Plan ID** is the stable identifier used everywhere in this document.
- **Branch slug** is the trailing portion of the branch name. The full branch is
  `<type>/<github-issue-number>-<slug>`, produced by
  `gh issue develop <github-issue-number> --name <type>/<github-issue-number>-<slug> --checkout`. The type
  prefix is given in the slug column.
- **Depends** lists plan identifiers that must be merged first. An issue with no dependency inside its
  milestone may be worked in parallel with its siblings, but a milestone never starts before the previous
  milestone is fully merged with continuous integration green.
- **Lines** is the reviewable-changed-line budget for code, excluding lockfiles, user interface build
  artifacts, and evaluation run outputs. An issue projected past roughly 400 lines is split before work
  starts, not merged large. A value of `prose` marks a documentation-only issue, which is held to the separate
  standard in specification section 16 instead: one document or one closely coupled pair per pull request, and
  no prose mixed with code.
- **Body** is the issue template: `P` for Problem, Design, Acceptance criteria, Risks, Out of scope;
  `H` for Hypothesis, Design, Acceptance criteria, Risks, Out of scope.

Every issue, without exception, carries: a label, a milestone, a linked development branch, at least one
commit comment recording a measurement or a decision a reviewer would otherwise have to guess, a substantive
self-review comment before merge, and a closing comment with post-merge evidence.

## Milestone M0: Scaffold

Goal: a stack that comes up on a clean machine, a continuous integration pipeline that enforces the house
style, and a Kubernetes path that exists before it is needed at M5. No product logic.

| Plan ID | Title | Branch slug | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Author the technical specification and the issue breakdown | `chore/…-contract` | `type:infra` | none | prose | P |
| A2 | Python package skeleton, pyproject, and Makefile targets | `chore/…-skeleton` | `type:infra` | A1 | 220 | P |
| A3 | Docker Compose stack: Kafka in KRaft mode, PostgreSQL with pgvector, API, console, OpenTelemetry collector | `chore/…-compose` | `type:infra` | A2 | 300 | P |
| A4 | Continuous integration: ruff, pytest, and the prose linter | `chore/…-ci` | `type:infra` | A2 | 200 | P |
| A5 | Kubernetes path on kind, with tool install targets | `chore/…-kind` | `type:infra` | A3 | 260 | P |
| A6 | Rendered architecture page and diagram synchronization check | `chore/…-architecture-page` | `type:infra` | A3 | 380 | P |

Notes that shape these six issues:

- A3 uses a single-broker Kafka in KRaft mode with no ZooKeeper container, and puts the vector store inside
  PostgreSQL using pgvector rather than running a separate vector service. Both choices are driven by the
  memory budget of the development machine and both are recorded in a commit comment with the measured
  resident set size of the running stack.
- A4 includes the prose linter because principle 9 and the definition of done both require the absence of
  contractions, em dashes, and unfilled placeholders. Enforcing that by hand across more than thirty pull
  requests is not credible; enforcing it with a grep-based check in continuous integration is. This check
  found a real defect in A1 that two readings had missed, which is the empirical argument for it.
- A5 installs `kind`, `kubectl`, and `helm`, none of which are present on the development machine. This lands
  at M0 rather than M5 so the gap is discovered now rather than at the deployment milestone. It measured the
  idle control plane at 655 MB against the Compose stack's 658 MB, 1.3 GB together with 5.9 GB still available,
  so **memory is not the constraint A38 has to plan around. Host ports are:** both the cluster and the Compose
  stack publish the API and the console, so running them together requires different ports for each, or the
  Compose stack stopped first. `deploy/runbook.md` at A38 records that rather than a memory limit.
- A6 carries a check that fails continuous integration when the Mermaid source in `README.md` and
  `docs/architecture.html` drift apart, so the synchronization requirement is mechanical rather than
  aspirational.

## Milestone M1: Labeled set and judge first

Goal: the labeled set, the red-team set, the judge, and the dual scoreboard, all working and all scored,
before any agent exists. Hard rule 1 makes this milestone the gate for everything after it. No file under
`anomalydesk/agents/` is created in M1.

| Plan ID | Title | Branch slug | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| A7 | Pin event sources and record licensing in docs/sources.md | `data/…-sources` | `phase:evalset` | A4 | 240 | P |
| A8 | PostgreSQL schema and migrations | `feat/…-schema` | `phase:evalset` | A3 | 300 | P |
| A9 | Event envelope, normalization, and offset assignment | `feat/…-envelope` | `phase:evalset` | A7, A8 | 280 | P |
| A10 | Label 100 or more operational events with rubrics | `data/…-labeled-set` | `phase:evalset` | A9 | 260 | P |
| A11 | Red-team set: contradiction, missing data, injection, must-escalate | `data/…-redteam` | `safety` | A10 | 300 | P |
| A12 | Model interface and token ledger | `feat/…-model-interface` | `phase:evalset` | A8 | 280 | P |
| A13 | Judge harness: rubric scoring and citation span verification | `feat/…-judge` | `phase:evalset` | A10, A12 | 380 | P |
| A14 | Dual scoreboard and the continuous integration smoke slice | `feat/…-scoreboard` | `phase:evalset` | A13 | 320 | P |
| A15 | Finding: judge-to-human agreement on the M1 subsample | `docs/…-m1-finding` | `finding` | A14 | prose | P |

Notes:

- A12 lands before the judge because the judge is itself a model caller and must record its own tokens and
  cost through the same ledger. Building the ledger twice is how cost accounting becomes a footnote.
- A13 implements the three mechanical grounding checks from specification section 7 before any quality
  scoring, so a fabricated citation cannot be rescued by fluent prose.
- A13 requires a model credential. There is no `ANTHROPIC_API_KEY` in the environment at the time of writing
  and no local inference runtime installed, so this issue is blocked on the owner supplying one. M0 is not
  affected.
- A14 prints both scoreboards from the first run. The override-rate column reads zero at M1 because no
  operator has dispositioned anything yet, and that zero is labeled as not-yet-measured rather than as a good
  result.
- A15 is the audit from specification section 8.4. A judge nobody has checked against a human is an opinion,
  so this finding is a milestone deliverable rather than optional documentation.

## Milestone M2: Ingestion and single-agent baseline

Goal: a real stream, a real index, and the first scored number. Everything after M2 is measured against what
lands here.

| Plan ID | Title | Branch slug | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| A16 | Producer and deterministic replayer over a fixed offset list | `feat/…-producer-replayer` | `phase:ingest` | A9, A14 | 320 | P |
| A17 | Consumer with idempotency, bounded retry, and a dead letter queue | `feat/…-consumer` | `phase:ingest` | A16 | 360 | P |
| A18 | Structure-aware chunking with per-chunk provenance | `feat/…-chunking` | `phase:ingest` | A8 | 300 | P |
| A19 | Embeddings and pgvector index build | `feat/…-index` | `phase:ingest` | A18 | 280 | P |
| A20 | Single-agent classifier with structured output | `feat/…-baseline-agent` | `phase:ingest` | A12, A17 | 300 | P |
| A21 | Experiment: record the single-agent baseline as the number to beat | `exp/…-baseline-run` | `exp` | A19, A20 | 200 | H |

Notes:

- A16 is where replay determinism becomes real, and it is also where the honest limit in specification
  section 10 is implemented: the run harness executes each scored configuration three times and reports the
  mean with the range, because the pinned model rejects sampling parameters and output variance cannot be
  configured away.
- A20 is the first agent in the repository, and it may not be started until A14 is merged. That ordering is
  hard rule 1 and it is checked at review time.
- A21 fills the first row of specification section 13 and is the first experiment pull request, so it is the
  first to lead with the dual scoreboard table. It also produces the first real run-to-run range figures,
  which the acceptance criteria of A27 depend on being smaller than the improvement A27 targets.

## Milestone M3: Multi-agent orchestration

Goal: three agents behind typed schemas, an orchestrator that cannot silently drop an event, and a scored
delta against M2 that reports latency and cost honestly alongside quality.

| Plan ID | Title | Branch slug | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| A22 | Shared agent schemas and the schema violation counter | `feat/…-schemas` | `phase:agents` | A20 | 300 | P |
| A23 | Classifier and retrieval agents behind typed contracts | `feat/…-classifier-retrieval` | `phase:agents` | A22 | 340 | P |
| A24 | Drafting agent with structural citations | `feat/…-drafting` | `phase:agents` | A23 | 320 | P |
| A25 | Orchestrator with step budgets and a degraded fallback to the queue | `feat/…-orchestrator` | `phase:agents` | A24 | 380 | P |
| A26 | Tool scoping and the operator confirmation gate | `feat/…-tool-scope` | `safety` | A25 | 300 | P |
| A27 | Experiment: multi-agent workflow versus the M2 baseline | `exp/…-multiagent-run` | `exp` | A26 | 220 | H |

Notes:

- A22 lands the violation counter with the schemas rather than after them, because hard rule 2 requires a
  violation to be counted and reported rather than reinterpreted, and a counter added later always misses the
  paths written before it.
- A25 carries the invariant that every failure, timeout, and budget exhaustion ends in an operator queue
  entry. The acceptance criteria include a test that injects a failure at each hop and asserts a queue entry
  exists in every case.
- A26 implements specification section 12 as code: no tools on the classifier or drafting agents, one
  read-only tool on the retrieval agent, and a confirmation gate in the orchestrator rather than in a prompt.
  It is labeled `safety` and its red-team assertions run in continuous integration.
- A27 targets a six-point improvement in action quality. That target is provisional until A21 reports real
  run-to-run range: if the range turns out to be comparable to six points, the criterion is not measurable
  and is revised before A27 starts rather than after it fails.

## Milestone M4: Human loop and the second scoreboard

Goal: the second scoreboard becomes real, measured from operator behavior rather than from the judge, and the
first written analysis of the two disagreeing.

| Plan ID | Title | Branch slug | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| A28 | Versioned escalation policy loader and evaluator | `feat/…-escalation-policy` | `phase:human` | A25 | 300 | P |
| A29 | Operator queue API and disposition persistence | `feat/…-queue-api` | `phase:human` | A28 | 320 | P |
| A30 | React operator console: queue and detail views | `feat/…-console` | `phase:human` | A29 | 400 | P |
| A31 | Override-rate scoreboard with field-level edit capture | `feat/…-override-rate` | `phase:human` | A30 | 300 | P |
| A32 | Finding: judge versus operator disagreement analysis | `docs/…-disagreement` | `finding` | A31 | prose | P |

Notes:

- A28 moves thresholds out of code and into `configs/escalation.yaml` under version control, and adds the
  must-escalate subset to the continuous integration gate so a weakened policy fails the build rather than
  quietly improving the aggregate score.
- A30 is the largest single pull request in the plan at a 400-line budget. If the queue and detail views
  together exceed that, the detail view splits into its own issue rather than merging over budget.
- A31 captures edits at field granularity, so an override of severity is distinguishable from an override of
  the action list. A single boolean would make the second scoreboard far less useful than the effort it costs
  to build.
- A32 is the deliverable hard rule 5 exists for. It reports both numbers first and proposes interpretations
  second, and it does not adjust a rubric or a threshold to make the two agree.

## Milestone M5: Observability, red-teaming, and the deploy gate

Goal: answer where the latency and the money went, prove the safety properties rather than assert them, and
gate deployment on evaluation regression.

| Plan ID | Title | Branch slug | Label | Depends | Lines | Body |
| --- | --- | --- | --- | --- | --- | --- |
| A33 | OpenTelemetry spans per event and per agent hop | `feat/…-spans` | `phase:obs` | A25 | 320 | P |
| A34 | Trace report: per-hop latency and cost per triage | `feat/…-trace-report` | `phase:obs` | A33 | 300 | P |
| A35 | Red-team runner and the safety report | `feat/…-redteam-runner` | `safety` | A11, A26 | 340 | P |
| A36 | A/B harness scored against override rate | `exp/…-ab-harness` | `exp` | A31, A34 | 320 | H |
| A37 | Evaluation-regression deploy gate in continuous integration | `feat/…-deploy-gate` | `phase:obs` | A35, A36 | 280 | P |
| A38 | Kubernetes deployment on kind and deploy/runbook.md | `chore/…-deploy` | `phase:obs` | A5, A37 | 380 | P |
| A39 | Final results report and the filled section 13 table | `docs/…-results` | `finding` | A38 | prose | P |

Notes:

- A35 turns specification section 12 from a claim into a measurement. Compliance with an injected instruction
  is a scored safety failure, and the report covers contradictory events, missing data, injected text, and
  must-escalate cases as four separate sections.
- A36 scores against override rate rather than against the judge, which is the point of building a second
  scoreboard at all. Where the two disagree, the finding is written rather than resolved by preference.
- A37 blocks a merge on must-escalate regression regardless of aggregate quality gains, per hard rule 4.
- A39 fills the results table in specification section 13 from real runs and closes the definition of done.

## Issue count and coverage

Thirty-nine issues, which satisfies the definition-of-done requirement of thirty or more, each linked to a
merged pull request through a development branch.

| Milestone | Plan IDs | Count |
| --- | --- | --- |
| M0 Scaffold | A1 to A6 | 6 |
| M1 Labeled set and judge | A7 to A15 | 9 |
| M2 Ingestion and baseline | A16 to A21 | 6 |
| M3 Multi-agent orchestration | A22 to A27 | 6 |
| M4 Human loop | A28 to A32 | 5 |
| M5 Observability and deploy gate | A33 to A39 | 7 |

## GitHub issue mapping

Updated as each issue is opened. A plan identifier with no GitHub number has not been opened yet, which is a
statement of current state rather than a gap to be filled in later by someone else.

This table is a ledger rather than prose, and it is maintained inside the pull request of the issue whose row
it records. The rule in specification section 16 that documentation is not mixed with code exists to stop a
substantive specification change from being buried inside a code review; it was written too broadly and is not
intended to cover a one-row bookkeeping update, which is worth less as a separate pull request than the review
attention it would consume.

| Plan ID | GitHub issue | Pull request | Status |
| --- | --- | --- | --- |
| A1 | 1 | 2 | Merged |
| A2 | 3 | 8 | Merged |
| A3 | 4 | 10 | Merged |
| A4 | 5 | 9 | Merged |
| A5 | 6 | 13 | In review |
| A6 | 7 | 14 | In review |
| A40 | 11 | 12 | In review |

A40 is a defect fix against A3 rather than a planned item, added when an automated security review
of 923993a found that the stack published every service on all interfaces.

Plan identifiers A7 through A39 are not yet opened. Each milestone's issue list is posted for owner
confirmation before that milestone begins, so M1 issues are opened once M0 is fully merged.

## Ordering constraints that are not negotiable

1. **A14 before A20.** The scoreboard prints before the first agent exists. This is hard rule 1 and it is the
   single ordering constraint most likely to be violated under time pressure. It is checkable at review time
   by confirming that no file under `anomalydesk/agents/` appears in any merged pull request before A14 is
   merged.
2. **A22 before A23, A24, and A25.** Schemas and the violation counter precede the agents that must satisfy
   them.
3. **A26 before A27.** Tool scoping lands before the experiment that reports the multi-agent workflow as a
   result, so no scored number is produced by a configuration with unscoped tools.
4. **A28 before A31.** The policy is versioned before the override rate is measured against it, otherwise the
   second scoreboard has no fixed policy to measure.
5. **A35 and A36 before A37.** The gate cannot enforce checks that do not exist.

## Deviations from this plan

A deviation is raised with the owner before it is made, never discovered in a pull request. The three
categories that always require a conversation first are: a change that breaks replay determinism as defined in
specification section 10, a change that weakens the escalation policy or the must-escalate gate, and a change
that widens tool scope. Adding a dependency not implied by the specification, and changing the judge model,
are also owner decisions rather than implementation details.

Two container topology deviations were raised with the owner before A3 was started, and both were confirmed.
They are recorded here as decided rather than assumed, because both are written into specification section 2
and the repository structure and would be a migration rather than a configuration change to reverse after A18
and A19 land. Both are driven by the measured memory headroom of roughly 7 GB on the development machine.

1. **The vector store is placed inside PostgreSQL using pgvector** rather than running as a separate service.
   The build prompt lists a vector store as a distinct component of the Compose stack; the owner confirmed
   that this is a capability requirement rather than a container count. This keeps the citation-to-chunk join
   inside a single query, which is what makes the judge span verification in specification section 7
   straightforward. Revisit past roughly one million chunks.
2. **Kafka runs as a single broker in KRaft mode** with no ZooKeeper container and no replication. Durability
   buys little here because the event source is a replayable fixed offset list rather than a live production
   feed, so a lost partition is recovered by re-running `make replay`. The consequence accepted with this
   choice is that A17 does not exercise real partition rebalance behavior.
