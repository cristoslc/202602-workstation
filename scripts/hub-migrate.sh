#!/usr/bin/env bash
# shellcheck shell=bash
# Migrate Syncthing+Unison hub to a new server.
# Usage: scripts/hub-migrate.sh <source-host> <dest-host> [--dry-run] [--force]
set -euo pipefail

# ---------------------------------------------------------------------------
# Source guard for testability (bats can source without executing main logic)
# ---------------------------------------------------------------------------
_HUB_MIGRATE_SOURCED=1
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  _HUB_MIGRATE_SOURCED=0
fi

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SYNCTHING_HUB_USER=syncthing
SYNCTHING_CONFIG_DIR="/home/${SYNCTHING_HUB_USER}/.local/state/syncthing"
SYNCTHING_DATA_DIR="/srv/syncthing"
UNISON_DATA_DIR="/srv/code-sync"
KEY_FILES=(cert.pem key.pem)

RSYNC_OPTS=(
  -az                   # archive, compress
  --info=progress2      # overall transfer progress
  --partial             # resume interrupted transfers
  --human-readable      # human-readable sizes
)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
hub_migrate_usage() {
  cat <<'EOF'
Usage: scripts/hub-migrate.sh <source-host> <dest-host> [--dry-run] [--force]

Migrate Syncthing + Unison hub data and identity to a new server.

Phases:
  1. Check SSH connectivity to both hosts
  2. Check disk space on destination
  3. Pre-stage: rsync data directories (non-destructive)
  4. Cutover: stop source, final delta rsync, copy keys+config, start dest
  5. Verify: confirm device ID matches and service is running

Options:
  --dry-run     Preview all phases without making changes
  --force       Skip interactive confirmation (required for non-TTY cutover)

Examples:
  make hub-migrate SOURCE=old-hub DEST=new-hub
  make hub-migrate-dry SOURCE=old-hub DEST=new-hub
  scripts/hub-migrate.sh old-hub new-hub
  scripts/hub-migrate.sh old-hub new-hub --dry-run
  scripts/hub-migrate.sh old-hub new-hub --force
EOF
}

hub_migrate_check_ssh() {
  local source_host="$1" dest_host="$2"

  echo "@@PHASE:check-ssh@@"
  echo "Checking SSH connectivity..."

  if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$source_host" true 2>/dev/null; then
    echo "ERROR: Cannot connect to source host '$source_host' via SSH."
    echo "Ensure SSH key auth is configured and the host is reachable."
    return 1
  fi
  echo "  Source ($source_host): OK"

  if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$dest_host" true 2>/dev/null; then
    echo "ERROR: Cannot connect to dest host '$dest_host' via SSH."
    echo "Ensure SSH key auth is configured and the host is reachable."
    return 1
  fi
  echo "  Dest   ($dest_host): OK"

  echo "@@PHASE_DONE:check-ssh@@"
}

hub_migrate_check_disk_space() {
  local source_host="$1" dest_host="$2"

  echo ""
  echo "@@PHASE:check-disk-space@@"
  echo "Checking disk space..."

  # Get used space on source (kilobytes) for both data dirs
  local source_syncthing_kb source_unison_kb source_total_kb
  source_syncthing_kb="$(ssh -o BatchMode=yes "$source_host" \
    "du -sk ${SYNCTHING_DATA_DIR} 2>/dev/null | cut -f1" 2>/dev/null)" || source_syncthing_kb=0
  [[ -z "$source_syncthing_kb" ]] && source_syncthing_kb=0

  source_unison_kb="$(ssh -o BatchMode=yes "$source_host" \
    "du -sk ${UNISON_DATA_DIR} 2>/dev/null | cut -f1" 2>/dev/null)" || source_unison_kb=0
  [[ -z "$source_unison_kb" ]] && source_unison_kb=0

  source_total_kb=$(( source_syncthing_kb + source_unison_kb ))

  # Get available space on dest (kilobytes) for /srv
  local dest_avail_kb
  dest_avail_kb="$(ssh -o BatchMode=yes "$dest_host" \
    "df -k /srv 2>/dev/null | tail -1 | awk '{print \$4}'" 2>/dev/null)" || dest_avail_kb=0
  [[ -z "$dest_avail_kb" ]] && dest_avail_kb=0

  echo "  Source used:      $(( source_total_kb / 1024 )) MB (syncthing: $(( source_syncthing_kb / 1024 )) MB, unison: $(( source_unison_kb / 1024 )) MB)"
  echo "  Dest available:   $(( dest_avail_kb / 1024 )) MB"
  echo "@@DISK:source_kb:${source_total_kb}@@"
  echo "@@DISK:dest_avail_kb:${dest_avail_kb}@@"

  if [[ "$dest_avail_kb" -lt "$source_total_kb" ]]; then
    echo "ERROR: Destination does not have enough disk space."
    echo "  Need: $(( source_total_kb / 1024 )) MB, Available: $(( dest_avail_kb / 1024 )) MB"
    return 1
  fi

  echo "  Disk space check: OK"
  echo "@@PHASE_DONE:check-disk-space@@"
}

