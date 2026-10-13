#!/usr/bin/env bash
# =============================================================================
# Setup Git Hooks for Suraksha Repository
# Configures pre-commit and pre-push hooks to block secrets
# =============================================================================
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "Configuring Git hooks path to .githooks..."
git config core.hooksPath .githooks

chmod +x .githooks/pre-push .githooks/pre-commit scripts/scan_secrets.py

# Also link/copy to .git/hooks for redundancy
mkdir -p .git/hooks
cp .githooks/pre-push .git/hooks/pre-push
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-push .git/hooks/pre-commit

echo "Git hooks configured successfully!"
echo "  - pre-commit: scans staged changes to prevent secret commits"
echo "  - pre-push:   scans commits being pushed to prevent secret pushes"
