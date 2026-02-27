# iTerm2 Preferences

Full iTerm2 settings managed via stow. The plist in this directory is
deployed to `~/.config/iterm2/` by the stow role, and the `macos-defaults`
role tells iTerm2 to load from that folder.

The plaintext plist is **gitignored** — only the age-encrypted copy at
`macos/files/iterm2/iterm2.plist.age` is committed to the repo.

## How it works

1. **Import** decrypts `iterm2.plist.age` → plaintext plist here
2. **Stow** symlinks the plist to `~/.config/iterm2/com.googlecode.iterm2.plist`
3. **Ansible** sets `PrefsCustomFolder` + `LoadPrefsFromCustomFolder` in the standard domain
4. **iTerm2** reads settings from the custom folder on launch

## Syncing changes back to the repo

After changing settings in iTerm2 (profiles, colors, keybindings, etc.):

```
make iterm2-export
```

This re-exports the live plist as XML into the stow package (local use) and
age-encrypts it to `macos/files/iterm2/iterm2.plist.age` for the repo.

## New machines

No manual steps needed — bootstrap handles everything:
- Homebrew installs iTerm2
- Import decrypts the plist from the repo
- Stow deploys the plist
- macos-defaults configures the custom folder pointer
- First launch picks up all settings automatically
