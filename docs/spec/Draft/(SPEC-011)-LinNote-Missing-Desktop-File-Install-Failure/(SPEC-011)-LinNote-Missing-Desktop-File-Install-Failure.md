---
title: "LinNote Missing Desktop File Install Failure"
artifact: SPEC-011
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

# LinNote Missing Desktop File Install Failure

## Problem Statement

After SPEC-010 fixed the cmake source path, LinNote now builds successfully but `cmake --install build` fails because `CMakeLists.txt` (line 151) references `org.example.LinNote.desktop` while the v1.0.0 source tree ships `linnote.desktop`. This is an upstream filename mismatch in the LinNote repository.

## External Behavior

**Input:** `cmake --install build` runs in `/tmp/linnote-build` after a successful build.
**Precondition:** Build completed, binary exists at `build/LinNote`.
**Output:** Fatal cmake error: `file INSTALL cannot find "/tmp/linnote-build/org.example.LinNote.desktop"`.
**Postcondition:** Bootstrap aborts. Binary was partially installed to `/usr/local/bin/LinNote` but the `.desktop` file and the stat check target (`/usr/local/bin/linnote`, lowercase) are missing.

## Acceptance Criteria

1. **Given** a fresh build of LinNote v1.0.0, **when** the install step runs, **then** the binary is installed to `/usr/local/bin/LinNote` and a `.desktop` file is placed in `/usr/local/share/applications/`.
2. **Given** the install succeeds, **when** the role's stat check runs on next invocation, **then** `/usr/local/bin/linnote` exists (or the stat path matches the installed binary name).

## Reproduction Steps

1. Run bootstrap with SPEC-010 fix applied (cmake source path `.`).
2. Build succeeds, but `cmake --install build` fails at the desktop file step.
3. Error: `file INSTALL cannot find "/tmp/linnote-build/org.example.LinNote.desktop"`.

## Severity

high

## Expected vs. Actual Behavior

**Expected:** `cmake --install build` installs binary and desktop file without error.

**Actual:** Install fails because `CMakeLists.txt` references `org.example.LinNote.desktop` but the source tree contains `linnote.desktop`.

## Verification

| Criterion | Evidence | Result |
|-----------|----------|--------|

## Scope & Constraints

- Fix the ansible role to work around the upstream mismatch by copying `linnote.desktop` to the expected name before install.
- Also fix the stat check path — upstream builds the binary as `LinNote` (capital L, capital N) but the role checks for `/usr/local/bin/linnote` (lowercase).
- No changes to upstream LinNote repository.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-13 | — | Initial creation |
