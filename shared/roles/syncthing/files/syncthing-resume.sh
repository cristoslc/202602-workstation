#!/usr/bin/env bash
# Trigger Syncthing rescan after system resume from suspend.
# Installed to /usr/lib/systemd/system-sleep/ by Ansible.

case "$1" in
  post)
    # Brief delay for network to reconnect
    sleep 3

    # Run git-repo-scanner before Syncthing restart to update
    # .stglobalignore with any repos created while awake.
    # This ensures Syncthing reads correct ignores on reconnect.
    # See ADR-006 for architecture details.
    for user_home in /home/*/; do
      scanner="${user_home}.local/bin/git-repo-scanner"
      if [[ -x "$scanner" ]]; then
        user="$(basename "$user_home")"
        su - "$user" -c "$scanner" 2>/dev/null || true
      fi
    done

    # Restart all active syncthing@ user instances to force reconnection
    for unit in $(systemctl list-units --type=service --state=running --no-legend 'syncthing@*' 2>/dev/null | awk '{print $1}'); do
      systemctl restart "$unit" 2>/dev/null || true
    done
    ;;
esac
