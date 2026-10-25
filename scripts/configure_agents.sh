#!/usr/bin/env bash
set -euo pipefail

# Scripts directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATES_DIR="${REPO_ROOT}/templates"

# Load .env if present
if [ -f "${REPO_ROOT}/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "${REPO_ROOT}/.env" | xargs)
fi

# Fallback defaults
export STRATA_HOST="${STRATA_HOST:-127.0.0.1}"
export STRATA_PORT="${STRATA_PORT:-8080}"
export STRATA_BASE_URL="${STRATA_BASE_URL:-http://${STRATA_HOST}:${STRATA_PORT}/v1}"
export STRATA_MODEL="${STRATA_MODEL:-qwen3.8-flash-next-coder-iq1_m}"
export STRATA_CONTEXT_WINDOW="${STRATA_CONTEXT_WINDOW:-131072}"
export STRATA_MAX_TOKENS="${STRATA_MAX_TOKENS:-4096}"
export STRATA_API_KEY="${STRATA_API_KEY:-none}"

BIN_DIR="${HOME}/.local/bin"
mkdir -p "${BIN_DIR}"

echo "=== 1. Checking / Installing Agent Binaries ==="

# 1. Crush
if command -v crush >/dev/null 2>&1; then
  echo "Crush is already installed at: $(command -v crush)"
else
  echo "Installing Crush CLI to ${BIN_DIR}/crush..."
  CRUSH_VERSION="0.98.2"
  CRUSH_TAR="/tmp/crush_${CRUSH_VERSION}_Linux_x86_64.tar.gz"
  curl -fsSL "https://github.com/charmbracelet/crush/releases/download/v${CRUSH_VERSION}/crush_${CRUSH_VERSION}_Linux_x86_64.tar.gz" -o "${CRUSH_TAR}"
  tar -xzf "${CRUSH_TAR}" -C /tmp/ "crush_${CRUSH_VERSION}_Linux_x86_64/crush"
  mv "/tmp/crush_${CRUSH_VERSION}_Linux_x86_64/crush" "${BIN_DIR}/crush"
  chmod +x "${BIN_DIR}/crush"
  rm -rf "${CRUSH_TAR}" "/tmp/crush_${CRUSH_VERSION}_Linux_x86_64"
  echo "Installed Crush successfully."
fi

# 2. Goose
if command -v goose >/dev/null 2>&1; then
  echo "Goose is already installed at: $(command -v goose)"
else
  echo "Installing Goose CLI to ${BIN_DIR}/goose..."
  GOOSE_BIN_DIR="${BIN_DIR}" CONFIGURE=false bash "${REPO_ROOT}/../goose/download_cli.sh" || {
    curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | GOOSE_BIN_DIR="${BIN_DIR}" CONFIGURE=false bash
  }
  echo "Installed Goose successfully."
fi

# 3. Pi
if command -v pi >/dev/null 2>&1; then
  echo "Pi is already installed at: $(command -v pi)"
else
  echo "Installing Pi CLI via npm..."
  npm install -g --ignore-scripts @earendil-works/pi-coding-agent
  echo "Installed Pi successfully."
fi

echo "=== 2. Rendering Agent Configurations from Templates ==="

# Python template renderer to safely substitute vars
render_template() {
  local src="$1"
  local dest="$2"
  python3 -c "
import os, string, sys
with open(sys.argv[1], 'r') as f:
    template = string.Template(f.read())
rendered = template.safe_substitute(os.environ)
with open(sys.argv[2], 'w') as f:
    f.write(rendered)
" "$src" "$dest"
}

# --- Crush Config ---
CRUSH_CONFIG_DIR="${HOME}/.config/crush"
mkdir -p "${CRUSH_CONFIG_DIR}"
render_template "${TEMPLATES_DIR}/crushrc.template" "${CRUSH_CONFIG_DIR}/crushrc"
echo "Rendered Crush config: ${CRUSH_CONFIG_DIR}/crushrc"

# --- Goose Config ---
GOOSE_CONFIG_DIR="${HOME}/.config/goose"
mkdir -p "${GOOSE_CONFIG_DIR}/custom_providers"
render_template "${TEMPLATES_DIR}/goose_config.yaml.template" "${GOOSE_CONFIG_DIR}/config.yaml"
render_template "${TEMPLATES_DIR}/goose_provider_strata.json.template" "${GOOSE_CONFIG_DIR}/custom_providers/strata.json"
echo "Rendered Goose config: ${GOOSE_CONFIG_DIR}/config.yaml"
echo "Rendered Goose custom provider: ${GOOSE_CONFIG_DIR}/custom_providers/strata.json"

# --- Pi Config ---
PI_AGENT_DIR="${HOME}/.pi/agent"
mkdir -p "${PI_AGENT_DIR}"

python3 -c "
import json, os, string
from pathlib import Path

models_template_path = Path('${TEMPLATES_DIR}/pi_models.json.template')
models_path = Path('${PI_AGENT_DIR}/models.json')
settings_path = Path('${PI_AGENT_DIR}/settings.json')

with open(models_template_path, 'r') as f:
    rendered_strata = string.Template(f.read()).safe_substitute(os.environ)
strata_provider_obj = json.loads(rendered_strata)

if models_path.exists():
    try:
        with open(models_path, 'r') as f:
            data = json.load(f)
    except Exception:
        data = {'providers': {}}
else:
    data = {'providers': {}}

if 'providers' not in data:
    data['providers'] = {}

data['providers']['strata'] = strata_provider_obj

with open(models_path, 'w') as f:
    json.dump(data, f, indent=2)

if settings_path.exists():
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
    except Exception:
        settings = {}
else:
    settings = {}

settings['defaultProvider'] = 'strata'
settings['defaultModel'] = os.environ.get('STRATA_MODEL', 'qwen3.8-flash-next-coder-iq1_m')

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
"
echo "Configured Pi provider & defaults: ${PI_AGENT_DIR}/models.json and settings.json"

echo "=== Codified configuration completed successfully! ==="
