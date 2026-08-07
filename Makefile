# Anomaly Desk. Every target named in README.md section 15 is declared here.
#
# A target whose implementation has not landed yet exits non-zero and names the plan
# identifier that implements it. It never exits zero. A target that silently does nothing
# makes a broken pipeline look green, which is worse than a missing target, and the deploy
# gate at A37 runs these same targets.

.DEFAULT_GOAL := help
SHELL := /bin/bash
PYTHON ?= python3

# Pinned toolchain versions for the Kubernetes path, installed by A5 into ./bin.
KIND_VERSION    ?= v0.23.0
KUBECTL_VERSION ?= v1.30.2
HELM_VERSION    ?= v3.15.2

# Prints the message for a target that is declared but not yet implemented, then fails.
define pending
	@printf '\033[33m%s is not implemented yet.\033[0m\n' "$(1)"; \
	printf 'It is delivered by plan item %s. See BREAKDOWN.md for its dependencies.\n' "$(2)"; \
	exit 1
endef

.PHONY: help
help: ## List every target
	@printf 'Anomaly Desk targets\n\n'
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@printf '\nTargets marked (A<n>) are declared but not implemented; they exit non-zero.\n'

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

# PyTorch arrives transitively through sentence-transformers, and its default wheel on
# Linux depends on the full CUDA stack: cuBLAS, cuDNN, cuFFT, nvrtc and the rest. That is
# several gigabytes of GPU libraries on a machine with no GPU, and it contradicts the
# hardware constraint in README.md section 4 that no stage of this project requires one.
# Installing the CPU-only build first from the PyTorch CPU index satisfies the dependency,
# so the second command resolves it as already present and never reaches the CUDA wheels.
# Measured difference: 191 MB against 526 MB for torch alone, before CUDA.
TORCH_CPU_INDEX ?= https://download.pytorch.org/whl/cpu

.PHONY: install
install: ## Install the package and development dependencies, CPU-only
	$(PYTHON) -m pip install torch --index-url $(TORCH_CPU_INDEX)
	$(PYTHON) -m pip install -e '.[dev]'
	@printf '\033[32mInstalled. Verifying no CUDA packages were pulled in.\033[0m\n'
	@if $(PYTHON) -m pip list 2>/dev/null | grep -qiE '^(nvidia-|cuda-)'; then \
		printf '\033[31mCUDA packages are present. This machine has no GPU and README.md\n'; \
		printf 'section 4 forbids requiring one. Investigate before continuing.\033[0m\n'; \
		$(PYTHON) -m pip list | grep -iE '^(nvidia-|cuda-)'; \
		exit 1; \
	else \
		printf 'No CUDA packages present, as required.\n'; \
	fi

.PHONY: lint
lint: ## Run ruff check and format check
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

.PHONY: format
format: ## Apply ruff formatting
	$(PYTHON) -m ruff format .

.PHONY: test
test: ## Run the test suite
	$(PYTHON) -m pytest

.PHONY: prose
prose: ## Enforce the house prose style on tracked Markdown
	$(PYTHON) scripts/prose_lint.py

.PHONY: check
check: lint prose test ## Run everything continuous integration runs, in the same order
	@printf '\033[32mAll local checks passed.\033[0m\n'

# ---------------------------------------------------------------------------
# Data and retrieval
# ---------------------------------------------------------------------------

.PHONY: data
data: ## (A9) Fetch and normalize pinned sources, assign offsets
	$(call pending,make data,A9)

.PHONY: index
index: ## (A19) Chunk runbooks with provenance, embed, load pgvector
	$(call pending,make index,A19)

.PHONY: replay
replay: ## (A16) Emit the fixed offset list into Kafka
	$(call pending,make replay,A16)

# ---------------------------------------------------------------------------
# Evaluation. Note the ordering constraint: eval works before any agent exists.
# ---------------------------------------------------------------------------

.PHONY: eval
eval: ## (A14) Score the current variant, print the dual scoreboard
	$(call pending,make eval,A14)

.PHONY: smoke
smoke: ## (A14) The continuous integration evaluation slice
	$(call pending,make smoke,A14)

.PHONY: redteam
redteam: ## (A35) Adversarial and must-escalate run, write the safety report
	$(call pending,make redteam,A35)

.PHONY: trace-report
trace-report: ## (A34) Per-hop latency and cost per triage
	$(call pending,make trace-report,A34)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

.PHONY: serve
serve: ## (A29) Run the API on :8000
	$(call pending,make serve,A29)

.PHONY: ui
ui: ## (A30) Run the operator console on :3000
	$(call pending,make ui,A30)

.PHONY: up
up: ## (A3) Bring up the full Docker Compose stack
	$(call pending,make up,A3)

.PHONY: down
down: ## (A3) Stop the Docker Compose stack
	$(call pending,make down,A3)

# ---------------------------------------------------------------------------
# Kubernetes
# ---------------------------------------------------------------------------

.PHONY: kind-up
kind-up: ## (A5) Install pinned tooling into ./bin and create the local cluster
	$(call pending,make kind-up,A5)

.PHONY: kind-down
kind-down: ## (A5) Delete the local cluster
	$(call pending,make kind-down,A5)

.PHONY: deploy
deploy: ## (A38) Deploy to the local cluster
	$(call pending,make deploy,A38)

.PHONY: gate
gate: ## (A37) Run the evaluation-regression deploy gate
	$(call pending,make gate,A37)
