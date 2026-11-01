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
for name in KERNELSRC ROOTFS_OVERLAY OUTPUT_ROOT OUTPUT_DIR MODULES_DIR ROOTFS INITRAMFS SERIAL_LOG; do
    value=${!name:-}
    if [[ $value == [A-Za-z]:/* ]]; then export "$name=$(cygpath -u "$value")"; fi
done
''')
        self.mock('uname', 'if [[ ${1:-} == -s ]]; then echo Linux; else echo x86_64; fi')
        for name in ('sudo', 'curl', 'apt-get'):
            self.mock(name, 'echo forbidden-tool >&2; exit 99')
        self.mock('make', 'exec "$MAKE_TOOL" "$@"')
        self.mock('mmdebstrap', '''
printf '%s\\0' "$@" > "$MOCK_STATE/pack-args"
printf '%s' "$INIT" > "$MOCK_STATE/guest-init"
echo pack >> "$MOCK_STATE/events"
args=("$@")
printf rootfs > "${args[${#args[@]}-2]}"
''')
        self.mock('bsdtar', '''
while (( $# )); do
    if [[ $1 == -cf ]]; then printf archive > "$2"; exit; fi
    shift
done
exit 98
''')
        self.mock('qemu-system-x86_64', '''
printf '%s\\0' "$@" > "$MOCK_STATE/qemu-args"
echo qemu >> "$MOCK_STATE/events"
exit "${MOCK_QEMU_EXIT:-0}"
''')
        self.mock('gdb-multiarch', 'printf "%s\\0" "$@" > "$MOCK_STATE/gdb-args"')
        (self.root / '.cache').mkdir()
        (self.root / '.cache/debian-bookworm.gpg').write_text('fixture', encoding='utf-8')

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

    def built_kernel(self):
        kernel = self.root / 'linux-5.15.2'
        files = {
            '.config': '\n'.join('CONFIG_' + n + '=y' for n in (
                'MODULES', 'BLK_DEV_INITRD', 'DEVTMPFS', 'PROC_FS', 'SYSFS', 'DEBUG_FS', 'SERIAL_8250_CONSOLE')) + '\n',
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

    def test_package_and_boot_use_initramfs_and_network(self):
        self.built_kernel()
        self.success(self.invoke('boot'))
        args = self.args('qemu-args')
        self.assertIn('-initrd', args)
        self.assertIn('rdinit=/init', args[args.index('-append') + 1])
        self.assertNotIn('-drive', args)
        self.assertNotIn('format=raw,if=virtio', args)
        self.assertEqual(args[args.index('-m') + 1], '2G')
        self.assertIn('virtio-net-pci,netdev=net0', args)
        pack = self.args('pack-args')
        self.assertIn('bookworm', pack)
        self.assertIn('--mode=unshare', pack)
        self.assertTrue(any('debian-bookworm.gpg' in x for x in pack))
        self.assertTrue(any('sync-in' in x and 'overlay' in x for x in pack))
        init = (self.root / 'guest-init').read_text(encoding='utf-8')
        self.assertIn('name=${iface##*/}', init)
        self.assertIn('udhcpc -n -q -i "$name"', init)

    def test_debug_and_gdb_share_port_without_duplicate_nic(self):
        self.built_kernel()
        self.success(self.invoke('debug', 'GDB_PORT=2345'))
        args = self.args('qemu-args')
        self.assertIn('-S', args)
        self.assertIn('tcp:127.0.0.1:2345', args)
        self.assertEqual(args.count('-netdev'), 1)
        self.success(self.invoke('gdb', 'GDB_PORT=2345'))
        self.assertIn('target remote 127.0.0.1:2345', self.args('gdb-args'))

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

    def test_image_reuse_and_overlay_update(self):
        self.built_kernel()
        self.success(self.invoke('boot'))
        self.success(self.invoke('boot'))
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 1)
        changed = self.root / 'overlay/root/new.txt'
        changed.write_text('new', encoding='utf-8')
        os.utime(changed, (time.time() + 2, time.time() + 2))
        self.success(self.invoke('boot'))
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 2)

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

    def test_changed_kernel_module_repackages_without_new_bzimage(self):
        kernel = self.built_kernel()
        module = kernel / 'drivers/test.ko'
        module.parent.mkdir()
        module.write_text('old', encoding='utf-8')
        (kernel / 'modules.order').write_text('drivers/test.ko\n', encoding='utf-8')
        self.success(self.invoke('boot'))
        module.write_text('rebuilt', encoding='utf-8')
        os.utime(module, (time.time() + 2, time.time() + 2))
        self.success(self.invoke('boot'))
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 2)

    def test_packaging_failure_stops_before_qemu(self):
        self.built_kernel()
        self.mock('mmdebstrap', 'exit 42')
        result = self.invoke('boot')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'qemu-args').exists())
        self.assertFalse((self.root / 'out/amd64/initramfs.cpio').exists())

    def test_lab_cannot_escape_source_tree(self):
        result = self.invoke('stage', 'LAB=../../outside')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'overlay/root/labs').exists())

    def test_missing_initramfs_option_stops_packaging(self):
        kernel = self.built_kernel()
        config = kernel / '.config'
        config.write_text(config.read_text().replace('CONFIG_BLK_DEV_INITRD=y', '# CONFIG_BLK_DEV_INITRD is not set'))
        result = self.invoke('boot')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CONFIG_BLK_DEV_INITRD=y', result.stderr)
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
        self.success(self.invoke('rebuild'))
        self.assertEqual(disk.read_bytes(), b'persistent')
        self.assertTrue((self.root / 'linux-5.15.2/Makefile').exists())
        self.assertEqual((self.root / 'events').read_text().splitlines().count('pack'), 2)

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


if __name__ == '__main__':
    unittest.main()