hub_migrate_pre_stage() {
  local source_host="$1" dest_host="$2" dry_run="$3"

  echo ""
  echo "@@PHASE:pre-stage@@"
  echo "Pre-staging data directories..."

  local rsync_extra=()
  if [[ "$dry_run" == "true" ]]; then
    rsync_extra+=(--dry-run)
    echo "  (dry-run mode — no data will be copied)"
  fi

  # Pre-stage Syncthing data
  echo ""
  echo "@@RSYNC_START:syncthing-data@@"
  echo "=== Syncing ${SYNCTHING_DATA_DIR} from ${source_host} to ${dest_host} ==="
  rsync "${RSYNC_OPTS[@]}" "${rsync_extra[@]}" \
    -e ssh "${source_host}:${SYNCTHING_DATA_DIR}/" \
    --rsync-path="rsync" \
    --rsh="ssh -o BatchMode=yes" \
    -e "ssh -A" \
    "${dest_host}:${SYNCTHING_DATA_DIR}/" 2>&1 || {
      # Direct host-to-host rsync may not work; fall back to relay through local
      echo "  Direct rsync failed, relaying through local machine..."
      local tmpdir
      tmpdir="$(mktemp -d)"
      rsync "${RSYNC_OPTS[@]}" "${rsync_extra[@]}" \
        "${source_host}:${SYNCTHING_DATA_DIR}/" "${tmpdir}/"
      rsync "${RSYNC_OPTS[@]}" "${rsync_extra[@]}" \
        "${tmpdir}/" "${dest_host}:${SYNCTHING_DATA_DIR}/"
      rm -rf "$tmpdir"
    }
  echo "@@RSYNC_DONE:syncthing-data@@"

  # Pre-stage Unison data
  echo ""
  echo "@@RSYNC_START:unison-data@@"
  echo "=== Syncing ${UNISON_DATA_DIR} from ${source_host} to ${dest_host} ==="
  rsync "${RSYNC_OPTS[@]}" "${rsync_extra[@]}" \
    "${source_host}:${UNISON_DATA_DIR}/" \
    "${dest_host}:${UNISON_DATA_DIR}/" 2>&1 || {
      echo "  Direct rsync failed, relaying through local machine..."
      local tmpdir
      tmpdir="$(mktemp -d)"
      rsync "${RSYNC_OPTS[@]}" "${rsync_extra[@]}" \
        "${source_host}:${UNISON_DATA_DIR}/" "${tmpdir}/"
      rsync "${RSYNC_OPTS[@]}" "${rsync_extra[@]}" \
        "${tmpdir}/" "${dest_host}:${UNISON_DATA_DIR}/"
      rm -rf "$tmpdir"
    }
  echo "@@RSYNC_DONE:unison-data@@"

  echo ""
  echo "@@PHASE_DONE:pre-stage@@"
}

