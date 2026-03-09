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
        decrypt clean-secrets status verify verify-role template-export \
        edit-secrets-shared edit-secrets-linux edit-secrets-macos \
        key-export key-import key-send key-receive \
        log-send log-receive export-iterm2 export-ice export-raycast export-streamdeck export-openin \
        export-typora-themes snippets-convert export-all \
        backup-status backup-browse \
        data-pull data-pull-dry code-pull code-pull-dry verify-sync-boundary \
        hub-migrate hub-migrate-dry hub-provision hub-restore \
        hub-backup-keys new-role

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
		shared/lib/wizard.sh scripts/*.sh scripts/wsync scripts/git-repo-scanner

ansible-lint: ## Run ansible-lint on all playbooks (SOPS disabled)
	ANSIBLE_VARS_ENABLED=host_group_vars ANSIBLE_CONFIG=$(CURDIR)/linux/ansible.cfg ansible-lint linux/site.yml
	ANSIBLE_VARS_ENABLED=host_group_vars ANSIBLE_CONFIG=$(CURDIR)/macos/ansible.cfg ansible-lint macos/site.yml

apply: ## Apply a specific role: make apply ROLE=git (or ROLE=gh for sub-task)
ifndef ROLE
	$(error ROLE is required. Usage: make apply ROLE=git)
endif
	./scripts/apply-role.sh $(PLATFORM_DIR) $(ROLE)

new-role: ## Scaffold a new role: make new-role NAME=my-tool
ifndef NAME
	$(error NAME is required. Usage: make new-role NAME=my-tool)
endif
	./scripts/new-role.sh $(NAME)

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

status: ## Show workstation verification dashboard (Textual TUI)
	@uv run --with textual,pyyaml,jinja2 scripts/setup.py --status

verify: ## Verify all installed apps (headless, exit 1 on failures)
	@uv run --with pyyaml scripts/workstation-status.py --verify

verify-sync-boundary: ## Check for unprotected git repos in Syncthing folders
	@./scripts/git-repo-scanner --dry-run

verify-role: ## Verify a single role: make verify-role ROLE=git
ifndef ROLE
	$(error ROLE is required. Usage: make verify-role ROLE=git)
endif
	@uv run --with pyyaml scripts/workstation-status.py --verify --role $(ROLE)

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

export-all: export-iterm2 export-ice export-streamdeck export-raycast export-openin export-typora-themes ## Export all settings

export-iterm2: ## Re-export iTerm2 plist, age-encrypted for the repo (macOS only)
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	defaults export com.googlecode.iterm2 - | plutil -convert xml1 -o macos/dotfiles/iterm2/.config/iterm2/com.googlecode.iterm2.plist -
	@AGE_PUBKEY=$$(grep -oE 'age1[a-z0-9]+' .sops.yaml | head -1); \
	mkdir -p macos/files/iterm2; \
	age -r "$$AGE_PUBKEY" -o macos/files/iterm2/iterm2.plist.age macos/dotfiles/iterm2/.config/iterm2/com.googlecode.iterm2.plist; \
	echo "iTerm2 plist exported and encrypted. Review with: git diff --stat macos/files/iterm2/"

export-ice: ## Re-export Ice plist, age-encrypted for the repo (macOS only)
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	@AGE_PUBKEY=$$(grep -oE 'age1[a-z0-9]+' .sops.yaml | head -1); \
	defaults export com.jordanbaird.Ice - | plutil -convert xml1 -o /tmp/ice-export.plist -; \
	mkdir -p macos/files/ice; \
	age -r "$$AGE_PUBKEY" -o macos/files/ice/ice.plist.age /tmp/ice-export.plist; \
	rm -f /tmp/ice-export.plist; \
	echo "Ice plist exported and encrypted. Review with: git diff --stat macos/files/ice/"

export-raycast: ## Export Raycast settings and age-encrypt for the repo (macOS only)
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

export-streamdeck: ## Export Stream Deck profiles + plugin list (age-encrypted, macOS only)
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	@SD_BACKUP="$$HOME/Library/Application Support/com.elgato.StreamDeck/BackupV3"; \
	SDFILE=$$(ls -t "$$SD_BACKUP"/*.streamDeckProfilesBackup 2>/dev/null | head -1); \
	if [ -z "$$SDFILE" ]; then echo "No Stream Deck backup found in BackupV3/"; exit 1; fi; \
	echo "Found: $$SDFILE"; \
	AGE_PUBKEY=$$(grep -oE 'age1[a-z0-9]+' .sops.yaml | head -1); \
	age -r "$$AGE_PUBKEY" -o macos/files/stream-deck/streamdeck.backup.age "$$SDFILE"; \
	echo "Profiles encrypted."; \
	echo "Scanning plugins (installed + backup)..."; \
	python3 -c " \
import sys; sys.path.insert(0, 'scripts/setup_tui'); \
from pathlib import Path; \
from lib.defaults import export_streamdeck_plugin_list; \
print(export_streamdeck_plugin_list(backup_path=Path('$$SDFILE'))) \
	"; \
	age -r "$$AGE_PUBKEY" -o macos/files/stream-deck/plugins.json.age macos/files/stream-deck/plugins.json; \
	echo "Plugin list encrypted."; \
	echo "Review with: git diff --stat macos/files/stream-deck/"

export-openin: ## Export OpenIn preferences, age-encrypted for the repo (macOS only)
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	@BUNDLE_ID=$$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" /Applications/Setapp/OpenIn.app/Contents/Info.plist); \
	mkdir -p macos/files/openin; \
	defaults export "$$BUNDLE_ID" - | plutil -convert xml1 -o macos/files/openin/openin.plist -; \
	AGE_PUBKEY=$$(grep -oE 'age1[a-z0-9]+' .sops.yaml | head -1); \
	age -r "$$AGE_PUBKEY" -o macos/files/openin/openin.plist.age macos/files/openin/openin.plist; \
	echo "OpenIn settings exported and encrypted. Review with: git diff --stat macos/files/openin/"

export-typora-themes: ## Sync Typora themes from local install to repo (cross-platform)
	@if [ "$(PLATFORM)" = "darwin" ]; then \
		THEMES_DIR="$$HOME/Library/Application Support/abnerworks.Typora/themes"; \
	else \
		THEMES_DIR="$$HOME/.config/Typora/themes"; \
	fi; \
	if [ ! -d "$$THEMES_DIR" ]; then echo "Typora themes directory not found: $$THEMES_DIR"; exit 1; fi; \
	BUNDLED="github.css newsprint.css night.css pixyll.css whitey.css"; \
	DEST="$(CURDIR)/shared/files/typora-themes"; \
	mkdir -p "$$DEST"; \
	count=0; \
	for f in "$$THEMES_DIR"/*.css; do \
		base=$$(basename "$$f"); \
		skip=false; \
		for b in $$BUNDLED; do [ "$$base" = "$$b" ] && skip=true; done; \
		if [ "$$skip" = "false" ]; then \
			cp "$$f" "$$DEST/$$base"; \
			count=$$((count + 1)); \
		fi; \
	done; \
	for d in "$$THEMES_DIR"/*/; do \
		base=$$(basename "$$d"); \
		skip=false; \
		for b in github newsprint night pixyll whitey old-themes; do [ "$$base" = "$$b" ] && skip=true; done; \
		if [ "$$skip" = "false" ]; then \
			cp -r "$$d" "$$DEST/$$base"; \
			count=$$((count + 1)); \
		fi; \
	done; \
	echo "Typora themes exported ($$count items). Review with: git diff --stat shared/files/typora-themes/"

