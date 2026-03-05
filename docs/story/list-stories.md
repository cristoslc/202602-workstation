# User Story Lifecycle Index

## Draft

| ID | Title | Date | Commit | Notes |
|----|-------|------|--------|-------|
| STORY-006 | [Headless Settings Import]((STORY-006)-Headless-Settings-Import.md) | 2026-03-03 | ad25d92 | Investigate removing interactive GUI dialogs from Raycast/Stream Deck import (EPIC-003) |
| STORY-012 | [GitHub Copilot CLI Installation]((STORY-012)-GitHub-Copilot-CLI-Installation.md) | 2026-03-05 | ab03bdb | Standalone Copilot CLI on both platforms (EPIC-006) |

## Ready

| ID | Title | Date | Commit | Notes |
|----|-------|------|--------|-------|
| STORY-004 | [Resumable Data Pull]((STORY-004)-Resumable-Data-Pull.md) | 2026-03-03 | ad25d92 | rsync --partial for resumable data migration (EPIC-002) |
| STORY-005 | [Code Repo Migration Tool]((STORY-005)-Code-Repo-Migration-Tool.md) | 2026-03-03 | ad25d92 | make code-pull with repo discovery and dirty-state detection (EPIC-002) |

## Implemented

| ID | Title | Date | Commit | Notes |
|----|-------|------|--------|-------|
| STORY-007 | [1Password Age Key Retrieval]((STORY-007)-1Password-Age-Key-Retrieval.md) | 2026-03-05 | a17a7d2 | 1Password CLI retrieval with biometric auth + error handling (EPIC-004) |
| STORY-008 | [Ansible Failure Summary Panel]((STORY-008)-Ansible-Failure-Summary-Panel.md) | 2026-03-05 | 19c087c | All ACs met by existing TUI parser + summary + retry (EPIC-004) |
| STORY-009 | [Role Scaffolding Generator]((STORY-009)-Role-Scaffolding-Generator.md) | 2026-03-05 | 19c087c | scripts/new-role.sh + Makefile target (EPIC-004) |
| STORY-010 | [Auto-Propagation on Login]((STORY-010)-Auto-Propagation-on-Login.md) | 2026-03-05 | e47a69e | launchd + systemd auto-pull with desktop notifications (EPIC-004) |
| STORY-001 | [Backup Hub Syncthing Identity Keys]((STORY-001)-Backup-Hub-Syncthing-Identity-Keys.md) | 2026-03-03 | 3301fe2 | Age-encrypt hub cert.pem/key.pem to repo (ADR-002 pattern) |
| STORY-002 | [Hub Sync Monitor]((STORY-002)-Hub-Sync-Monitor.md) | 2026-03-03 | 3301fe2 | Spoke-side health check with desktop + Shoutrrr alerts |
| STORY-003 | [Hub Migration Automation]((STORY-003)-Hub-Migration-Automation.md) | 2026-03-03 | 3301fe2 | make hub-migrate script + Ansible hub playbook with key injection |
| STORY-011 | [Cross-Platform CI]((STORY-011)-Cross-Platform-CI.md) | 2026-03-05 | a17a7d2 | macOS + Linux matrix CI with all lint/syntax/test checks (EPIC-004) |

## Abandoned

_None._
