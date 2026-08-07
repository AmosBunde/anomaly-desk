#!/usr/bin/env bash
# Install kind, kubectl, and helm into ./bin at pinned versions.
#
# None of the three is present on the development machine. This lands at M0 rather than at
# M5 deliberately: discovering at the deployment milestone that the path needs three missing
# tools, on a machine with a constrained memory budget that must also run a control plane,
# is how a definition-of-done item quietly becomes unreachable.
#
# Installs into a gitignored ./bin rather than a system path, so the toolchain is
# reproducible, needs no sudo, and cannot collide with a version another project installed.
#
# Idempotent: a tool already present at the pinned version is left alone. A target that
# fails on second invocation gets worked around with manual cleanup, and manual cleanup is
# how a documented path stops matching what people actually do.

set -euo pipefail

KIND_VERSION="${KIND_VERSION:?KIND_VERSION must be set by the Makefile}"
KUBECTL_VERSION="${KUBECTL_VERSION:?KUBECTL_VERSION must be set by the Makefile}"
HELM_VERSION="${HELM_VERSION:?HELM_VERSION must be set by the Makefile}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${REPO_ROOT}/bin"
mkdir -p "${BIN_DIR}"

case "$(uname -m)" in
  x86_64)          ARCH=amd64 ;;
  aarch64|arm64)   ARCH=arm64 ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"

green() { printf '\033[32m%s\033[0m\n' "$1"; }
note()  { printf '  %s\n' "$1"; }

# Returns 0 when the tool is already installed at the pinned version.
already_installed() {
  local binary="$1" wanted="$2"
  [[ -x "${BIN_DIR}/${binary}" ]] || return 1
  "${BIN_DIR}/${binary}" version 2>/dev/null | grep -q -- "${wanted}" || return 1
  return 0
}

install_kind() {
  if already_installed kind "${KIND_VERSION}"; then
    note "kind ${KIND_VERSION} already installed"
    return
  fi
  note "installing kind ${KIND_VERSION}"
  curl -fsSL -o "${BIN_DIR}/kind" \
    "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-${OS}-${ARCH}"
  chmod +x "${BIN_DIR}/kind"
}

install_kubectl() {
  if already_installed kubectl "${KUBECTL_VERSION}"; then
    note "kubectl ${KUBECTL_VERSION} already installed"
    return
  fi
  note "installing kubectl ${KUBECTL_VERSION}"
  curl -fsSL -o "${BIN_DIR}/kubectl" \
    "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH}/kubectl"
  chmod +x "${BIN_DIR}/kubectl"
}

install_helm() {
  if already_installed helm "${HELM_VERSION}"; then
    note "helm ${HELM_VERSION} already installed"
    return
  fi
  note "installing helm ${HELM_VERSION}"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "${tmp}"' RETURN
  curl -fsSL -o "${tmp}/helm.tar.gz" \
    "https://get.helm.sh/helm-${HELM_VERSION}-${OS}-${ARCH}.tar.gz"
  tar -xzf "${tmp}/helm.tar.gz" -C "${tmp}"
  mv "${tmp}/${OS}-${ARCH}/helm" "${BIN_DIR}/helm"
  chmod +x "${BIN_DIR}/helm"
}

install_kind
install_kubectl
install_helm

green "Toolchain ready in ./bin"
"${BIN_DIR}/kind" --version
"${BIN_DIR}/kubectl" version --client --output=yaml | grep gitVersion | head -1
"${BIN_DIR}/helm" version --short
