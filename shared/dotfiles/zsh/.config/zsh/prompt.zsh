# shellcheck shell=bash
# Prompt: hostname ~/path [user] ❯
# Show username before chevron when running as a different user (e.g. su)
if [[ $USER != "${LOGNAME}" ]]; then
  _prompt_user="%F{117}%n"
else
  _prompt_user=""
fi
PROMPT="%F{123}%m%f %F{213}%~%f ${_prompt_user}%F{117}❯%f "
