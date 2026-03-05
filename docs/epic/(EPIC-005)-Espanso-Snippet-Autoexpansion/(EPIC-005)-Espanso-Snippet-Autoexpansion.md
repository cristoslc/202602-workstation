---
title: "Espanso Snippet Autoexpansion"
artifact: EPIC-005
status: Complete
author: cristos
created: 2026-03-04
last-updated: 2026-03-05
parent-vision: VISION-001
success-criteria:
  - All Raycast-imported snippets with date/time placeholders auto-expand correctly in Espanso
  - The raycast_to_espanso.py converter handles parametric Raycast placeholders ({date format="..."}, {time format="..."}) in addition to simple placeholders ({date}, {time})
  - Existing non-date snippets remain unaffected by converter changes
  - Re-importing a Raycast export and re-encrypting produces a working raycast.yml with native Espanso date extensions
depends-on: []
addresses: []
---

# Espanso Snippet Autoexpansion

## Goal / Objective

Fix the Raycast-to-Espanso snippet import pipeline so that date and time placeholders auto-expand correctly. Currently, Raycast exports use parametric date placeholders (`{date format="yyyy-MM-dd"}`), but the `raycast_to_espanso.py` converter only handles the simple form (`{date}`). The result is that the deployed `raycast.yml` contains literal Raycast syntax that Espanso cannot interpret, so typing triggers like `d;;` or `dt;;` produces the raw placeholder string instead of the current date/time.

### Root Cause

Raycast exports date/time snippets in two forms:

1. **Simple** (no custom format): `{date}`, `{time}` — these are already handled by the converter.
2. **Parametric** (custom format): `{date format="yyyy-MM-dd"}`, `{date format="yyyy-MM-dd HHmm"}`, `{date format="'GMT'Z"}` — these are **not** recognized by the converter and pass through as literal strings.

The converter's `_DATE_FORMATS` dictionary only matches exact simple-form keys. The parametric form requires regex-based extraction of the Raycast format string and translation to Python `strftime` equivalents for Espanso's date extension.

### Format Translation Required

Raycast uses Java/ICU-style date format tokens; Espanso uses Python `strftime` codes:

| Raycast token | strftime | Meaning |
|---------------|----------|---------|
| `yyyy` | `%Y` | 4-digit year |
| `yy` | `%y` | 2-digit year |
| `MM` | `%m` | Zero-padded month |
| `dd` | `%d` | Zero-padded day |
| `HH` | `%H` | 24-hour hour |
| `hh` | `%I` | 12-hour hour |
| `mm` | `%M` | Minute |
| `ss` | `%S` | Second |
| `a` | `%p` | AM/PM |
| `EEEE` | `%A` | Full weekday |
| `EEE` | `%a` | Abbreviated weekday |
| `MMMM` | `%B` | Full month name |
| `MMM` | `%b` | Abbreviated month name |
| `Z` | `%z` | Timezone offset |

Literal text in Raycast formats is enclosed in single quotes (e.g., `'GMT'`).

## Scope Boundaries

**In scope:**
- Update `raycast_to_espanso.py` to parse parametric `{date format="..."}` and `{time format="..."}` placeholders
- Implement Raycast-to-strftime format string translation
- Update tests in `tests/python/test_raycast_to_espanso.py`
- Re-run the converter on the current Raycast export and re-encrypt the result
- Validate that `d;;`, `dt;;`, and `dtz;;` triggers produce correct output after deployment

**Out of scope:**
- Changes to Espanso's backend configuration
- Adding new snippet triggers (only fixing existing ones)
- Modifying the stow/deployment pipeline
- Handling other unsupported Raycast placeholders beyond date/time

## Child Specs

_Updated as Agent Specs are created under this epic._

## Key Dependencies

None. The converter and test infrastructure already exist.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-03-04 | bafabec | Initial creation |
| Complete | 2026-03-05 | 3d2f68b | Converter updated, tests passing, encrypted YAML fixed |
