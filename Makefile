SHELL := /bin/bash
PLATFORM := $(shell uname -s | tr '[:upper:]' '[:lower:]')
ifeq ($(PLATFORM),darwin)
  PLATFORM_DIR := macos
else
  PLATFORM_DIR := linux
endif

WORKSTATION_DIR ?= $(HOME)/.workstation
ANSIBLE_CONFIG := $(CURDIR)/$(PLATFORM_DIR)/ansible.cfg
export ANSIBLE_CONFIG

# SOPS looks for age keys at ~/Library/Application Support/sops/age/ on macOS,
# but we store them at ~/.config/sops/age/ (XDG convention). Tell SOPS where to look.
SOPS_AGE_KEY_FILE ?= $(HOME)/.config/sops/age/keys.txt
export SOPS_AGE_KEY_FILE

# Ensure uv and other ~/.local/bin tools are on PATH (uv installs there).
export PATH := $(HOME)/.local/bin:$(PATH)

CHECK_LOG ?= check.log

# Restic backup defaults for make targets
RESTIC_STALE_HOURS ?= 8
RESTIC_B2_BUCKET ?= $(shell cat $(HOME)/.config/restic/bucket-name 2>/dev/null)

.PHONY: help setup first-run bootstrap lint shellcheck yamllint ansible-lint \
        check-collisions check-sync check-playbook test test-bats test-python check apply \
        decrypt clean-secrets status template-export \
        edit-secrets-shared edit-secrets-linux edit-secrets-macos \
        key-export key-import key-send key-receive \
        log-send log-receive iterm2-export raycast-export streamdeck-export export-all \
        backup-status backup-browse \
        data-pull data-pull-dry

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Setup wizard (Textual TUI — replaces first-run + bootstrap)
	./setup.sh

first-run: ## One-time repo setup (age key, encrypt secrets, GitHub remote)
	./first-run.sh

bootstrap: ## Run full bootstrap for this platform (via TUI)
	./setup.sh --bootstrap

lint: ## Run all linters (yamllint, shellcheck, ansible-lint, collisions)
	./scripts/lint.sh

yamllint: ## Run yamllint on all YAML files
	yamllint . --no-warnings

