#!/usr/bin/env bash
# Trigger Syncthing rescan after system resume from suspend.
# Installed to /usr/lib/systemd/system-sleep/ by Ansible.

case "$1" in
  post)
    # Brief delay for network to reconnect
    sleep 3
    # Restart all active syncthing@ user instances to force reconnection
    for unit in $(systemctl list-units --type=service --state=running --no-legend 'syncthing@*' 2>/dev/null | awk '{print $1}'); do
      systemctl restart "$unit" 2>/dev/null || true
    done
    ;;
esac
