# Upstream source

- Project: https://github.com/aweeraman/kernel-utils
- Pinned commit: `afed59263764949e7245a447be0324bd984dd561`
- Source Makefile blob: `5a1ec787e5c01e8c7b45f0efe4450a8f652d9410`
- License: GPL-3.0, included verbatim as `COPYING`.

`upstream.mk` is adapted from the Makefile at that commit. Local changes:

- Replace the disposable initramfs workflow with a persistent ext4 root disk.
  QEMU boots with `root=/dev/vda`; Debian's systemd-sysv supplies PID 1.
- Keep the `image`, `boot`, `boot-log`, `debug`, `gdb` and cleanup interface.
  Add `update-image` to refresh modules/overlay without resetting guest data.
  `image` reuses an existing disk; `rebuild` backs up the old disk after the
  replacement has been built successfully. Cleanup only removes `out/`.
- Use `scripts/manage-image.sh` for locked, temporary loop mounts and atomic
  publication of new disks. `scripts/run-qemu.sh` holds the same lock while
  QEMU runs and verifies the kernel release metadata.
- Replace the custom `/init` hook with `scripts/configure-guest.sh` inside the
  Debian chroot: systemd serial login, DHCP, hostname and the root account.
- Invoke mmdebstrap through `scripts/run-mmdebstrap.sh $(MMDEBSTRAP_FLAGS)`.

The extra flags select verified Debian Bookworm signing keys on Ubuntu 22.04.
The wrapper stages public keyrings in a temporary, traversable directory so
apt's verification UID can read them even when the host home has mode 0700 or
0750. It also gives the child a temporary HOME and removes the staged files
when mmdebstrap exits. Host directory permissions stay unchanged.
For a mirror URL, it also pins the provided key fingerprints with an explicit
signed-by repository entry. This prevents mmdebstrap 0.8.4 from choosing the
host's older Debian keyring instead. The guest includes debian-archive-keyring
and its repository entry contains no temporary host paths.
`Makefile` supplies project defaults, and `study.mk` adds preparation, lab staging
and configuration checks. No nested Git repository or Git
submodule is required. Upstream changes are reviewed and imported explicitly.

# Lab sources

- Project: https://github.com/linux-kernel-labs/linux
- Pinned commit: `a251a609fa4a8efb4fc41f9315d18c70a333aa1e`
- License: GPL-2.0, the license of that repository.

`templates/lab02-kernel-api/` is copied from `tools/labs/templates/kernel_api`
at that commit and keeps the full solutions. The task sources are unchanged;
`README.md` is a Korean study guide based on the upstream lab page, and
`Makefile` is a local addition that builds every task from the lab directory.

`scripts/generate_skels.py` is `tools/labs/templates/generate_skels.py` from
the same commit. Its regex literals are raw strings to avoid escape warnings
on newer Python. `scripts/make-skels.sh` wraps it like upstream `make skels`
(default `TODO=0`), but writes into `labs/` and never overwrites existing files.
Like upstream `skels/Kbuild`, it regenerates a top-level `labs/<lab>/Kbuild`
that lists every task, so `make lab LAB=<lab>` builds them in one kbuild run.
Lab 01 predates this workflow and keeps its skeletons in `labs/`.
