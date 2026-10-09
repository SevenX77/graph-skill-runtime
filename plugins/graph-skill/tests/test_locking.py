"""Installation contention and interrupted-process recovery use real OS locks."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGING = Path(__file__).resolve().parents[1] / "packaging"
sys.path.insert(0, str(PACKAGING))
from locking import installer_lock, process_running
from ownership import InstallError


class InstallerLockTests(unittest.TestCase):
    def test_live_legacy_owner_and_unknown_marker_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            marker = state / "installer.lock"
            for content in (str(os.getpid()), "", "not-a-pid", "0", "-1", str(2**40)):
                marker.write_text(content)
                with self.assertRaises(InstallError):
                    with installer_lock(state):
                        self.fail("must not acquire uncertain/live ownership")
                self.assertEqual(marker.read_text(), content)

    def test_dead_legacy_pid_is_recovered_and_normal_exit_cleans_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            process = subprocess.Popen([sys.executable, "-c", "pass"])
            process.wait(timeout=10)
            self.assertFalse(process_running(process.pid))
            marker = state / "installer.lock"
            marker.write_text(str(process.pid))
            messages = []
            with installer_lock(state, messages.append):
                self.assertEqual(marker.read_text(), str(os.getpid()))
            self.assertFalse(marker.exists())
            self.assertTrue(messages)
            with installer_lock(state):
                self.assertTrue(marker.exists())

    def test_concurrent_owner_excluded_then_killed_owner_recovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            script = (
                "import sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(PACKAGING)!r}); "
                "from locking import installer_lock\n"
                f"with installer_lock(Path({str(state)!r})):\n"
                " print('acquired', flush=True)\n"
                " sys.stdin.read()\n"
            )
            child = subprocess.Popen([sys.executable, "-u", "-c", script], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "acquired")
                marker = (state / "installer.lock").read_bytes()
                with self.assertRaisesRegex(InstallError, "Another installer"):
                    with installer_lock(state):
                        self.fail("concurrent installer admitted")
                self.assertEqual((state / "installer.lock").read_bytes(), marker)
                child.kill()
                child.wait(timeout=10)
                with installer_lock(state):
                    self.assertEqual((state / "installer.lock").read_text(), str(os.getpid()))
            finally:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)

    def test_inaccessible_process_and_changed_record_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            marker = state / "installer.lock"
            marker.write_text("123")
            with patch("locking.process_running", return_value=True):
                with self.assertRaises(InstallError):
                    with installer_lock(state):
                        pass
            self.assertEqual(marker.read_text(), "123")
            marker.unlink()
            with self.assertRaisesRegex(InstallError, "record changed"):
                with installer_lock(state):
                    marker.write_text("other owner")
            self.assertEqual(marker.read_text(), "other owner")


if __name__ == "__main__":
    unittest.main()
