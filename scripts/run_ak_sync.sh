#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${AKSYNC_ENV_FILE:-${REPO_ROOT}/scripts/ak_sync.env}"

if [[ -f "${ENV_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
fi

cd "${REPO_ROOT}"

ARGS=(run-all --commit-message "sync: auto merge upstream and rewrite internal imports")

if [[ "${AKSYNC_DRY_RUN:-0}" == "1" ]]; then
    ARGS+=(--dry-run)
else
    ARGS+=(--publish --deploy)
fi

python3 -m tools.ak_sync.cli "${ARGS[@]}"
