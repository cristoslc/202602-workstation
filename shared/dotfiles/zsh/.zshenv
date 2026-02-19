# Managed by iac-daily-driver-environments.
# PATH setup lives here — sourced before .zshrc, so fragment load order doesn't matter.

# Homebrew (macOS)
if [ -d /opt/homebrew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# uv
if [ -d "$HOME/.local/bin" ]; then
  export PATH="$HOME/.local/bin:$PATH"
fi

# fnm (Node version manager)
if [ -d "$HOME/.local/share/fnm" ]; then
  export PATH="$HOME/.local/share/fnm:$PATH"
  eval "$(fnm env --use-on-cd)"
fi

# uv managed Python
if [ -d "$HOME/.local/share/uv/python" ]; then
  export PATH="$(find "$HOME/.local/share/uv/python" -maxdepth 2 -name bin -type d | head -1):$PATH" 2>/dev/null
fi

# direnv
if command -v direnv &>/dev/null; then
  eval "$(direnv hook zsh)"
fi
