# shellcheck shell=bash
# Prompt: hostname ~/path [user] ❯
# Show username before chevron when running as a different user (e.g. su)
if [[ $USER != "${LOGNAME}" ]]; then
  _prompt_user="%F{117}%n"
else
  _prompt_user=""
fi

# Shorten deep paths: ~/a/b/c/d/e → ~/a/.../d/e (keeps first + last 2 segments)
_prompt_short_pwd() {
  local p="${PWD/#$HOME/~}"
  local parts=("${(@s:/:)p}")
  if (( ${#parts} > 4 )); then
    echo "${parts[1]}/${parts[2]}/.../${parts[-2]}/${parts[-1]}"
  else
    echo "$p"
  fi
}
setopt PROMPT_SUBST
PROMPT='%F{123}%m%f %F{213}$(_prompt_short_pwd)%f ${_prompt_user}%F{117}❯%f '
