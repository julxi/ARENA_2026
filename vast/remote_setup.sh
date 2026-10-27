#!/bin/bash
# Builds the ARENA venv on a rented vast.ai machine. Run over ssh by `vast/arena_vast.py up`, inside a
# time budget (the host is rejected if the install is too slow). Safe to re-run by hand:
#   bash -l /root/ARENA_2026/vast/remote_setup.sh
#
# This is the part of install_uv.sh that a vast.ai base image still needs. Intentionally left out:
# installing uv (Julian wants the image's own uv: installing one would hide that the image is not the
# one we think we rented) and the apt install of git/curl (the vastai/base-image images ship both).
# install_uv.sh writes VS Code settings into ~/.vscode for opening /root as the folder; here they go
# into the repo's own .vscode instead, because arena_vast.py opens VS Code on the repo folder.
set -euo pipefail

PYTHON_VERSION="3.13"
KERNEL_NAME="arena-env"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"

for tool in uv git; do
    command -v "$tool" >/dev/null || { echo "$tool is not installed in this image" >&2; exit 1; }
done
echo "=== Using $(uv --version) ==="

# Same marker logic as install_uv.sh: the marker is written only after every dependency installed, so a
# missing marker means an earlier run was interrupted and the venv is rebuilt rather than trusted.
INSTALL_MARKER="$VENV_DIR/.arena-install-complete"
if [[ -f "$INSTALL_MARKER" ]] && "$VENV_DIR/bin/python" -c "import sys; assert sys.version.startswith('$PYTHON_VERSION.')" 2>/dev/null; then
    echo "=== Reusing existing venv at $VENV_DIR ==="
else
    echo "=== Creating venv at $VENV_DIR (python $PYTHON_VERSION) ==="
    uv venv --clear --python "$PYTHON_VERSION" --seed "$VENV_DIR"
fi
rm -f "$INSTALL_MARKER"
echo "=== Installing Python dependencies from $REPO_DIR/requirements.txt ==="
# Copy instead of hardlink: uv's cache and the venv can sit on different filesystems in a container.
uv pip install --link-mode copy --python "$VENV_DIR/bin/python" -r "$REPO_DIR/requirements.txt"
touch "$INSTALL_MARKER"
"$VENV_DIR/bin/python" -m ipykernel install --user --name "$KERNEL_NAME" --display-name "$KERNEL_NAME"

# Appended after whatever the image's .bashrc activates, so this venv wins in new shells.
ACTIVATE_LINE="source $VENV_DIR/bin/activate"
if ! grep -qxF "$ACTIVATE_LINE" "$HOME/.bashrc" 2>/dev/null; then
    echo "$ACTIVATE_LINE" >> "$HOME/.bashrc"
fi
# vast.ai images start tmux in every ssh login shell; the work happens in VS Code terminals instead.
touch "$HOME/.no_auto_tmux"

mkdir -p "$REPO_DIR/.vscode"
cat > "$REPO_DIR/.vscode/settings.json" << EOF
{
    "python.defaultInterpreterPath": "$VENV_DIR/bin/python",
    "python.analysis.extraPaths": [
        "$REPO_DIR/chapter0_fundamentals/exercises",
        "$REPO_DIR/chapter1_transformer_interp/exercises",
        "$REPO_DIR/chapter2_rl/exercises",
        "$REPO_DIR/chapter3_llm_evals/exercises",
        "$REPO_DIR/chapter4_alignment_science/exercises"
    ]
}
EOF
echo "=== Setup done ==="
