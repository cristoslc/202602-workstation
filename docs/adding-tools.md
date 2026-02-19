# Adding a New Tool

## One Platform Only

Example: adding **lazygit** to Linux.

1. Create the role:
   ```
   linux/roles/lazygit/tasks/main.yml
   ```

2. Add to the appropriate phase playbook:
   ```yaml
   # linux/plays/02-dev-tools.yml
   - role: lazygit
     tags: [lazygit, dev-tools]
   ```

3. If it has config files, add a stow package:
   ```
   linux/dotfiles/lazygit/.config/lazygit/config.yml
   ```

## Both Platforms

Example: adding **lazygit** cross-platform.

1. Create a shared role with OS dispatch:
   ```
   shared/roles/lazygit/tasks/main.yml     # include_tasks dispatch
   shared/roles/lazygit/tasks/debian.yml    # apt install
   shared/roles/lazygit/tasks/darwin.yml    # brew install
   ```

2. Add to the Brewfile (macOS package manifest):
   ```ruby
   # macos/roles/homebrew/files/Brewfile
   brew "lazygit"
   ```

3. Add to phase playbooks in **both** platforms:
   ```yaml
   # linux/plays/02-dev-tools.yml AND macos/plays/02-dev-tools.yml
   - role: lazygit
     tags: [lazygit, dev-tools]
   ```

4. Shared dotfiles (if needed):
   ```
   shared/dotfiles/lazygit/.config/lazygit/config.yml
   ```

## Naming Conventions

- **Dotfile fragments** in `~/.config/zsh/`: use natural names. Shared = generic (`aliases.zsh`), platform = platform name (`linux.zsh`), secrets = `secrets.zsh`, local = `local.zsh`.
- **Roles**: one directory per tool, matching the tool name.
- **Tags**: match the role name for selective runs (`make apply ROLE=lazygit`).
