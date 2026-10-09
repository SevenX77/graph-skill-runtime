"""Regression evidence for the narrowly allowed native compilation boundary."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))

import native_build
from ownership import InstallError


class NativeBuildTests(unittest.TestCase):
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
