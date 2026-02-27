#!/usr/bin/env bash
set -euo pipefail

# Export a clean template copy of this repo to a sibling directory.
# Strips personalized content (age keys, repo URLs, encrypted secrets)
# and creates a fresh single-commit git history.
#
# Usage: ./scripts/templatize.sh [target-dir]
#   Default target: ../workstation-template

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${1:-$(dirname "$REPO_DIR")/workstation-template}"

# --- Personalized values to strip ---
# After first-run personalizes the repo, fill these in to re-export a clean template.
AGE_PUBLIC_KEY="${AGE_PUBLIC_KEY:?Set AGE_PUBLIC_KEY to your age public key}"
GITHUB_REPO_URL="${GITHUB_REPO_URL:?Set GITHUB_REPO_URL to your repo clone URL}"
GITHUB_USERNAME="${GITHUB_USERNAME:?Set GITHUB_USERNAME to your GitHub username}"
REPO_NAME="${REPO_NAME:?Set REPO_NAME to your repo name}"

# --- Phase 1: Validate ---

echo "==> Validating..."

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "ERROR: $REPO_DIR is not a git repository."
  exit 1
fi

if [ -e "$TARGET_DIR" ]; then
  echo "ERROR: Target directory already exists: $TARGET_DIR"
  echo "       Remove it first if you want to re-export."
  exit 1
fi

# --- Phase 2: Copy tracked files ---

echo "==> Copying tracked files to $TARGET_DIR..."
mkdir -p "$TARGET_DIR"
cd "$REPO_DIR"
git ls-files -z | cpio -0 -pdm "$TARGET_DIR" 2>/dev/null

# --- Phase 3: De-personalize tokens ---

echo "==> Replacing personalized values with template tokens..."

# .sops.yaml — replace age public key.
sed -i "s|${AGE_PUBLIC_KEY}|\${AGE_PUBLIC_KEY}|g" "$TARGET_DIR/.sops.yaml"

# setup.sh — replace repo URL.
sed -i "s|${GITHUB_REPO_URL}|\${GITHUB_REPO_URL}|g" "$TARGET_DIR/setup.sh"

# bootstrap.sh — replace repo URL.
sed -i "s|${GITHUB_REPO_URL}|\${GITHUB_REPO_URL}|g" "$TARGET_DIR/bootstrap.sh"

# README.md — replace repo URL, username, repo name.
# Title line must be replaced before REPO_NAME to avoid partial match.
sed -i "s|^# ${REPO_NAME}$|# \${REPO_NAME}|" "$TARGET_DIR/README.md"
sed -i "s|${GITHUB_REPO_URL}|\${GITHUB_REPO_URL}|g" "$TARGET_DIR/README.md"
sed -i "s|${GITHUB_USERNAME}|\${GITHUB_USERNAME}|g" "$TARGET_DIR/README.md"
sed -i "s|${REPO_NAME}|\${REPO_NAME}|g" "$TARGET_DIR/README.md"

# --- Phase 4: Replace encrypted secrets with plaintext placeholders ---

echo "==> Writing plaintext secret placeholders..."

cat > "$TARGET_DIR/shared/secrets/vars.sops.yml" << 'YAML'
---
# Shared secrets — replaced during first-run personalization.
# These values are encrypted with your age key after setup.
git_user_email: PLACEHOLDER
git_user_name: PLACEHOLDER
git_signing_key: PLACEHOLDER
YAML

cat > "$TARGET_DIR/linux/secrets/vars.sops.yml" << 'YAML'
---
# Linux secrets — replaced during first-run personalization.
# Add platform-specific secret variables here.
placeholder: true
YAML

cat > "$TARGET_DIR/macos/secrets/vars.sops.yml" << 'YAML'
---
# macOS secrets — replaced during first-run personalization.
# Add platform-specific secret variables here.
placeholder: true
YAML

cat > "$TARGET_DIR/shared/secrets/dotfiles/zsh/.config/zsh/secrets.zsh.sops" << 'SHELL'
# shellcheck shell=bash
# Shell secrets — sourced by .zshrc
# Replace PLACEHOLDER values with real API keys, then encrypt with SOPS.