hub_migrate_cutover() {
  local source_host="$1" dest_host="$2"

  echo ""
  echo "@@PHASE:cutover@@"
  echo "Beginning cutover..."

  # Step 1: Stop Syncthing on source
  echo "  Stopping Syncthing on ${source_host}..."
  ssh -o BatchMode=yes "$source_host" \
    "sudo systemctl stop syncthing@${SYNCTHING_HUB_USER}" 2>/dev/null
  echo "@@CUTOVER:source-stopped@@"

  # Step 2: Final delta rsync for Syncthing data
  echo "  Final delta rsync for ${SYNCTHING_DATA_DIR}..."
  rsync "${RSYNC_OPTS[@]}" \
    "${source_host}:${SYNCTHING_DATA_DIR}/" \
    "${dest_host}:${SYNCTHING_DATA_DIR}/" 2>&1 || {
      local tmpdir
      tmpdir="$(mktemp -d)"
      rsync "${RSYNC_OPTS[@]}" \
        "${source_host}:${SYNCTHING_DATA_DIR}/" "${tmpdir}/"
      rsync "${RSYNC_OPTS[@]}" \
        "${tmpdir}/" "${dest_host}:${SYNCTHING_DATA_DIR}/"
      rm -rf "$tmpdir"
    }

  # Step 3: Final delta rsync for Unison data
  echo "  Final delta rsync for ${UNISON_DATA_DIR}..."
  rsync "${RSYNC_OPTS[@]}" \
    "${source_host}:${UNISON_DATA_DIR}/" \
    "${dest_host}:${UNISON_DATA_DIR}/" 2>&1 || {
      local tmpdir
      tmpdir="$(mktemp -d)"
      rsync "${RSYNC_OPTS[@]}" \
        "${source_host}:${UNISON_DATA_DIR}/" "${tmpdir}/"
      rsync "${RSYNC_OPTS[@]}" \
        "${tmpdir}/" "${dest_host}:${UNISON_DATA_DIR}/"
      rm -rf "$tmpdir"
    }

  # Step 4: Copy Syncthing identity keys and config
  echo "  Copying Syncthing identity keys..."
  local tmpkeys
  tmpkeys="$(mktemp -d)"
  for keyfile in "${KEY_FILES[@]}"; do
    scp -o BatchMode=yes "${source_host}:${SYNCTHING_CONFIG_DIR}/${keyfile}" "${tmpkeys}/${keyfile}"
    scp -o BatchMode=yes "${tmpkeys}/${keyfile}" "${dest_host}:${SYNCTHING_CONFIG_DIR}/${keyfile}"
  done

  echo "  Copying Syncthing config..."
  scp -o BatchMode=yes "${source_host}:${SYNCTHING_CONFIG_DIR}/config.xml" "${tmpkeys}/config.xml"
  scp -o BatchMode=yes "${tmpkeys}/config.xml" "${dest_host}:${SYNCTHING_CONFIG_DIR}/config.xml"
  rm -rf "$tmpkeys"
  echo "@@CUTOVER:keys-copied@@"

  # Step 5: Fix ownership on dest
  echo "  Fixing ownership on ${dest_host}..."
  ssh -o BatchMode=yes "$dest_host" \
    "sudo chown -R ${SYNCTHING_HUB_USER}:${SYNCTHING_HUB_USER} ${SYNCTHING_CONFIG_DIR} ${SYNCTHING_DATA_DIR} ${UNISON_DATA_DIR}"
  echo "@@CUTOVER:ownership-fixed@@"

  # Step 6: Start Syncthing on dest
  echo "  Starting Syncthing on ${dest_host}..."
  ssh -o BatchMode=yes "$dest_host" \
    "sudo systemctl start syncthing@${SYNCTHING_HUB_USER}" 2>/dev/null
  echo "@@CUTOVER:dest-started@@"

  echo "@@PHASE_DONE:cutover@@"
}

