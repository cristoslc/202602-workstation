---
title: "SPEC-004: Apply Role Search Filter"
artifact: SPEC-004
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-05
parent-epic: EPIC-004
linked-research: []
linked-adrs: []
depends-on: []
addresses:
  - JOURNEY-002.PP-03
---

# SPEC-004: Apply Role Search Filter

## Problem Statement

The Apply Role screen (`ApplyRoleScreen`) presents all discovered roles in a flat `OptionList` grouped by phase headers. As the role catalog grows (currently ~20 roles across 7 phases), users must scroll through the entire list to find the role they want. There is no way to filter or search, which slows down the most common TUI operation: applying a single known role after editing its tasks.

## External Behavior

### Inputs

- **Search query**: Free-text string typed into an `Input` widget positioned above the role list.
- **Role manifest**: The existing `discover_playbook()` output (list of phases, each containing roles with names, tags, and descriptions).

### Outputs

- **Filtered role list**: The `OptionList` is dynamically filtered to show only roles whose name, description, or tags fuzzy-match the query. Phase headers remain visible only if they contain at least one matching role.
- **Selection**: Selecting a filtered role behaves identically to the current flow — pushes `BootstrapPasswordScreen` in single-role mode.

### Preconditions

- The role manifest has been loaded via `discover_playbook()`.
- The Apply Role screen is mounted and visible.

### Postconditions

- Clearing the search input restores the full unfiltered role list.
- The selected role (if any) is passed to the existing execution pipeline unchanged.

### Constraints

- No new Python dependencies. Use stdlib or Textual builtins for fuzzy matching (e.g., substring containment with case folding, or a lightweight scoring function).
- Search must feel instant — no perceptible delay for the current role catalog size (~50 items).
- Phase headers (`disabled` separator items in `OptionList`) must not be selectable or returned as matches.
- Keyboard-first: the search input should be focused on screen mount, and arrow-down from the input should move focus into the filtered list.

## Acceptance Criteria

1. **Given** the Apply Role screen is displayed, **when** the user types "dock" into the search bar, **then** only roles matching "dock" appear (e.g., "docker") and non-matching phase groups are hidden.
2. **Given** a search query is active, **when** the user clears the input, **then** the full role list is restored with all phase headers.
3. **Given** a search query matches roles across multiple phases, **when** results are displayed, **then** matching roles remain grouped under their correct phase headers.
4. **Given** the search bar is empty, **when** the screen loads, **then** the search input has focus and the full role list is visible below it.
5. **Given** a partial or misspelled query like "pythn", **when** the user types it, **then** "python" still appears in results (fuzzy tolerance).
6. **Given** a role has tags ["Firefox", "Brave", "Chrome"], **when** the user types "brave", **then** that role appears in results (tag matching).

## Scope & Constraints

**In scope:**
- Search `Input` widget on `ApplyRoleScreen`
- Fuzzy matching logic (name, description, tags)
- Dynamic filtering of the `OptionList`
- Keyboard navigation between search input and role list

**Out of scope:**
- Changes to `BootstrapPhaseScreen` or `BootstrapRoleScreen` (multi-select screens)
- Persistent search history or saved filters
- Sorting or ranking of results (maintain phase order)
- Changes to role discovery or manifest format

## Implementation Approach

1. **Add `Input` widget** above the `OptionList` in `ApplyRoleScreen.compose()`. Bind `Input.Changed` to a filter handler.
2. **Implement fuzzy match function** — a simple scoring approach: split the query into characters, check if they appear in order within the candidate string (name + description + tags joined). Case-insensitive. This handles typos like "pythn" → "python" naturally.
3. **Filter handler** — on each keystroke, rebuild the `OptionList` contents: iterate the manifest, skip roles that don't match, skip phase headers with zero matching children. Preserve existing `Option` / disabled-separator structure.
4. **Focus management** — `on_mount` focuses the `Input`. Arrow-down from `Input` moves focus to the `OptionList`. Escape in the list returns focus to the input.
5. **CSS** — style the `Input` to match the existing screen aesthetic (border, padding consistent with other Textual screens in the app).

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | fb7ea84 | Initial creation |
