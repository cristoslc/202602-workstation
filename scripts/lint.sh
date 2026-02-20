#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

exit_code=0

echo "Running yamllint..."
if command -v yamllint &>/dev/null; then
  yamllint -d relaxed "$REPO_DIR" --no-warnings || exit_code=1
else
  echo "yamllint not installed. Install with: pip install yamllint"
fi

echo ""
echo "Running ansible-lint..."
if command -v ansible-lint &>/dev/null; then
  for platform in linux macos; do
    echo "  Linting $platform..."
    cd "$REPO_DIR/$platform"
    ANSIBLE_CONFIG="$REPO_DIR/$platform/ansible.cfg" ansible-lint site.yml || exit_code=1
  done
else
  echo "ansible-lint not installed. Install with: pip install ansible-lint"
fi

echo ""
if [ "$exit_code" -ne 0 ]; then
  echo "Lint failed."
else
  echo "Lint complete."
fi
exit "$exit_code"
