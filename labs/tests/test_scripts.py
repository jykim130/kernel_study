"""Unprivileged checks: no downloads, real mounts, package installs or QEMU boot.

Lifecycle tests use isolated project copies and fake privileged commands.
The production Linux guard is bypassed only in those disposable copies.
"""
import hashlib
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
BASH = os.environ.get("BASH_EXE")
if not BASH and os.name == "nt":
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    if candidate.is_file():
        BASH = str(candidate)
BASH = BASH or shutil.which("bash")


@unittest.skipUnless(BASH, "Bash is required")
class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="test lab, ")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.root = self.repo / "labs"
        self.root.mkdir()
        for directory in ("config", "scripts"):
            shutil.copytree(PROJECT / directory, self.root / directory)
        shutil.copy2(PROJECT.parent / "boot", self.repo / "boot")
        self.bin = self.root / "mock-bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.log"

    def mock(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\nset -eu\n" + body + "\n", encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def simulate_linux(self):
        common = self.root / "scripts/common.sh"
        with common.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\nrequire_linux() { :; }\n")
            if os.name == "nt":
                # Windows sandbox rejects mkdir -p through read-only ancestors.
                # Lifecycle fixtures stay relative to their disposable cwd;
                # previews separately exercise real absolute paths and quoting.
                handle.write('''PROJECT_ROOT=.
CACHE_DIR=./.cache
KERNEL_SRC=./src/linux-5.15.2
KERNEL_BUILD="$KERNEL_SRC"
IMAGE_DIR=./images
ROOTFS_IMAGE=./images/rootfs.img
LOG_DIR=./logs
''')
        self.mock("flock", 'exit "${MOCK_LOCK_EXIT:-0}"')
        self.mock("sudo", 'echo unexpected-sudo >> "$MOCK_CALLS"; exit 99')
        self.mock("qemu-system-x86_64", 'echo qemu >> "$MOCK_CALLS"; exit "${MOCK_QEMU_EXIT:-0}"')

    def invoke(self, script, *args, **overrides):
        env = os.environ.copy()
        env.update({"MOCK_CALLS": str(self.calls), "MOCK_STATE": str(self.root), "BUILD_JOBS": "2"})
        env.update(overrides)
        # Construct PATH inside Bash so both Windows and Linux path formats work.
        return subprocess.run(
            [BASH, "-c", 'export PATH="$PWD/mock-bin:$PATH"; exec bash "$@"',
             "test", str(self.repo / "boot" if script == "boot" else self.root / "scripts" / script), *args],
            cwd=self.root, env=env, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
        )

    def built_kernel(self):
        build = self.root / "src/linux-5.15.2"
        for filename, text in {
            "arch/x86/boot/bzImage": "test-image",
            "include/config/kernel.release": "5.15.2-kernel-study\n",
            "modules.order": "",
        }.items():
            path = build / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def image(self, release="5.15.2-kernel-study"):
        images = self.root / "images"
        images.mkdir(exist_ok=True)
        image = images / "rootfs.img"
        image.write_bytes(b"existing-user-data")
        (images / "rootfs.img.kernel-release").write_text(release + "\n", encoding="utf-8")
        return image

    def test_shell_syntax_and_lf(self):
        for path in [PROJECT.parent / "boot"] + list((PROJECT / "scripts").glob("*.sh")) + list((PROJECT / "config").glob("*.sh")):
            with self.subTest(path=path.name):
                result = subprocess.run([BASH, "-n", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(b"\r\n", path.read_bytes())

    def test_help_needs_no_artifacts_or_privileges(self):
        for script in ("install-deps.sh", "build-kernel.sh", "make-rootfs.sh", "run-qemu.sh"):
            with self.subTest(script=script):
                result = self.invoke(script, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Usage:", result.stdout)

    def test_preview_uses_direct_virtio_boot_and_quotes_paths(self):
        result = self.invoke("run-qemu.sh", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = shlex.split(result.stdout)
        self.assertEqual(args[args.index("-accel") + 1], "tcg")
        drive = args[args.index("-drive") + 1]
        self.assertIn("test lab,, ", drive)  # QEMU's comma escaping, not a new option.
        self.assertTrue(drive.endswith("/images/rootfs.img,format=raw,if=virtio"))
        self.assertIn("root=/dev/vda", args[args.index("-append") + 1])
        self.assertNotIn("-initrd", args)
        self.assertNotIn("-gdb", args)
        self.assertNotIn("-S", args)
        self.assertFalse((self.root / "images").exists())

    def test_debug_preview_pauses_on_loopback_with_requested_resources(self):
        result = self.invoke("run-qemu.sh", "--dry-run", "--debug", "--gdb-port", "1235",
                             "--snapshot", QEMU_MEMORY="2048", QEMU_CPUS="3")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = shlex.split(result.stdout)
        self.assertEqual(args[args.index("-gdb") + 1], "tcp:127.0.0.1:1235")
        self.assertIn("-S", args)
        self.assertIn("-snapshot", args)
        self.assertEqual(args[args.index("-m") + 1], "2048")
        self.assertEqual(args[args.index("-smp") + 1], "3")

    def test_boot_selects_in_tree_kernel_and_forwards_debug_options(self):
        result = self.invoke("boot", "linux-5.15.2", "--dry-run", "--debug",
                             "--snapshot", "--gdb-port", "1235")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = shlex.split(result.stdout)
        self.assertTrue(args[args.index("-kernel") + 1].endswith(
            "/src/linux-5.15.2/arch/x86/boot/bzImage"))
        self.assertEqual(args[args.index("-gdb") + 1], "tcp:127.0.0.1:1235")
        self.assertIn("-snapshot", args)
        self.assertIn("-S", args)
        self.assertFalse((self.root / "src").exists())
        self.assertFalse((self.root / "images").exists())

    def test_boot_help_and_kernel_name_validation_need_no_artifacts(self):
        result = self.invoke("boot", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Usage: ./boot linux-5.15.2", result.stdout)
        result = self.invoke("boot")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stderr)
        for name in ("linux-5.15.4", "../linux-5.15.2", "--debug"):
            with self.subTest(name=name):
                result = self.invoke("boot", name, "--dry-run")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Kernel must match", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_invalid_options_are_rejected_before_launch(self):
        for args in (("--accel",), ("--accel", "invalid"), ("--gdb-port", "0"),
                     ("--gdb-port", "65536"), ("--gdb-port", "abc"), ("--unknown",)):
            with self.subTest(args=args):
                result = self.invoke("run-qemu.sh", "--dry-run", *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ERROR:", result.stderr)
        result = self.invoke("run-qemu.sh", "--dry-run", QEMU_MEMORY="-1")
        self.assertNotEqual(result.returncode, 0)

    def test_existing_image_is_never_overwritten(self):
        self.simulate_linux()
        image = self.image()
        result = self.invoke("make-rootfs.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("leaving it unchanged", result.stdout)
        self.assertEqual(image.read_bytes(), b"existing-user-data")
        self.assertFalse(self.calls.exists())

    def test_update_requires_existing_image_before_sudo(self):
        self.simulate_linux()
        result = self.invoke("make-rootfs.sh", "--update-modules")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No rootfs image", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_release_mismatch_blocks_qemu(self):
        self.simulate_linux()
        self.built_kernel()
        self.image("different-kernel")
        result = self.invoke("run-qemu.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Kernel release mismatch", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_qemu_failure_is_not_hidden_by_log_pipeline(self):
        self.simulate_linux()
        self.built_kernel()
        self.image()
        result = self.invoke("boot", "linux-5.15.2", MOCK_QEMU_EXIT="7")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertIn("qemu", self.calls.read_text())
        self.assertTrue(list((self.root / "logs").glob("qemu-*.log")))

    def test_lock_contention_blocks_image_operation(self):
        self.simulate_linux()
        result = self.invoke("make-rootfs.sh", MOCK_LOCK_EXIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another build", result.stderr)
        self.assertFalse(self.calls.exists())

    def prepare_failed_module_install(self):
        self.simulate_linux()
        self.built_kernel()
        self.image()
        for name in ("make", "gcc-11", "mount", "umount"):
            self.mock(name, "exit 0")
        self.mock("mountpoint", 'test -f "$MOCK_STATE/mounted"')
        self.mock("sudo", '''
echo "$1" >> "$MOCK_CALLS"
case "$1" in
    -v) exit 0 ;;
    mount) touch "$MOCK_STATE/mounted" ;;
    make) exit 42 ;;
    umount)
        if [[ ${MOCK_UNMOUNT_FAIL:-0} == 1 ]]; then exit 8; fi
        rm -f "$MOCK_STATE/mounted" ;;
    *) exit 99 ;;
esac''')

    def test_failed_module_install_unmounts_and_preserves_image(self):
        self.prepare_failed_module_install()
        result = self.invoke("make-rootfs.sh", "--update-modules")
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertIn("umount", self.calls.read_text())
        self.assertFalse((self.root / "mounted").exists())
        self.assertFalse(list((self.root / ".cache").glob("rootfs-mount.*")))
        self.assertEqual((self.root / "images/rootfs.img").read_bytes(), b"existing-user-data")

    def test_failed_unmount_retains_mount_directory_for_recovery(self):
        self.prepare_failed_module_install()
        result = self.invoke("make-rootfs.sh", "--update-modules", MOCK_UNMOUNT_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cleanup failed. Mount left at:", result.stderr)
        self.assertTrue(list((self.root / ".cache").glob("rootfs-mount.*")))

    def test_corrupt_archive_stops_before_extracting_source(self):
        self.simulate_linux()
        for name in ("make", "gcc-11", "bison", "flex", "bc"):
            self.mock(name, "exit 0")
        cache = self.root / ".cache"
        cache.mkdir(exist_ok=True)
        (cache / "linux-5.15.2.tar.xz").write_bytes(b"not the official archive")
        result = self.invoke("build-kernel.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAILED", result.stdout + result.stderr)
        self.assertFalse((self.root / "src/linux-5.15.2").exists())
        self.assertFalse(self.calls.exists())



    @staticmethod
    def boot_config():
        return """CONFIG_VIRTIO_PCI=y
CONFIG_VIRTIO_BLK=y
CONFIG_EXT4_FS=y
CONFIG_DEVTMPFS=y
CONFIG_DEVTMPFS_MOUNT=y
CONFIG_SERIAL_8250_CONSOLE=y
CONFIG_LOCALVERSION="-kernel-study"
"""

    def prepare_fake_kernel_build(self, config=None, with_source=True):
        self.simulate_linux()
        for name in ("gcc-11", "bison", "flex", "bc"):
            self.mock(name, "exit 0")
        self.mock("curl", "exit 99")  # These tests never download anything.
        if with_source:
            source = self.root / "src/linux-5.15.2"
            source.mkdir(parents=True)
            (source / "Makefile").write_text("# kernel source fixture\n", encoding="utf-8")
            if config is not None:
                (source / ".config").write_text(config, encoding="utf-8", newline="\n")
        self.mock("make", '''
if printenv KBUILD_OUTPUT >/dev/null; then exit 96; fi
for arg in "$@"; do
    [[ $arg != O=* ]] || exit 97
done
echo "$*" >> "$MOCK_CALLS"
if [[ " $* " == *" bzImage modules "* ]]; then
    mkdir -p src/linux-5.15.2/arch/x86/boot src/linux-5.15.2/include/config
    echo test-image > src/linux-5.15.2/arch/x86/boot/bzImage
    echo 5.15.2-kernel-study > src/linux-5.15.2/include/config/kernel.release
    touch src/linux-5.15.2/modules.order
fi
''')

    def test_separate_build_config_is_reused_without_redirecting_output(self):
        self.prepare_fake_kernel_build()
        legacy = self.root / "build/linux-5.15.2/.config"
        legacy.parent.mkdir(parents=True)
        config = self.boot_config() + "CONFIG_TEST_PREVIOUS_SETTING=y\n"
        legacy.write_text(config, encoding="utf-8", newline="\n")
        result = self.invoke("build-kernel.sh", KBUILD_OUTPUT=str(self.root / "obsolete-output"))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        source = self.root / "src/linux-5.15.2"
        self.assertEqual((source / ".config").read_text(encoding="utf-8"), config)
        self.assertEqual(legacy.read_text(encoding="utf-8"), config)
        self.assertTrue((source / "arch/x86/boot/bzImage").is_file())
        self.assertFalse((self.root / "obsolete-output").exists())

    def test_existing_source_config_takes_precedence_over_old_build(self):
        config = self.boot_config() + "CONFIG_TEST_CURRENT_SETTING=y\n"
        self.prepare_fake_kernel_build(config=config)
        legacy = self.root / "build/linux-5.15.2/.config"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("old configuration must not replace current settings\n", encoding="utf-8", newline="\n")
        result = self.invoke("build-kernel.sh")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((self.root / "src/linux-5.15.2/.config").read_text(encoding="utf-8"), config)

    def test_first_build_extracts_sources_before_building_in_tree(self):
        self.prepare_fake_kernel_build(with_source=False)
        cache = self.root / ".cache"
        cache.mkdir()
        archive = cache / "linux-5.15.2.tar.xz"
        with tarfile.open(archive, "w:xz") as output:
            for name, text in {"Makefile": "# kernel source fixture\n", ".config": self.boot_config()}.items():
                data = text.encode("utf-8")
                entry = tarfile.TarInfo("linux-5.15.2/" + name)
                entry.size = len(data)
                output.addfile(entry, io.BytesIO(data))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        settings = self.root / "config/lab.conf.sh"
        settings.write_text(settings.read_text(encoding="utf-8") + f'\nKERNEL_SHA256={digest}\n',
                            encoding="utf-8", newline="\n")
        result = self.invoke("build-kernel.sh")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        source = self.root / "src/linux-5.15.2"
        self.assertEqual((source / "Makefile").read_text(encoding="utf-8"), "# kernel source fixture\n")
        self.assertTrue((source / "arch/x86/boot/bzImage").is_file())
        self.assertFalse((self.root / "build").exists())


if __name__ == "__main__":
    unittest.main()
