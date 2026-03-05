#!/usr/bin/env bash
# Generate a new Ansible role skeleton with cross-platform structure.
# Usage: ./scripts/new-role.sh <role-name>

set -euo pipefail

ROLES_DIR="shared/roles"

die() { echo "ERROR: $*" >&2; exit 1; }

# ── Validate input ──────────────────────────────────────────────────
[[ $# -ge 1 ]] || die "Usage: make new-role NAME=<name>"

NAME="$1"

# Must be lowercase kebab-case (letters, digits, hyphens).
[[ "$NAME" =~ ^[a-z][a-z0-9-]*$ ]] || \
    die "Role name must be lowercase kebab-case (letters, digits, hyphens): $NAME"

ROLE_DIR="${ROLES_DIR}/${NAME}"
[[ ! -d "$ROLE_DIR" ]] || die "Role already exists: ${ROLE_DIR}/"

# Convert kebab-case to snake_case for variable names.
VAR_PREFIX="${NAME//-/_}"

# ── Create directory structure ──────────────────────────────────────
mkdir -p "${ROLE_DIR}/defaults" "${ROLE_DIR}/tasks"

# ── defaults/main.yml ──────────────────────────────────────────────
cat > "${ROLE_DIR}/defaults/main.yml" <<EOF
---
# ${NAME} role defaults

# Whether to enable ${NAME} on this machine
${VAR_PREFIX}_enabled: true
EOF

# ── tasks/main.yml ─────────────────────────────────────────────────
cat > "${ROLE_DIR}/tasks/main.yml" <<'OUTER'
---
# ROLE_NAME role

- name: Include OS-specific tasks
  ansible.builtin.include_tasks: "{{ ansible_facts.os_family | lower }}.yml"

# TODO: Add shared (cross-platform) tasks below.
# To add verification, create an entry in scripts/verify-registry.yml.
OUTER
# Stamp the role name into the comment.
sed -i '' "s/ROLE_NAME/${NAME}/" "${ROLE_DIR}/tasks/main.yml" 2>/dev/null || \
    sed -i "s/ROLE_NAME/${NAME}/" "${ROLE_DIR}/tasks/main.yml"

# ── tasks/darwin.yml ───────────────────────────────────────────────
cat > "${ROLE_DIR}/tasks/darwin.yml" <<EOF
---
# macOS-specific tasks for ${NAME}

- name: Install ${NAME} via Homebrew
  community.general.homebrew:
    name: ${NAME}
    state: present
EOF

# ── tasks/debian.yml ───────────────────────────────────────────────
cat > "${ROLE_DIR}/tasks/debian.yml" <<EOF
---
# Linux/Debian-specific tasks for ${NAME}

- name: Install ${NAME}
  ansible.builtin.apt:
    name: ${NAME}
    state: present
  become: true
EOF

# ── Summary ────────────────────────────────────────────────────────
echo "Role '${NAME}' scaffolded at ${ROLE_DIR}/"
echo ""
echo "Generated files:"
find "${ROLE_DIR}" -type f | sort | sed 's/^/  /'
echo ""
echo "Next steps:"
echo "  1. Add to a play file (e.g., macos/plays/02-dev-tools.yml):"
echo "       - role: ${NAME}"
echo "         tags: [${NAME}, dev-tools]"
echo "  2. Edit defaults/main.yml with role-specific variables"
echo "  3. Implement tasks in tasks/*.yml"
echo "  4. Add verification entry to scripts/verify-registry.yml"
echo "  5. Test with: make apply ROLE=${NAME}"