hub_migrate_verify() {
  local source_host="$1" dest_host="$2"

  echo ""
  echo "@@PHASE:verify@@"
  echo "Verifying migration..."

  # Get source device ID (Syncthing is stopped, read from cert)
  local source_device_id
  source_device_id="$(ssh -o BatchMode=yes "$source_host" \
    "syncthing --device-id 2>/dev/null || echo UNKNOWN")" || source_device_id="UNKNOWN"

  # Get dest device ID
  local dest_device_id
  dest_device_id="$(ssh -o BatchMode=yes "$dest_host" \
    "syncthing --device-id 2>/dev/null || echo UNKNOWN")" || dest_device_id="UNKNOWN"

  echo "  Source device ID: ${source_device_id}"
  echo "  Dest device ID:   ${dest_device_id}"
  echo "@@VERIFY:source_id:${source_device_id}@@"
  echo "@@VERIFY:dest_id:${dest_device_id}@@"

  if [[ "$source_device_id" != "UNKNOWN" && "$dest_device_id" != "UNKNOWN" ]]; then
    if [[ "$source_device_id" == "$dest_device_id" ]]; then
      echo "  Device ID match: OK"
      echo "@@VERIFY:id_match:true@@"
    else
      echo "  WARNING: Device IDs do not match. Spokes will need to re-pair."
      echo "@@VERIFY:id_match:false@@"
    fi
  else
    echo "  WARNING: Could not verify device IDs."
    echo "@@VERIFY:id_match:unknown@@"
  fi

  # Check if Syncthing is running on dest
  local dest_service_status
  dest_service_status="$(ssh -o BatchMode=yes "$dest_host" \
    "systemctl is-active syncthing@${SYNCTHING_HUB_USER} 2>/dev/null")" || dest_service_status="unknown"

  echo "  Dest Syncthing service: ${dest_service_status}"
  echo "@@VERIFY:dest_service:${dest_service_status}@@"

  if [[ "$dest_service_status" == "active" ]]; then
    echo "  Service running: OK"
  else
    echo "  WARNING: Syncthing is not active on dest. Check with: ssh ${dest_host} systemctl status syncthing@${SYNCTHING_HUB_USER}"
  fi

  echo "@@PHASE_DONE:verify@@"
}

hub_migrate_main() {
  local source_host="${1:-}"
  local dest_host="${2:-}"
  local dry_run="false"
  local force="false"

  if [[ -z "$source_host" || -z "$dest_host" ]]; then
    hub_migrate_usage
    exit 1
  fi

  shift 2
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      --force)   force="true"; shift ;;
      -h|--help) hub_migrate_usage; exit 0 ;;
      *) echo "Unknown option: $1"; hub_migrate_usage; exit 1 ;;
    esac
  done

  echo "=== Hub Migration ==="
  echo "Source: ${source_host}"
  echo "Dest:   ${dest_host}"
  if [[ "$dry_run" == "true" ]]; then
    echo "Mode:   DRY RUN"
  else
    echo "Mode:   LIVE"
  fi
  echo ""

  # Phase 1: Check SSH
  hub_migrate_check_ssh "$source_host" "$dest_host"

  # Phase 2: Check disk space
  hub_migrate_check_disk_space "$source_host" "$dest_host"

  # Phase 3: Pre-stage
  hub_migrate_pre_stage "$source_host" "$dest_host" "$dry_run"

  # Phase 4: Cutover
  if [[ "$dry_run" == "true" ]]; then
    echo ""
    echo "@@PHASE:cutover-preview@@"
    echo "=== DRY RUN — cutover would perform: ==="
    echo "  1. Stop Syncthing on ${source_host}"
    echo "  2. Final delta rsync of ${SYNCTHING_DATA_DIR} and ${UNISON_DATA_DIR}"
    echo "  3. Copy identity keys (${KEY_FILES[*]}) and config.xml"
    echo "  4. Fix ownership to ${SYNCTHING_HUB_USER} on ${dest_host}"
    echo "  5. Start Syncthing on ${dest_host}"
    echo "@@PHASE_DONE:cutover-preview@@"
    echo ""
    echo "=== DRY RUN complete. No destructive changes were made. ==="
    return 0
  fi

  # Interactive confirmation: TTY vs non-TTY
  if [[ -t 0 ]]; then
    # stdin is a TTY — prompt interactively
    echo ""
    echo "Ready to cut over? This will stop Syncthing on ${source_host}. [y/N]"
    local confirm
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
      echo "Cutover aborted by user."
      return 1
    fi
  else
    # stdin is NOT a TTY — require --force
    if [[ "$force" != "true" ]]; then
      echo ""
      echo "ERROR: Non-interactive mode detected. Use --force to proceed with cutover."
      echo "  scripts/hub-migrate.sh ${source_host} ${dest_host} --force"
      return 1
    fi
    echo ""
    echo "Non-interactive mode with --force — proceeding with cutover."
  fi

  hub_migrate_cutover "$source_host" "$dest_host"

  # Phase 5: Verify
  hub_migrate_verify "$source_host" "$dest_host"

  echo ""
  echo "=== Hub migration from ${source_host} to ${dest_host} complete. ==="
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if [[ "$_HUB_MIGRATE_SOURCED" -eq 0 ]]; then
  hub_migrate_main "$@"
fi