shellcheck: ## Run shellcheck on all shell scripts
	shellcheck --severity=warning \
		setup.sh bootstrap.sh first-run.sh \
		linux/bootstrap.sh macos/bootstrap.sh \
		shared/lib/wizard.sh scripts/*.sh scripts/wsync

ansible-lint: ## Run ansible-lint on all playbooks (SOPS disabled)
	ANSIBLE_VARS_ENABLED=host_group_vars ANSIBLE_CONFIG=$(CURDIR)/linux/ansible.cfg ansible-lint linux/site.yml
	ANSIBLE_VARS_ENABLED=host_group_vars ANSIBLE_CONFIG=$(CURDIR)/macos/ansible.cfg ansible-lint macos/site.yml

apply: ## Apply a specific role: make apply ROLE=git (or ROLE=gh for sub-task)
ifndef ROLE
	$(error ROLE is required. Usage: make apply ROLE=git)
endif
	./scripts/apply-role.sh $(PLATFORM_DIR) $(ROLE)

decrypt: ## Decrypt all SOPS files to .decrypted/ dirs
	@echo "Decrypting shared secrets..."
	@./scripts/decrypt-secrets.sh shared/secrets
	@echo "Decrypting $(PLATFORM_DIR) secrets..."
	@./scripts/decrypt-secrets.sh $(PLATFORM_DIR)/secrets

clean-secrets: ## Wipe decrypted secrets, unstow symlinks, truncate Ansible log
	# NOTE: rm does not securely erase data on SSDs. This is acceptable assuming
	# full-disk encryption (FileVault on macOS, LUKS on Linux) is enabled.
	# Unstow secret dotfile packages so symlinks don't dangle.
	@for secrets_dotfiles in shared/secrets/.decrypted/dotfiles $(PLATFORM_DIR)/secrets/.decrypted/dotfiles; do \
		if [ -d "$(WORKSTATION_DIR)/$$secrets_dotfiles" ]; then \
			stow -D -d "$(WORKSTATION_DIR)/$$(dirname $$secrets_dotfiles)" -t "$(HOME)" "$$(basename $$secrets_dotfiles)" 2>/dev/null || true; \
		fi; \
	done
	find . -type d -name '.decrypted' -exec rm -rf {} + 2>/dev/null || true
	# Truncate Ansible log (may contain token values from prior runs).
	@: > "$(HOME)/.local/log/ansible.log" 2>/dev/null || true
	@echo "Decrypted secrets, stow symlinks, and Ansible log cleaned."

edit-secrets-shared: ## Edit shared encrypted vars
	sops shared/secrets/vars.sops.yml

edit-secrets-linux: ## Edit Linux encrypted vars
	sops linux/secrets/vars.sops.yml

edit-secrets-macos: ## Edit macOS encrypted vars
	sops macos/secrets/vars.sops.yml

status: ## Show workstation status (stub — Rich dashboard planned)
	@uv run --with rich scripts/workstation-status.py 2>/dev/null || echo "Status dashboard requires uv + Python. Run bootstrap first."

check-collisions: ## Check for stow filename collisions between layers
	./scripts/check-stow-collisions.sh

check-sync: ## Check cross-platform settings haven't drifted
	./scripts/check-synced-settings.sh

check-playbook: ## Syntax-check Ansible playbooks (no sudo needed)
	ANSIBLE_VARS_ENABLED=host_group_vars ANSIBLE_CONFIG=$(CURDIR)/linux/ansible.cfg ansible-playbook linux/site.yml --syntax-check
	ANSIBLE_VARS_ENABLED=host_group_vars ANSIBLE_CONFIG=$(CURDIR)/macos/ansible.cfg ansible-playbook macos/site.yml --syntax-check

test-bats: ## Run bats shell unit tests
	bats tests/bats/

test-python: ## Run Python unit tests (first-run wizard + setup TUI)
	uv run --with rich,pyyaml,textual,jinja2,pytest,pytest-asyncio pytest tests/python/ -v

test: lint test-bats test-python ## Run all linters and tests

check: ## Quick local verification (no ansible-lint); writes output to $(CHECK_LOG)
	@echo "Writing check log to: $(CHECK_LOG)"
	@set -euo pipefail; { \
		echo "=== make check started: $$(date '+%Y-%m-%d %H:%M:%S %Z') ==="; \
		$(MAKE) shellcheck; \
		$(MAKE) yamllint; \
		$(MAKE) check-collisions; \
		$(MAKE) check-sync; \
		$(MAKE) check-playbook; \
		$(MAKE) test-bats; \
		$(MAKE) test-python; \
		echo "=== make check completed: $$(date '+%Y-%m-%d %H:%M:%S %Z') ==="; \
	} 2>&1 | tee "$(CHECK_LOG)"

key-send: ## Send age key to another machine via Magic Wormhole
	./scripts/transfer-key.sh send

key-receive: ## Receive age key from another machine via Magic Wormhole
	./scripts/transfer-key.sh receive

key-export: ## Export age key as passphrase-encrypted blob (for AirDrop/paste)
	./scripts/transfer-key.sh export

key-import: ## Import age key from passphrase-encrypted blob
	./scripts/transfer-key.sh import

log-send: ## Send bootstrap.log to another machine via Magic Wormhole
	@test -f bootstrap.log || { echo "No bootstrap.log found. Run make bootstrap first."; exit 1; }
	uv run --with magic-wormhole wormhole send bootstrap.log

log-receive: ## Receive bootstrap.log from another machine via Magic Wormhole
	uv run --with magic-wormhole wormhole receive -o bootstrap.log

export-all: iterm2-export streamdeck-export raycast-export ## Export all settings (macOS only)

iterm2-export: ## Re-export iTerm2 plist to stow package (macOS only)
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	defaults export com.googlecode.iterm2 - | plutil -convert xml1 -o macos/dotfiles/iterm2/.config/iterm2/com.googlecode.iterm2.plist -
	@echo "iTerm2 plist exported. Review with: git diff macos/dotfiles/iterm2/"

raycast-export: ## Export Raycast settings and age-encrypt for the repo (macOS only)
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	@echo "Opening Raycast export UI..."
	@echo "Save the .rayconfig file WITHOUT a password to ~/Downloads (the default)."
	@open "raycast://extensions/raycast/raycast/export-settings-data"
	@read -p "Press Enter after saving the export..."
	@RCFILE=$$(ls -t "$$HOME"/Downloads/*.rayconfig 2>/dev/null | head -1); \
	if [ -z "$$RCFILE" ]; then echo "No .rayconfig found in ~/Downloads"; exit 1; fi; \
	echo "Found: $$RCFILE"; \
	AGE_PUBKEY=$$(grep -oE 'age1[a-z0-9]+' .sops.yaml | head -1); \
	age -r "$$AGE_PUBKEY" -o macos/files/raycast/raycast.rayconfig.age "$$RCFILE"; \
	rm -f "$$RCFILE"; \
	echo "Raycast export encrypted. Review with: git diff --stat macos/files/raycast/"

streamdeck-export: ## Export Stream Deck profiles (age-encrypted, macOS only)
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	@SD_BACKUP="$$HOME/Library/Application Support/com.elgato.StreamDeck/BackupV3"; \
	SDFILE=$$(ls -t "$$SD_BACKUP"/*.streamDeckProfilesBackup 2>/dev/null | head -1); \
	if [ -z "$$SDFILE" ]; then echo "No Stream Deck backup found in BackupV3/"; exit 1; fi; \
	echo "Found: $$SDFILE"; \
	AGE_PUBKEY=$$(grep -oE 'age1[a-z0-9]+' .sops.yaml | head -1); \
	age -r "$$AGE_PUBKEY" -o macos/files/stream-deck/streamdeck.backup.age "$$SDFILE"; \
	echo "Stream Deck profiles encrypted. Review with: git diff --stat macos/files/stream-deck/"

data-pull: ## Bulk-copy user data from another machine: make data-pull SOURCE=<hostname>
ifndef SOURCE
	$(error SOURCE is required. Usage: make data-pull SOURCE=desktop)
endif
	./scripts/data-pull.sh $(SOURCE)

data-pull-dry: ## Preview data pull without copying: make data-pull-dry SOURCE=<hostname>
ifndef SOURCE
	$(error SOURCE is required. Usage: make data-pull-dry SOURCE=desktop)
endif
	./scripts/data-pull.sh $(SOURCE) --dry-run

template-export: ## Export clean template repo (no personal data, fresh history)
	./scripts/templatize.sh

backup-status: ## Check heartbeat staleness + show latest restic snapshots
	@HEARTBEAT="$$HOME/.local/log/restic-heartbeat.log"; \
	if [ -f "$$HEARTBEAT" ]; then \
	  LAST=$$(tail -1 "$$HEARTBEAT" | cut -d' ' -f1); \
	  AGE=$$(( ($$(date +%s) - $$(date -d "$$LAST" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%%H:%%M:%%SZ" "$$LAST" +%s)) / 3600 )); \
	  if [ "$$AGE" -gt $(RESTIC_STALE_HOURS) ]; then \
	    echo "WARNING: Last successful backup was $$AGE hours ago (threshold: $(RESTIC_STALE_HOURS)h)"; \
	  else \
	    echo "OK: Last successful backup $$AGE hours ago"; \
	  fi; \
	else \
	  echo "WARNING: No heartbeat file found — has a backup ever completed?"; \
	fi
ifeq ($(RESTIC_B2_BUCKET),)
	@echo "Set RESTIC_B2_BUCKET to show snapshots: make backup-status RESTIC_B2_BUCKET=my-bucket"
else
	@B2_ACCOUNT_ID=$$(sops -d --extract '["restic_b2_account_id"]' shared/secrets/vars.sops.yml) \
	B2_ACCOUNT_KEY=$$(sops -d --extract '["restic_b2_account_key"]' shared/secrets/vars.sops.yml) \
	RESTIC_PASSWORD=$$(sops -d --extract '["restic_repo_password"]' shared/secrets/vars.sops.yml) \
	restic -r "b2:$(RESTIC_B2_BUCKET):/" snapshots --host "$$(hostname)" --latest 3
endif

backup-browse: ## Open Backrest web UI at localhost:9898
	$(if $(filter darwin,$(PLATFORM)),open,xdg-open) http://localhost:9898
