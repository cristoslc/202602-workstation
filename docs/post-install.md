# Post-Install Manual Steps

These steps cannot be automated and must be done manually after bootstrap completes.

## Both Platforms

- [ ] 1Password: sign in and enable SSH agent in Settings → Developer
- [ ] 1Password browser extension: install in Firefox (and optionally Brave/Chrome)
- [ ] Firefox: sign in and sync profile
- [ ] Git: verify SSH key works (`ssh -T git@github.com` — key served via 1Password agent)
- [ ] Docker Hub: sign in (`docker login`)
- [ ] Tailscale: sign in (`tailscale up` on Linux, or open app on macOS)
- [ ] Surfshark: sign in to the app
- [ ] Slack: sign in to workspaces
- [ ] Signal: verify phone number
- [ ] Spotify: sign in
- [ ] Stream Deck: open app, configure buttons/profiles, import backup if available
- [ ] Restic: verify backup works (`make backup-status`)
- [ ] Backrest: open `http://localhost:9898` and confirm dashboard shows repo
- [ ] Verify first backup completes without error
- [ ] (Optional) Pause backups: Backrest web UI → plan → disable schedule
- [ ] (Optional) Bandwidth limit: set `restic_upload_limit` in defaults

## Linux (Mint 22)

- [ ] Cinnamon desktop preferences (wallpaper, panel layout, theme)
- [ ] Vicinae: initial setup and configuration
- [ ] Verify Espanso is running (`espanso status`)
- [ ] Verify default browser is correct (`xdg-settings get default-web-browser`)
- [ ] Verify MIME associations: `xdg-mime query default x-scheme-handler/https`
- [ ] Select a screenshot tool (Flameshot or Shutter) and add to the `screenshots` role
- [ ] Verify Timeshift snapshots (`sudo timeshift --list`) and Restic backups (`make backup-status`)

## macOS

- [ ] Setapp: sign in and install Setapp-managed apps (Dato, BusyCal, CleanShot X, Downie, OpenIn, Paletro)
- [ ] OpenIn: if no export was imported during bootstrap, configure browser routing rules (work profile → Chrome, personal → Firefox, etc.), then run `make openin-export`
- [ ] CleanShot X: configure screenshot shortcuts (replace default ⌘⇧4)
- [ ] Dato: configure menu bar calendar display
- [ ] BusyCal: sign in to calendar accounts
- [ ] Paletro: verify it's accessible via shortcut
- [ ] Raycast: if no export was imported during bootstrap, set as default launcher and configure clipboard history, snippets, window management, then run `make raycast-export`
- [ ] Sign into Mac App Store (required for `mas` installs)
- [ ] iCloud sign-in (if applicable)
- [ ] Backblaze: sign in and configure backup
- [ ] Verify Restic backup is running alongside Backblaze (`make backup-status`)
- [ ] Set default browser in System Settings → Default web browser
