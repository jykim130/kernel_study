#!/usr/bin/env bash
# Runs inside the new Debian chroot, never on the Ubuntu host.
set -euo pipefail
[[ -x /lib/systemd/systemd && -L /sbin/init ]] || { echo 'systemd-sysv is required in INCLUDEPKGS.' >&2; exit 1; }
[[ ${GUEST_HOSTNAME:-} =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] || { echo 'Invalid GUEST_HOSTNAME.' >&2; exit 1; }
[[ ${GUEST_ROOT_PASSWORD:-} != *$'\n'* && ${GUEST_ROOT_PASSWORD:-} != *$'\r'* ]] || exit 1
printf '%s\n' "$GUEST_HOSTNAME" > /etc/hostname
printf '127.0.0.1 localhost\n127.0.1.1 %s\n' "$GUEST_HOSTNAME" > /etc/hosts
printf '/dev/vda / ext4 defaults 0 1\n' > /etc/fstab
printf 'nameserver 10.0.2.3\n' > /etc/resolv.conf
mkdir -p /etc/systemd/network
printf '[Match]\nName=en* eth*\n\n[Network]\nDHCP=yes\n' > /etc/systemd/network/20-wired.network
systemctl --root=/ enable "serial-getty@${CONSOLE:-ttyS0}.service" systemd-networkd.service
printf 'root:%s\n' "$GUEST_ROOT_PASSWORD" | chpasswd
chsh -s "${GUEST_SHELL:-/bin/bash}" root
# The default target is explicit so boot does not depend on preset policy.
systemctl --root=/ set-default multi-user.target
