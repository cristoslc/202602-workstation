---
id: bd_202602-workstation-20e.4
status: closed
deps: []
links: []
created: 2026-03-05T03:01:33Z
type: task
priority: 2
---
# Re-import Raycast export and re-encrypt

Re-run the converter on the current Raycast JSON export to produce an updated raycast.yml with native Espanso date extensions. Re-encrypt with SOPS and verify the d;;, dt;;, dtz;; triggers use Espanso date vars instead of raw Raycast placeholders.


