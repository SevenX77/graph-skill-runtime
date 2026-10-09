"""Regression evidence for the narrowly allowed native compilation boundary."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))

import native_build
import runtime_layout
from ownership import InstallError


class NativeBuildTests(unittest.TestCase):
    def test_universal_mac_python_uses_running_architecture(self):
        for machine, expected in [("x86_64", "darwin-x64"), ("arm64", "darwin-arm64")]:
            with self.subTest(machine=machine), patch.object(runtime_layout.sys, "platform", "darwin"), patch.object(
                runtime_layout.sysconfig, "get_platform", return_value="macosx-10.9-universal2"
            ), patch.object(runtime_layout.platform, "machine", return_value=machine):
                self.assertEqual(runtime_layout.current_target(), expected)

    def test_cross_platform_compilation_is_rejected(self):
        with patch.object(native_build, "current_target", return_value="win32-x64"):
            with self.assertRaisesRegex(InstallError, "Intel macOS build host"):
                native_build.require_native_target("darwin-x64", {"package": "cryptography"})

    def test_other_source_builds_are_rejected(self):
        with self.assertRaisesRegex(InstallError, "defined only"):
            native_build.require_native_target("darwin-x64", {"package": "cffi"})
        with self.assertRaisesRegex(InstallError, "defined only"):
            native_build.require_native_target("win32-arm64", {"package": "cryptography"})

    def test_external_library_dependency_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            extension = site / "cryptography/hazmat/bindings/_rust.abi3.so"
            extension.parent.mkdir(parents=True)
            extension.write_bytes(b"fixture")
            with patch.object(native_build.subprocess, "run"), patch.object(
                native_build.subprocess, "check_output",
                return_value=f"{extension}:\n\t/usr/local/opt/openssl/lib/libcrypto.dylib (compatibility version 4)\n",
            ) as capture:
                with self.assertRaisesRegex(InstallError, "build-machine library"):
                    native_build.inspect_extension(site, site / "python", {})
                self.assertEqual(capture.call_count, 1)


if __name__ == "__main__":
    unittest.main()
