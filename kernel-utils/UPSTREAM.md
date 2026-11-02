# Upstream source

- Project: https://github.com/aweeraman/kernel-utils
- Pinned commit: `afed59263764949e7245a447be0324bd984dd561`
- Source Makefile blob: `5a1ec787e5c01e8c7b45f0efe4450a8f652d9410`
- License: GPL-3.0, included verbatim as `COPYING`.

`upstream.mk` is the Makefile from that commit, with one local extension:

```diff
- mmdebstrap --architectures=...
+ bash scripts/run-mmdebstrap.sh $(MMDEBSTRAP_FLAGS) --architectures=...
```

The extra flags select verified Debian Bookworm signing keys on Ubuntu 22.04.
The wrapper stages public keyrings in a temporary, traversable directory so
apt's verification UID can read them even when the host home has mode 0700 or
0750. It also gives the child a temporary HOME and removes the staged files
when mmdebstrap exits. Host directory permissions stay unchanged.
All original packaging, QEMU, debugging and cleanup recipes remain in this file.
`Makefile` supplies project defaults, and `study.mk` adds preparation, lab staging,
configuration checks and the guest init hook. No nested Git repository or Git
submodule is required. Upstream changes are reviewed and imported explicitly.
