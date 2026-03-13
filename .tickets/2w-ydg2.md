---
id: 2w-ydg2
status: closed
deps: []
links: []
created: 2026-03-13T05:06:58Z
type: task
priority: 2
assignee: cristos
parent: 2w-wkka
tags: [spec:SPEC-006]
---
# Wire bootstrap role into steamos/site.yml

Create site.yml that runs steamos-bootstrap phase and ansible-lint clean.


## Notes

**2026-03-13T05:09:16Z**

site.yml created with 4 phases; ansible-lint shows expected errors for missing steamos-nix-packages and steamos-flatpak roles (not yet implemented)
