# Managed by iac-daily-driver-environments.
# Machine-specific overrides go in ~/.config/zsh/local.zsh (gitignored).

# Source all zsh config fragments.
# Shared, platform, secrets, and local files are all picked up by this glob.
for conf in "$HOME/.config/zsh/"*.zsh(N); do
  source "$conf"
done