snippets-convert: ## One-time: convert Raycast snippets JSON to SOPS-encrypted Espanso YAML
	@test "$(PLATFORM)" = "darwin" || { echo "macOS only"; exit 1; }
	@echo "Export your Raycast snippets: Raycast > Snippets > ... > Export All"
	@echo "Save the JSON file to ~/Downloads."
	@read -p "Press Enter after saving the export..."
	@SNIPFILE=$$(ls -t "$$HOME"/Downloads/Snippets*.json 2>/dev/null | head -1); \
	if [ -z "$$SNIPFILE" ]; then echo "No Snippets*.json found in ~/Downloads"; exit 1; fi; \
	echo "Found: $$SNIPFILE"; \
	SOPS_DEST="$(CURDIR)/shared/secrets/dotfiles/espanso/.config/espanso/match/raycast.yml"; \
	mkdir -p "$$(dirname "$$SOPS_DEST")"; \
	uv run --with pyyaml scripts/raycast_to_espanso.py "$$SNIPFILE" "$$SOPS_DEST"; \
	sops -e -i "$$SOPS_DEST"; \
	mv "$$SOPS_DEST" "$${SOPS_DEST}.sops"; \
	rm -f "$$SNIPFILE"; \
	echo "Snippets converted and encrypted to $${SOPS_DEST}.sops"; \
	echo "Edit later with: sops shared/secrets/dotfiles/espanso/.config/espanso/match/raycast.yml.sops"

