# Linux-specific shell configuration.

# fd is installed as fd-find on Debian
if command -v fdfind &>/dev/null && ! command -v fd &>/dev/null; then
  alias fd='fdfind'
fi

# bat is installed as batcat on Debian
if command -v batcat &>/dev/null && ! command -v bat &>/dev/null; then
  alias bat='batcat'
  alias cat='batcat --paging=never'
fi

# xdg-open shortcut
alias open='xdg-open'

# apt shortcuts
alias aptu='sudo apt update && sudo apt upgrade -y'
alias apti='sudo apt install -y'
alias apts='apt search'
