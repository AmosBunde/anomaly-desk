# API service image, per README.md section 2.
#
# Installs the package from pyproject.toml so the container and local development resolve
# the same dependency set. The CPU-only PyTorch index is used for the reason recorded in
# section 4: the default Linux torch wheel depends on the full CUDA stack, and nothing in
# this project has a GPU to run it on. Skipping this step would add several gigabytes of
# libraries that can never execute to an image running in a memory-constrained stack.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Dependency layer first, so source edits do not invalidate the expensive install.
COPY pyproject.toml README.md ./
RUN python -m pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && mkdir -p anomalydesk && touch anomalydesk/__init__.py \
 && python -m pip install . \
 && python -m pip uninstall -y anomaly-desk

# Fail the build rather than shipping an image that violates the section 4 constraint.
RUN if python -m pip list | grep -iE '^(nvidia-|cuda-)'; then \
      echo "CUDA packages present in the image. README.md section 4 forbids requiring a GPU." >&2; \
      python -m pip list | grep -iE '^(nvidia-|cuda-)' >&2; \
      exit 1; \
    fi \
 && python -c "import torch; assert '+cpu' in torch.__version__, torch.__version__" \
 && echo "Image is CPU-only, as required."

COPY anomalydesk ./anomalydesk
RUN python -m pip install --no-deps -e .

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "anomalydesk.serve.app:app", "--host", "0.0.0.0", "--port", "8000"]
