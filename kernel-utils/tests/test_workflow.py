"""Real Makefiles, fake kernels and tools; fixtures stay in the system temp dir.

No downloads, package installation, real mounts or QEMU boot are performed.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

PROJECT = Path(__file__).resolve().parents[1]
BASH = os.environ.get('BASH_EXE') or shutil.which('bash')
MAKE = os.environ.get('MAKE_EXE') or shutil.which('make') or shutil.which('mingw32-make')
BOOKWORM_KEYS = {
    'archive-key-12.asc': 'B8B80B5B623EAB6AD8775C45B7C5D7D6350947F8',
    'archive-key-12-security.asc': '05AB90340C0C5E797F44A8C8254CF3B5AEC0A8F0',
    'release-12.asc': '4D64FEC119C2029067D6E791F8D2585B8783D481',
}
if os.name == 'nt':
    BASH = BASH or r'C:\Program Files\Git\bin\bash.exe'
    if not MAKE and Path(r'C:\MinGW\bin\mingw32-make.exe').is_file():
        MAKE = r'C:\MinGW\bin\mingw32-make.exe'


@unittest.skipUnless(BASH and MAKE, 'GNU Make and Bash are required')
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kernel-study-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'kernel-utils'
        self.root.mkdir()
        for name in ('Makefile', 'study.mk', 'upstream.mk'):
            shutil.copy2(PROJECT / name, self.root / name)
        for name in ('scripts', 'overlay', 'labs', 'disks'):
            shutil.copytree(PROJECT / name, self.root / name)
        self.bin = self.root / 'mock-bin'
        self.bin.mkdir()
        # Only this disposable copy skips the UID check for root-run Linux CI.
        with (self.root / 'scripts/common.sh').open('a', encoding='utf-8', newline='\n') as f:
            f.write('\nrequire_linux() { [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]]; }\n')
            if os.name == 'nt':
                # Native GNU Make exports C:/ paths; Git Bash also exposes /tmp
                # as an alias for the same directory. Normalize fixtures only.
                f.write('''STUDY_ROOT=$(cygpath -u "$(cygpath -m "$STUDY_ROOT")")
for name in KERNELSRC ROOTFS_OVERLAY OUTPUT_ROOT OUTPUT_DIR MODULES_DIR ROOTFS ROOTFS_IMAGE SERIAL_LOG; do
    value=${!name:-}
    if [[ $value == [A-Za-z]:/* ]]; then export "$name=$(cygpath -u "$value")"; fi
done
''')
        if os.name == 'nt':
            # Native Make may launch mkdir with C:/ arguments. Use Git Bash's
            # /tmp alias, as above, for paths in this disposable fixture.
            self.mock('mkdir', '''
args=()
for arg in "$@"; do
    if [[ $arg == [A-Za-z]:/* ]]; then arg=$(cygpath -u "$arg"); fi
    args+=("$arg")
done
exec /usr/bin/mkdir "${args[@]}"
''')
        self.mock('uname', 'if [[ ${1:-} == -s ]]; then echo Linux; else echo x86_64; fi')
        for name in ('curl', 'apt-get'):
            self.mock(name, 'echo forbidden-tool >&2; exit 99')
        self.mock('sudo', '''
[[ ${1:-} != -v ]] || exit 0
case $1 in mount|umount|tar|tee|sync) exec "$@" ;; *) echo forbidden-sudo >&2; exit 99 ;; esac
''')
        self.mock('mkfs.ext4', 'echo format >> "$MOCK_STATE/events"; printf formatted > "${@: -1}"')
        self.mock('truncate', ':')
        self.mock('sync', ':')
        self.mock('mount', '''
dest=${@: -1}
printf '%s' "$dest" > "$MOCK_STATE/mounted"
if [[ -d $MOCK_STATE/guest-state ]]; then cp -a "$MOCK_STATE/guest-state/." "$dest/"; fi
''')
        self.mock('mountpoint', '[[ -f $MOCK_STATE/mounted ]] && [[ $(cat "$MOCK_STATE/mounted") == "${@: -1}" ]]')
        self.mock('umount', '''
[[ ${MOCK_UMOUNT_FAIL:-0} != 1 ]] || exit 32
dest=${@: -1}
mkdir -p "$MOCK_STATE/guest-state"
cp -a "$dest/." "$MOCK_STATE/guest-state/"
find "$dest" -mindepth 1 -delete
rm "$MOCK_STATE/mounted"
''')
        # Public-key fixtures contain fingerprints; this mock models inspection
        # and dearmoring without using real keys or making network requests.
        self.mock('gpg', '''
output=
dearmor=no
while (( $# )); do
    case $1 in
        --output) output=$2; shift 2 ;;
        --homedir) shift 2 ;;
        --dearmor) dearmor=yes; shift ;;
        --*) shift ;;
        *) input=$1; shift ;;
    esac
done
if [[ $dearmor == yes ]]; then cp -- "$input" "$output"; exit; fi
while IFS= read -r fingerprint; do
    [[ $fingerprint =~ ^[0-9A-F]{40}$ ]] || exit 2
    printf 'pub:-:4096:1:fixture:0:0::::::sc:\\nfpr:::::::::%s:\\n' "$fingerprint"
done < "$input"
''')
        self.mock('make', 'exec "$MAKE_TOOL" "$@"')
        self.mock('mmdebstrap', '''
printf '%s\\0' "$@" > "$MOCK_STATE/pack-args"
for arg in "$@"; do
    if [[ $arg == --keyring=* ]]; then
        cat -- "${arg#--keyring=}" > "$MOCK_STATE/used-keyring"
    fi
done
echo pack >> "$MOCK_STATE/events"
args=("$@")
mkdir -p "$MOCK_STATE/new-root/etc" "$MOCK_STATE/new-root/root"
printf original > "$MOCK_STATE/new-root/etc/hostname"
tar -C "$MOCK_STATE/new-root" -cpf "${args[${#args[@]}-2]}" .
''')
        self.mock('qemu-system-x86_64', '''
printf '%s\\0' "$@" > "$MOCK_STATE/qemu-args"
echo qemu >> "$MOCK_STATE/events"
exit "${MOCK_QEMU_EXIT:-0}"
''')
        self.mock('gdb-multiarch', 'printf "%s\\0" "$@" > "$MOCK_STATE/gdb-args"')
        (self.root / '.cache').mkdir()
        self.keyring = self.root / '.cache/debian-bookworm.gpg'
        self.keyring.write_text('\n'.join(BOOKWORM_KEYS.values()) + '\n', encoding='utf-8', newline='\n')

    def mock(self, name, body):
        path = self.bin / name
        path.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + body + '\n', encoding='utf-8', newline='\n')
        path.chmod(0o755)

    def invoke(self, *args, **env_changes):
        env = os.environ.copy()
        env.update(MAKE_TOOL=str(MAKE).replace('\\', '/'), MOCK_STATE=str(self.root).replace('\\', '/'))
        env.update(env_changes)
        shell = BASH
        if os.name == 'nt':
            # bin/bash.exe is Git's launcher and rewrites PATH on recursive
            # make calls; usr/bin/bash.exe is the shell itself.
            direct = Path(BASH).parents[1] / 'usr/bin/bash.exe'
            if direct.is_file():
                shell = str(direct)
        return subprocess.run(
            [BASH, '-c', 'export PATH="$PWD/mock-bin:$PATH"; exec "$MAKE_TOOL" --no-print-directory "$@"',
             'test', 'SHELL=' + str(shell).replace('\\', '/'), *args],
            cwd=self.root, env=env, text=True, encoding='utf-8', errors='replace',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=35)

    def mock_key_downloads(self, wrong_fingerprint=False):
        cases = '\n'.join(
            f'    */{name}) fingerprint={"0" * 40 if wrong_fingerprint else fingerprint} ;;'
            for name, fingerprint in BOOKWORM_KEYS.items())
        self.mock('curl', '''
while (( $# )); do
    case $1 in
        --output) output=$2; shift 2 ;;
        https://*) url=$1; shift ;;
        *) shift ;;
    esac
done
case $url in
''' + cases + '''
    *) exit 97 ;;
esac
printf '%s\\n' "$fingerprint" > "$output"
echo key-download >> "$MOCK_STATE/events"
''')

    def built_kernel(self):
        kernel = self.root / 'linux-5.15.2'
        files = {
            '.config': '\n'.join('CONFIG_' + n + '=y' for n in (
                'MODULES', 'BINFMT_ELF', 'BLOCK', 'PCI', 'VIRTIO', 'VIRTIO_PCI', 'VIRTIO_BLK',
                'EXT4_FS', 'DEVTMPFS', 'DEVTMPFS_MOUNT', 'PROC_FS', 'SYSFS', 'TMPFS',
                'SERIAL_8250_CONSOLE', 'CGROUPS', 'INOTIFY_USER', 'SIGNALFD', 'TIMERFD',
                'EPOLL', 'UNIX', 'DEBUG_FS', 'ACPI')) + '\n',
            'arch/x86/boot/bzImage': 'kernel', 'vmlinux': 'symbols',
            'include/config/kernel.release': '5.15.2-kernel-study\n', 'modules.order': '',
            'Makefile': '''.PHONY: modules_install modules
modules_install:
\tmkdir -p "$(INSTALL_MOD_PATH)/lib/modules/5.15.2-kernel-study"
\tprintf module > "$(INSTALL_MOD_PATH)/lib/modules/5.15.2-kernel-study/test.ko"
modules:
\tprintf module > "$(M)/test.ko"
'''}
        for name, value in files.items():
            path = kernel / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding='utf-8', newline='\n')
        return kernel

    def args(self, name):
        return [x.decode('utf-8') for x in (self.root / name).read_bytes().split(b'\0') if x]

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_help_and_config_do_not_create_artifacts(self):
        self.success(self.invoke('help'))
        result = self.invoke('print-config')
        self.success(result)
        self.assertIn('linux-5.15.2', result.stdout)
        self.assertIn('bookworm', self.invoke('help').stdout)
        self.assertFalse((self.root / 'out').exists())

    def test_package_and_boot_use_systemd_disk_and_network(self):
        self.built_kernel()
        self.success(self.invoke('boot'))
        args = self.args('qemu-args')
        self.assertNotIn('-initrd', args)
        self.assertIn('root=/dev/vda rootfstype=ext4 rw rootwait', args[args.index('-append') + 1])
        self.assertNotIn('rdinit=', args[args.index('-append') + 1])
        self.assertIn('file=' + self.root.as_posix() + '/disks/rootfs.img,format=raw,if=virtio,index=0', args)
        self.assertIn('-no-reboot', args)
        self.assertEqual(args[args.index('-m') + 1], '2G')
        self.assertIn('virtio-net-pci,netdev=net0', args)
        pack = self.args('pack-args')
        self.assertIn('bookworm', pack)
        self.assertIn('--mode=unshare', pack)
        self.assertTrue(any('debian-bookworm.gpg' in x for x in pack))
        self.assertTrue(any('sync-in' in x and 'overlay' in x for x in pack))
        self.assertTrue(any('chroot' in arg and 'configure-guest.sh' in arg for arg in pack))
        include = next(arg for arg in pack if arg.startswith('--include='))
        self.assertIn('systemd-sysv,udev', include)
        self.assertTrue((self.root / 'disks/rootfs.img').is_file())

    def test_debug_and_gdb_share_port_without_duplicate_nic(self):
        self.built_kernel()
        self.success(self.invoke('debug', 'GDB_PORT=2345'))
        args = self.args('qemu-args')
        self.assertIn('-S', args)
        self.assertIn('tcp:127.0.0.1:2345', args)
        self.assertEqual(args.count('-netdev'), 1)
        self.success(self.invoke('gdb', 'GDB_PORT=2345'))
        self.assertIn('target remote 127.0.0.1:2345', self.args('gdb-args'))

    def test_image_prepares_missing_keyring_and_reuses_it(self):
        self.built_kernel()
        self.keyring.unlink()
        self.mock_key_downloads()
        self.success(self.invoke('image'))
        self.assertEqual(self.keyring.read_text().splitlines(), list(BOOKWORM_KEYS.values()))
        keyring_arg = next(x for x in self.args('pack-args') if x.startswith('--keyring='))
        self.assertTrue(keyring_arg.startswith('--keyring=/tmp/kernel-study-bootstrap.'))
        self.assertEqual((self.root / 'used-keyring').read_text(), self.keyring.read_text())
        self.success(self.invoke('image'))
        self.assertEqual((self.root / 'events').read_text().splitlines().count('key-download'), 3)
        self.assertFalse(list((self.root / '.cache').glob('debian-keys.*')))

    def test_image_repairs_corrupt_and_incomplete_keyrings(self):
        self.built_kernel()
        self.mock_key_downloads()
        for contents in ('corrupt', BOOKWORM_KEYS['release-12.asc'] + '\n'):
            with self.subTest(contents=contents):
                self.keyring.write_text(contents, encoding='utf-8', newline='\n')
                self.success(self.invoke('rebuild'))
                self.assertEqual(self.keyring.read_text().splitlines(), list(BOOKWORM_KEYS.values()))

    def test_repository_pins_provided_keys_instead_of_host_keyring(self):
        self.built_kernel()
        flags = '--keyring=' + self.keyring.as_posix() + ' --components=main,contrib'
        self.success(self.invoke('image', 'MMDEBSTRAP_FLAGS=' + flags))
        mirror = self.args('pack-args')[-1]
        self.assertEqual(mirror, 'deb [signed-by=' + ','.join(BOOKWORM_KEYS.values())
                         + '] http://deb.debian.org/debian bookworm main contrib')
        self.assertNotIn('/tmp/', mirror)
        include = next(x for x in self.args('pack-args') if x.startswith('--include='))
        self.assertIn('debian-archive-keyring', include)

    def test_explicit_repository_entry_is_preserved(self):
        self.built_kernel()
        mirror = 'deb [signed-by=/usr/share/keyrings/custom.gpg] https://example.invalid/debian bookworm main'
        self.success(self.invoke('image', 'MIRROR=' + mirror))
        self.assertEqual(self.args('pack-args')[-1], mirror)

    def test_wrong_downloaded_key_stops_before_packaging(self):
        self.built_kernel()
        self.keyring.write_text('corrupt', encoding='utf-8')
        self.mock_key_downloads(wrong_fingerprint=True)
        result = self.invoke('boot')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected fingerprint', result.stderr)
        self.assertEqual(self.keyring.read_text(), 'corrupt')
        self.assertFalse((self.root / 'pack-args').exists())
        self.assertFalse((self.root / 'qemu-args').exists())
        self.assertFalse(list((self.root / '.cache').glob('debian-keys.*')))

    def test_added_packages_keep_baseline_and_disk_keeps_network(self):
        self.built_kernel()
        disk = self.root / 'disks/lab.img'
        disk.write_bytes(b'persistent-data')
        self.success(self.invoke('boot', 'EXTRA_PACKAGES=less,netcat-openbsd', 'DISK=' + disk.as_posix()))
        include = next(x for x in self.args('pack-args') if x.startswith('--include='))
        self.assertIn('bash,', include)
        self.assertIn('less,netcat-openbsd', include)
        self.assertFalse(include.endswith(','))
        self.assertIn('-drive', self.args('qemu-args'))
        self.assertIn('-netdev', self.args('qemu-args'))
        self.assertEqual(disk.read_bytes(), b'persistent-data')

    def test_image_reuse_and_explicit_overlay_update_preserve_guest(self):
        self.built_kernel()
        self.success(self.invoke('boot'))
        self.success(self.invoke('boot'))
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 1)
        changed = self.root / 'overlay/root/new.txt'
        changed.write_text('new', encoding='utf-8')
        os.utime(changed, (time.time() + 2, time.time() + 2))
        self.success(self.invoke('boot'))
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 1)
        guest = self.root / 'guest-state'
        (guest / 'root/keep.txt').write_text('persistent-data', encoding='utf-8')
        (guest / 'etc/hostname').write_text('custom-hostname', encoding='utf-8')
        self.success(self.invoke('update-image'))
        self.assertEqual((guest / 'root/keep.txt').read_text(), 'persistent-data')
        self.assertEqual((guest / 'etc/hostname').read_text(), 'custom-hostname')
        self.assertEqual((guest / 'root/new.txt').read_text(), 'new')
        self.assertEqual((self.root / 'events').read_text().splitlines().count('format'), 1)

    def test_lab_staging_refreshes_deleted_files_and_preserves_source(self):
        self.built_kernel()
        lab = self.root / 'labs/example'
        lab.mkdir()
        (lab / 'Makefile').write_text('obj-m += test.o\n', encoding='utf-8')
        (lab / 'test.c').write_text('source', encoding='utf-8')
        (lab / 'stale.txt').write_text('old', encoding='utf-8')
        (lab / '.git').mkdir()
        (lab / '.git/config').write_text('private', encoding='utf-8')
        self.success(self.invoke('lab', 'LAB=example'))
        dest = self.root / 'overlay/root/labs/example'
        self.assertEqual((dest / 'test.ko').read_text(), 'module')
        self.assertFalse((dest / '.git').exists())
        (lab / 'stale.txt').unlink()
        self.success(self.invoke('stage', 'LAB=example'))
        self.assertFalse((dest / 'stale.txt').exists())
        self.assertEqual((lab / 'test.c').read_text(), 'source')

    def test_changed_kernel_modules_are_installed_with_update_image(self):
        kernel = self.built_kernel()
        module = kernel / 'drivers/test.ko'
        module.parent.mkdir()
        module.write_text('old', encoding='utf-8')
        (kernel / 'modules.order').write_text('drivers/test.ko\n', encoding='utf-8')
        self.success(self.invoke('boot'))
        module.write_text('rebuilt', encoding='utf-8')
        os.utime(module, (time.time() + 2, time.time() + 2))
        self.success(self.invoke('update-image'))
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 1)
        self.assertEqual((self.root / 'guest-state/lib/modules/5.15.2-kernel-study/test.ko').read_text(), 'module')

    def test_packaging_failure_stops_before_qemu(self):
        self.built_kernel()
        self.mock('mmdebstrap', 'exit 42')
        result = self.invoke('boot')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'qemu-args').exists())
        self.assertFalse((self.root / 'disks/rootfs.img').exists())

    def test_lab_cannot_escape_source_tree(self):
        result = self.invoke('stage', 'LAB=../../outside')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'overlay/root/labs').exists())

    def test_modular_root_disk_driver_stops_before_packaging(self):
        kernel = self.built_kernel()
        config = kernel / '.config'
        config.write_text(config.read_text().replace('CONFIG_VIRTIO_BLK=y', 'CONFIG_VIRTIO_BLK=m'))
        result = self.invoke('boot')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CONFIG_VIRTIO_BLK=y', result.stderr)
        self.assertFalse((self.root / 'pack-args').exists())

    def test_qemu_failure_is_reported(self):
        self.built_kernel()
        result = self.invoke('boot', MOCK_QEMU_EXIT='7')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Error 7', result.stderr)

    def test_rebuild_preserves_disk_and_kernel(self):
        self.built_kernel()
        disk = self.root / 'disks/lab.img'
        disk.write_bytes(b'persistent')
        self.success(self.invoke('boot'))
        root_disk = self.root / 'disks/rootfs.img'
        root_disk.write_text('old-root-data')
        self.success(self.invoke('rebuild'))
        self.assertEqual(disk.read_bytes(), b'persistent')
        self.assertTrue((self.root / 'linux-5.15.2/Makefile').exists())
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 2)
        backups = [p for p in (self.root / 'disks').glob('rootfs.img.bak.*')
                   if not p.name.endswith('.kernel-release')]
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'old-root-data')
        self.assertEqual(Path(str(backups[0]) + '.kernel-release').read_text(), '5.15.2-kernel-study\n')

    def test_clean_preserves_root_and_next_boot_does_not_recreate_it(self):
        self.built_kernel()
        self.success(self.invoke('boot'))
        disk = self.root / 'disks/rootfs.img'
        disk.write_text('persistent-root')
        self.success(self.invoke('clean'))
        self.success(self.invoke('boot'))
        self.assertEqual(disk.read_text(), 'persistent-root')
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 1)

    def test_failed_rebuild_preserves_existing_root_disk(self):
        self.built_kernel()
        self.success(self.invoke('image'))
        disk = self.root / 'disks/rootfs.img'
        disk.write_text('keep-old-root')
        self.mock('mmdebstrap', 'exit 42')
        result = self.invoke('rebuild')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(disk.read_text(), 'keep-old-root')

    def test_release_mismatch_stops_qemu_until_update(self):
        self.built_kernel()
        self.success(self.invoke('image'))
        (self.root / 'disks/rootfs.img.kernel-release').write_text('old-release\n')
        result = self.invoke('boot')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('make update-image', result.stderr)
        self.assertFalse((self.root / 'qemu-args').exists())
        self.success(self.invoke('update-image'))
        self.success(self.invoke('boot'))

    def test_root_image_cannot_escape_disks_tree(self):
        self.built_kernel()
        result = self.invoke('image', 'ROOTFS_IMAGE=' + (self.root / 'out/rootfs.img').as_posix())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ROOTFS_IMAGE', result.stderr)
        self.assertFalse((self.root / 'pack-args').exists())

    @unittest.skipUnless(os.name == 'posix', 'Linux flock regression')
    def test_running_guest_prevents_update_and_rebuild(self):
        import fcntl
        self.built_kernel()
        self.success(self.invoke('image'))
        with (self.root / 'disks/rootfs.img.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for target in ('update-image', 'rebuild', 'boot'):
                result = self.invoke(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('root disk is in use', result.stderr)

    def test_unsafe_generated_paths_are_rejected(self):
        for override in ('OUTPUT_ROOT=.', 'OUTPUT_DIR=disks', 'MODULES_DIR=disks', 'SERIAL_LOG=disks/keep'):
            with self.subTest(override=override):
                result = self.invoke('clean', override)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ERROR:', result.stderr)
                self.assertTrue((self.root / 'Makefile').exists())

    def test_existing_source_is_kept_without_downloading(self):
        kernel = self.built_kernel()
        (kernel / 'local-change.c').write_text('keep', encoding='utf-8')
        self.success(self.invoke('source'))
        self.assertEqual((kernel / 'local-change.c').read_text(), 'keep')

    def test_corrupt_archive_is_rejected_before_extraction(self):
        (self.root / '.cache/linux-5.15.2.tar.xz').write_bytes(b'corrupt')
        result = self.invoke('source')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAILED', result.stdout + result.stderr)
        self.assertFalse((self.root / 'linux-5.15.2').exists())

    def test_shell_syntax_and_lf(self):
        for path in (PROJECT / 'scripts').glob('*.sh'):
            with self.subTest(path=path.name):
                result = subprocess.run([BASH, '-n', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(b'\r\n', path.read_bytes())


@unittest.skipUnless(
    os.name == 'posix' and hasattr(os, 'geteuid') and os.geteuid() == 0
    and all(shutil.which(tool) for tool in ('bash', 'gpg', 'gpgv', 'gpgconf', 'setpriv')),
    'Real keyring access regression requires Linux root, GnuPG and setpriv')
class KeyringAccessTests(unittest.TestCase):
    def test_private_home_does_not_hide_keyring_from_verification_uid(self):
        temp = tempfile.TemporaryDirectory(prefix='kernel-study-access-')
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        base.chmod(0o755)
        private = base / 'private-home'
        private.mkdir(mode=0o750)
        root = private / 'kernel-utils'
        scripts = root / 'scripts'
        scripts.mkdir(parents=True)
        for name in ('common.sh', 'run-mmdebstrap.sh'):
            shutil.copy2(PROJECT / 'scripts' / name, scripts / name)
        # Only this disposable fixture permits the root needed by setpriv.
        with (scripts / 'common.sh').open('a', encoding='utf-8') as f:
            f.write('\nrequire_linux() { :; }\n')

        gnupg = private / 'gnupg'
        gnupg.mkdir(mode=0o700)
        self.addCleanup(subprocess.run, ['gpgconf', '--homedir', str(gnupg), '--kill', 'gpg-agent'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        gpg = ['gpg', '--batch', '--no-options', '--homedir', str(gnupg),
               '--pinentry-mode', 'loopback', '--passphrase', '']
        result = subprocess.run(gpg + ['--quick-generate-key', 'kernel-study fixture', 'ed25519', 'sign', '1d'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        keyring = root / 'debian-bookworm.gpg'
        with keyring.open('wb') as f:
            subprocess.run(gpg + ['--export'], stdout=f, stderr=subprocess.PIPE, check=True, timeout=15)
        keyring.chmod(0o644)
        release = base / 'Release'
        release.write_text('Permission regression fixture\n', encoding='utf-8')
        signature = base / 'Release.gpg'
        subprocess.run(gpg + ['--output', str(signature), '--detach-sign', str(release)],
                       capture_output=True, check=True, timeout=15)
        release.chmod(0o644)
        signature.chmod(0o644)

        mock_bin = base / 'bin'
        mock_bin.mkdir()
        mock = mock_bin / 'mmdebstrap'
        mock.write_text('''#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do
    if [[ $arg == --keyring=* ]]; then keyring=${arg#--keyring=}; fi
done
printf '%s\\n%s\\n' "$keyring" "$HOME" > "$ACCESS_STATE"
exec setpriv --reuid=65534 --regid=65534 --clear-groups \\
    gpgv --homedir "$HOME" --status-fd=1 --keyring "$keyring" "$ACCESS_SIGNATURE" "$ACCESS_RELEASE"
''', encoding='utf-8', newline='\n')
        mock.chmod(0o755)
        env = os.environ.copy()
        env.update(PATH=str(mock_bin) + os.pathsep + env['PATH'],
                   ACCESS_STATE=str(base / 'access-state'), ACCESS_SIGNATURE=str(signature),
                   ACCESS_RELEASE=str(release))

        for mode, key_args in ((0o700, ['--keyring=' + str(keyring)]),
                               (0o750, ['--keyring', str(keyring)])):
            with self.subTest(mode=oct(mode)):
                private.chmod(mode)
                direct = subprocess.run(
                    ['setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', 'gpgv',
                     '--homedir', str(base), '--status-fd=1', '--keyring', str(keyring),
                     str(signature), str(release)], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(direct.returncode, 0)
                self.assertIn('NO_PUBKEY', direct.stdout)
                wrapped = subprocess.run(['bash', str(scripts / 'run-mmdebstrap.sh'), *key_args],
                                         env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(wrapped.returncode, 0, wrapped.stdout + wrapped.stderr)
                self.assertIn('VALIDSIG', wrapped.stdout)
                staged, child_home = (base / 'access-state').read_text().splitlines()
                self.assertTrue(staged.startswith('/tmp/kernel-study-bootstrap.'))
                self.assertFalse(Path(staged).exists())
                self.assertFalse(Path(child_home).exists())
                self.assertEqual(private.stat().st_mode & 0o777, mode)
                self.assertEqual(keyring.stat().st_mode & 0o777, 0o644)


if __name__ == '__main__':
    unittest.main()
