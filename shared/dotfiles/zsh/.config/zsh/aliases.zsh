# Cross-platform shell aliases.

# Navigation
alias ..='cd ..'
alias ...='cd ../..'

# Git
alias g='git'
alias gs='git status'
alias gd='git diff'
alias gl='git log --oneline -20'
alias gco='git checkout'
alias gcb='git checkout -b'
alias lg='lazygit'

# Safety
alias rm='rm -i'
alias mv='mv -i'
alias cp='cp -i'

# Modern replacements (available on both platforms via brew/apt)
if command -v eza &>/dev/null; then
  alias ls='eza'
  alias ll='eza -l'
  alias la='eza -la'
fi
if command -v dust &>/dev/null; then
  alias du='dust'
fi
if command -v duf &>/dev/null; then
  alias df='duf'
fi

# bat/cat — handles both macOS (bat) and Debian (batcat) naming
if command -v bat &>/dev/null; then
  alias cat='bat --paging=never'
elif command -v batcat &>/dev/null; then
  alias cat='batcat --paging=never'
fi

# Claude Code
alias claude-danger='claude --allow-dangerously-skip-permissions'

# Shell
alias reload='source ~/.zshrc'
alias h='history'
alias j='jobs -l'
alias cls='clear'
