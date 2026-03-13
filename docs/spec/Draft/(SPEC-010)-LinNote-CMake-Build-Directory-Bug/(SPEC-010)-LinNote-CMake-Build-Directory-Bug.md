---
title: "LinNote CMake Build Directory Bug"
artifact: SPEC-010
status: Draft
author: cristos
created: 2026-03-13
last-updated: 2026-03-13
type: bug
parent-epic:
linked-research:
linked-adrs:
depends-on:
addresses:
evidence-pool:
source-issue:
swain-do: required
---

# LinNote CMake Build Directory Bug

## Problem Statement

The LinNote ansible role (`shared/roles/notes/tasks/linnote.yml`) fails during bootstrap with a cmake build error. The `Build LinNote` task passes `..` as the source directory to cmake, which resolves to `/tmp` (the parent of `/tmp/linnote-build`) instead of `.` (the cloned source directory itself).

## External Behavior

**Input:** `bootstrap.sh` runs `linux/site.yml` which includes the `notes` role.
**Precondition:** LinNote is not already installed (`/usr/local/bin/linnote` absent).
**Output:** Fatal ansible failure at `Build LinNote` task — cmake cannot find `CMakeLists.txt`.
**Postcondition:** Bootstrap aborts with `failed=1`, no subsequent roles execute.

## Acceptance Criteria

1. **Given** a fresh system without LinNote installed, **when** the `notes` role runs the `Build LinNote` task, **then** cmake finds `CMakeLists.txt` in the cloned source directory and the build succeeds.
2. **Given** the build succeeds, **when** the `Install LinNote` task runs, **then** `/usr/local/bin/linnote` exists.

## Reproduction Steps

1. Ensure `/usr/local/bin/linnote` does not exist.
2. Run `./bootstrap.sh` (or the ansible playbook directly).
3. Observe fatal error at `TASK [notes : Build LinNote]`:
   ```
   CMake Error: The source directory "/tmp" does not appear to contain CMakeLists.txt.
   Error: /tmp/linnote-build/build is not a directory
   ```

## Severity

high

## Expected vs. Actual Behavior

**Expected:** cmake runs with `/tmp/linnote-build` as source directory (`chdir` + `.`), creates `/tmp/linnote-build/build/`, and compiles LinNote.

**Actual:** cmake runs with `/tmp` as source directory (`chdir` + `..`), fails because `/tmp/CMakeLists.txt` does not exist.

## Verification

| Criterion | Evidence | Result |
|-----------|----------|--------|

## Scope & Constraints

- One-line fix: change `..` to `.` on line 36 of `linnote.yml`.
- No other roles or tasks are affected.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-13 | — | Initial creation |