export ANTHROPIC_API_KEY="PLACEHOLDER"
export OPENAI_API_KEY="PLACEHOLDER"
SHELL

mkdir -p "$TARGET_DIR/linux/secrets/dotfiles/espanso/.config/espanso/match"
cat > "$TARGET_DIR/linux/secrets/dotfiles/espanso/.config/espanso/match/private.yml.sops" << 'YAML'
# Espanso private matches — encrypted with SOPS.
# Add your personal text expansions here, then encrypt.
matches:
  - trigger: ":placeholder"
    replace: "Replace this with your expansion"
YAML

# --- Phase 5: Fix token system in template copy ---
# state.py and tokens.py are already correct in the source (we just fixed them).
# No additional patching needed — the template inherits the fixed code.

# --- Phase 6: Git init + commit ---

echo "==> Initializing fresh git history..."
cd "$TARGET_DIR"
git init -q
git add -A
git -c commit.gpgsign=false commit -q -m "Initial template

Clean template export with all personalized content
replaced by template tokens. Fork this repo and run ./setup.sh to personalize."

# --- Phase 7: Verify ---

echo "==> Verifying template..."
ERRORS=0

# Check for leaked personal content.
if grep -rq "$GITHUB_USERNAME" --include='*.sh' --include='*.yml' --include='*.yaml' --include='*.md' --include='*.py' "$TARGET_DIR" 2>/dev/null; then
  echo "WARNING: Found '$GITHUB_USERNAME' in template files:"
  grep -rn "$GITHUB_USERNAME" --include='*.sh' --include='*.yml' --include='*.yaml' --include='*.md' --include='*.py' "$TARGET_DIR" || true
  ERRORS=$((ERRORS + 1))
fi

if grep -rq "$AGE_PUBLIC_KEY" "$TARGET_DIR" 2>/dev/null; then
  echo "WARNING: Found age public key in template files."
  ERRORS=$((ERRORS + 1))
fi

# Confirm template tokens exist.
if ! grep -q '\${AGE_PUBLIC_KEY}' "$TARGET_DIR/.sops.yaml"; then
  echo "ERROR: \${AGE_PUBLIC_KEY} token missing from .sops.yaml"
  ERRORS=$((ERRORS + 1))
fi

if ! grep -q '\${GITHUB_REPO_URL}' "$TARGET_DIR/setup.sh"; then
  echo "ERROR: \${GITHUB_REPO_URL} token missing from setup.sh"
  ERRORS=$((ERRORS + 1))
fi

if ! grep -q '\${GITHUB_REPO_URL}' "$TARGET_DIR/bootstrap.sh"; then
  echo "ERROR: \${GITHUB_REPO_URL} token missing from bootstrap.sh"
  ERRORS=$((ERRORS + 1))
fi

if ! grep -q '\${GITHUB_REPO_URL}' "$TARGET_DIR/README.md"; then
  echo "ERROR: \${GITHUB_REPO_URL} token missing from README.md"
  ERRORS=$((ERRORS + 1))
fi

# Confirm secrets are plaintext (no SOPS encryption blocks).
if grep -rq 'ENC\[AES256_GCM' "$TARGET_DIR/shared/secrets/" "$TARGET_DIR/linux/secrets/" "$TARGET_DIR/macos/secrets/" 2>/dev/null; then
  echo "ERROR: Found SOPS-encrypted content in secrets — should be plaintext."
  ERRORS=$((ERRORS + 1))
fi

if [ "$ERRORS" -gt 0 ]; then
  echo ""
  echo "Template export completed with $ERRORS warning(s). Review above."
  exit 1
fi

echo ""
echo "Template exported successfully to: $TARGET_DIR"
echo "  - $(cd "$TARGET_DIR" && git log --oneline | wc -l) commit(s)"
echo "  - $(cd "$TARGET_DIR" && git ls-files | wc -l) files"
echo ""
echo "Next steps:"
echo "  cd $TARGET_DIR"
echo "  gh repo create <username>/<repo-name> --public --source . --push"
