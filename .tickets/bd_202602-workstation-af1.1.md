---
id: bd_202602-workstation-af1.1
status: closed
deps: []
links: []
created: 2026-03-06T05:41:38Z
type: task
priority: 2
assignee: Cristos L-C
---
# Investigate Raycast headless import

Check if .rayconfig can be imported via defaults/filesystem manipulation instead of the open dialog. Raycast stores data in ~/Library/Application Support/com.raycast.macos/. Determine if we can bypass the GUI by writing directly to the data dir or using defaults import.

## Notes

FINDINGS: Raycast .rayconfig is an opaque binary format (not a zip/json). Settings span com.raycast.macos defaults domain + multiple encrypted sqlite databases in ~/Library/Application Support/com.raycast.macos/. No CLI exists. The open command triggers Raycast's proprietary import/merge dialog which handles encrypted data, conflict resolution, and extension reconciliation. Headless import is NOT feasible without reverse-engineering the format. The interactive confirm dialog is required.
FINDINGS: Raycast headless import NOT feasible - .rayconfig is opaque binary, no CLI, interactive dialog required.


