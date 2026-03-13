---
id: bd_202602-workstation-af1.2
status: closed
deps: []
links: []
created: 2026-03-06T05:41:39Z
type: task
priority: 2
---
# Investigate Stream Deck headless restore

Check if Stream Deck backup can be restored by copying contents to ~/Library/Application Support/com.elgato.StreamDeck/ instead of using the open dialog. The .streamDeckProfilesBackup format needs investigation.

## Notes

FINDINGS: Stream Deck .streamDeckProfilesBackup is a standard zip archive containing Profiles/<UUID>.sdProfile/ directories with manifest.json files and Images/. The backup's Profiles/ directory maps 1:1 to ~/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/. Headless restore IS feasible: (1) quit Stream Deck app, (2) unzip backup's Profiles/ contents into ProfilesV3/, (3) restart the app. No dialog needed.


