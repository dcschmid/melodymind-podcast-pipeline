#!/usr/bin/env bash
# Reproducible Miniconda + environment setup for MelodyMind Podcast Pipeline
# Usage: bash scripts/setup_conda.sh


set -euo pipefail

MINICONDA_DIR="${HOME}/miniconda3"
INSTALLER="${HOME}/miniconda.sh"
ENV_NAME="melodymind"

DOWNLOAD_MODELS=0
AUTO_YES=0

print_usage(){
  cat <<USAGE
Usage: $0 [--download-models] [-y|--yes]

Options:
  --download-models   After cloning SadTalker, run its model download script (large files).
  -y, --yes           Auto-confirm prompts (non-interactive).
USAGE
}

echo "[setup] Starting setup_conda.sh"

# simple arg parse
while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --download-models)
      DOWNLOAD_MODELS=1; shift ;;
    -y|--yes)
      AUTO_YES=1; shift ;;
    -h|--help)
      print_usage; exit 0 ;;
    *)
      echo "Unknown option: $1"; print_usage; exit 1 ;;
  esac
done

# If conda not present, install Miniconda silently to $MINICONDA_DIR
if ! command -v conda >/dev/null 2>&1; then
  echo "[setup] Downloading Miniconda installer..."
  curl -fsSL -o "${INSTALLER}" https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  echo "[setup] Installing Miniconda to ${MINICONDA_DIR} (silent)..."
  bash "${INSTALLER}" -b -p "${MINICONDA_DIR}"

  # Initialize conda for this shell session
  echo "[setup] Initializing conda in this shell..."
  eval "\$(${MINICONDA_DIR}/bin/conda shell.bash hook)"
  conda init >/dev/null 2>&1 || true
  # Try to source the user's .bashrc (best effort)
  if [ -f "${HOME}/.bashrc" ]; then
    # shellcheck disable=SC1090
    . "${HOME}/.bashrc" || true
  fi

  echo "[setup] Cleaning up installer"
  rm -f "${INSTALLER}"
else
  echo "[setup] conda already on PATH — skipping Miniconda install"
  eval "\$(conda shell.bash hook)"
fi

# Create environment if it doesn't exist
if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "[setup] conda env '${ENV_NAME}' already exists. Skipping creation."
else
  echo "[setup] Creating conda env '${ENV_NAME}' (Python 3.10)"
  conda create -n "${ENV_NAME}" python=3.10 -y
fi

echo "[setup] Activating '${ENV_NAME}'"
# shellcheck disable=SC1091
conda activate "${ENV_NAME}"

echo "[setup] Installing ffmpeg and git from conda-forge"
conda install -c conda-forge ffmpeg git -y

echo "[setup] Installing Python requirements for pipeline"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "${REPO_ROOT}/requirements.txt" ]; then
  pip install -r "${REPO_ROOT}/requirements.txt"
else
  echo "[setup] Warning: requirements.txt not found at ${REPO_ROOT}. Skipping pip install."
fi

# Optionally clone SadTalker skeleton (do NOT auto-download large models unless requested)
if [ ! -d "${REPO_ROOT}/SadTalker" ]; then
  echo "[setup] Cloning SadTalker repository into ${REPO_ROOT}/SadTalker"
  git clone https://github.com/OpenTalker/SadTalker.git "${REPO_ROOT}/SadTalker"
else
  echo "[setup] SadTalker already exists — skipping clone"
fi

# If requested, optionally run SadTalker model downloader (these are large files)
if [ "${DOWNLOAD_MODELS}" -eq 1 ]; then
  if [ ! -d "${REPO_ROOT}/SadTalker" ]; then
    echo "[setup] SadTalker directory missing; cannot download models."
  else
    echo "[setup] You asked to download SadTalker models. This will fetch model files which can be large (hundreds of MBs to several GB)."
    if [ "${AUTO_YES}" -eq 1 ]; then
      CONFIRMED=1
    else
      read -r -p "Proceed with downloading SadTalker models now? [y/N] " resp
      case "$resp" in
        [yY]|[yY][eE][sS]) CONFIRMED=1 ;;
        *) CONFIRMED=0 ;;
      esac
    fi
    if [ "${CONFIRMED}" -eq 1 ]; then
      echo "[setup] Running SadTalker model downloader (this may take a while)"
      (cd "${REPO_ROOT}/SadTalker" && bash scripts/download_models.sh)
      echo "[setup] SadTalker model download finished"
    else
      echo "[setup] Skipped SadTalker model download"
    fi
  fi
fi

echo
echo "[setup] Done. Next steps:"
echo "  - To deactivate environment:   conda deactivate"
echo "  - To remove environment:       conda remove -n ${ENV_NAME} --all"
echo "  - To download SadTalker models: cd SadTalker && bash scripts/download_models.sh"
echo
echo "[setup] Completed successfully"

exit 0
