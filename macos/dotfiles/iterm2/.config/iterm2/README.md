# iTerm2 Preferences

Full iTerm2 settings managed via stow. The `com.googlecode.iterm2.plist` in
this directory is deployed to `~/.config/iterm2/` by the stow role, and the
`macos-defaults` role tells iTerm2 to load from that folder.

## How it works

1. **Stow** symlinks the plist to `~/.config/iterm2/com.googlecode.iterm2.plist`
2. **Ansible** sets `PrefsCustomFolder` + `LoadPrefsFromCustomFolder` in the standard domain
3. **iTerm2** reads settings from the custom folder on launch

## Syncing changes back to the repo

After changing settings in iTerm2 (profiles, colors, keybindings, etc.):

```
make iterm2-export
```

This re-exports the live plist as XML into the stow package for diffable commits.

## New machines

No manual steps needed — bootstrap handles everything:
- Homebrew installs iTerm2
- Stow deploys the plist
- macos-defaults configures the custom folder pointer
- First launch picks up all settings automatically