code-pull: ## Migrate git repos from another machine: make code-pull SOURCE=<hostname>
ifndef SOURCE
	$(error SOURCE is required. Usage: make code-pull SOURCE=desktop)
endif
	./scripts/code-pull.sh $(SOURCE)

code-pull-dry: ## Preview code migration: make code-pull-dry SOURCE=<hostname>
ifndef SOURCE
	$(error SOURCE is required. Usage: make code-pull-dry SOURCE=desktop)
endif
	./scripts/code-pull.sh $(SOURCE) --dry-run

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

hub-migrate: ## Migrate hub to new server: make hub-migrate SOURCE=<old-hub> DEST=<new-hub>
ifndef SOURCE
	$(error SOURCE is required. Usage: make hub-migrate SOURCE=old-hub DEST=new-hub)
endif
ifndef DEST
	$(error DEST is required. Usage: make hub-migrate SOURCE=old-hub DEST=new-hub)
endif
	./scripts/hub-migrate.sh $(SOURCE) $(DEST)

hub-migrate-dry: ## Preview hub migration: make hub-migrate-dry SOURCE=<old-hub> DEST=<new-hub>
ifndef SOURCE
	$(error SOURCE is required)
endif
ifndef DEST
	$(error DEST is required)
endif
	./scripts/hub-migrate.sh $(SOURCE) $(DEST) --dry-run

hub-provision: ## Provision hub from scratch: make hub-provision HUB_HOST=<ip>
ifndef HUB_HOST
	$(error HUB_HOST is required. Usage: make hub-provision HUB_HOST=100.x.y.z)
endif
	cd infra/hub && ANSIBLE_HOST_KEY_CHECKING=false ansible-playbook hub.yml -e "hub_host=$(HUB_HOST)"

hub-restore: ## Restore hub with existing keys: make hub-restore HUB_HOST=<ip> KEY_DIR=<path>
ifndef HUB_HOST
	$(error HUB_HOST is required)
endif
ifndef KEY_DIR
	$(error KEY_DIR is required. Path to directory containing cert.pem + key.pem)
endif
	cd infra/hub && ANSIBLE_HOST_KEY_CHECKING=false ansible-playbook hub.yml -e "hub_host=$(HUB_HOST)" -e "syncthing_hub_inject_keys=true" -e "syncthing_hub_key_source=$(KEY_DIR)"

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

hub-backup-keys: ## Backup hub Syncthing identity keys (age-encrypted)
ifndef HUB_HOST
	$(error HUB_HOST is required. Usage: make hub-backup-keys HUB_HOST=100.x.y.z)
endif
	./scripts/hub-backup-keys.sh $(HUB_HOST)
