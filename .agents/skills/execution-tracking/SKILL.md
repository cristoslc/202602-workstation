---
name: execution-tracking
description: Bootstrap, install, and operate an external task-management CLI as the source of truth for agent execution tracking (instead of built-in todos). Provides the abstraction layer between spec-management intent (implementation plans and tasks) and concrete CLI commands. Use for tasks that require backend portability, persistent progress across agent runtimes, or external supervision.
license: UNLICENSED
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
metadata:
  short-description: Bootstrap and operate external task tracking
  version: 1.1.0
  author: cristos
---

# Execution Tracking

Abstraction layer for agent execution tracking. Other skills (e.g., spec-management) express intent using abstract terms; this skill translates that intent into concrete CLI commands.

## Term mapping

Other skills use these abstract terms. This skill maps them to the current backend:

| Abstract term | Meaning | bd mapping |
|---------------|---------|------------|
| **implementation plan** | Top-level container grouping all tasks for a spec artifact | `bd` epic (`bd create --type=epic`) |
| **task** | An individual unit of work within a plan | `bd` task (`bd create`) |
| **origin ref** | Immutable link from a plan to the spec that seeded it | `--external-ref <ID>` |
| **spec tag** | Mutable label linking a task to every spec it affects | `--labels spec:<ID>` / `bd label add` |
| **dependency** | Ordering constraint between tasks | `bd dep add` / `bd dep relate` |
| **ready work** | Unblocked tasks available for pickup | `bd ready` |

## Default workflow (current default: `bd`)
1. Check for `bd` availability:
   - Run `command -v bd` to test whether the binary is on `$PATH`.
2. If missing, attempt to install `bd`:
   - Detect the platform and available package managers.
   - macOS (Homebrew): `brew install beads`
   - Linux (Cargo): `cargo install beads`
   - If neither package manager is available, or the install command fails, proceed to the [Failure and fallback](#failure-and-fallback) section.
3. Initialize and validate:
   - `bd --help`
   - `bd ready`
   - If either command fails after a successful install, log the error and proceed to [Failure and fallback](#failure-and-fallback).
4. Track every meaningful work item with `bd` records.

## Canonical task states
Use this logical mapping even if the CLI uses different labels:
- `todo`: identified, not started
- `in_progress`: actively being worked
- `blocked`: cannot proceed due to dependency
- `done`: completed and verified

## Operating rules
1. Create/update external tasks at the start of work, after each major milestone, and before final response.
2. Keep task titles short and action-oriented.
3. Store handoff notes in the task entry rather than ephemeral chat context when possible.
4. Include references to related artifact IDs in task notes. Valid prefixes: `VISION-NNN`, `EPIC-NNN`, `SPEC-NNN`, `SPIKE-NNN`, `ADR-NNN`.

## Spec lineage tagging (bd-specific)
When creating `bd` tasks that implement a spec artifact:
- Tag the origin spec with `--external-ref <ID>` (e.g., `--external-ref SPEC-003`). This is immutable — it records which spec seeded the work.
- Tag all tasks with `spec:<ID>` labels (e.g., `--labels spec:SPEC-003`). These are mutable — add labels as cross-spec impact is discovered.
- When a task affects multiple specs, add additional labels: `bd label add <task-id> spec:SPEC-007`.
- Use `bd dep relate` for bidirectional links between tasks in different plans.
- Query all work for a spec with: `bd list --label spec:SPEC-003`.

## Parallel coordination (bd-specific)
- `bd swarm create <plan-id>` sets up a swarm — agents use `bd ready` to pick up unblocked work.
- For repeatable workflows, define a formula in `.beads/formulas/` and instantiate with `bd mol pour`.

## Observer pattern expectations
1. Maintain a compact current-status view that can be queried externally.
2. Ensure blockers are explicit and include required next action.
3. Use consistent tags/labels so supervisors can filter by stream, owner, or phase.

## Failure and fallback
If `bd` cannot be installed or is unavailable in the environment:
1. Log the failure reason in your work notes.
2. Fall back to a neutral text task ledger (JSONL or Markdown checklist) in the working directory.
3. Continue the same canonical state model and keep updates externally visible.
4. Mark that this fallback should be replaced once a preferred CLI is selected by SPIKE-001.

## Pending decision
The default CLI may change after `SPIKE-001 External Task CLI Evaluation`. Update this skill when the spike completes.
