"""The bytekeys command line tool, against an in-process engine with simulated hardware."""

import contextlib
import io
import os
import shutil
import tempfile
import unittest

from bytekeys import cli

from .fakesys import FakeSys


class CliTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeSys()
        self.fs.dmi(sys_vendor="ByteKeys", product_name="Test Laptop")
        self.dir = tempfile.mkdtemp(prefix="bk-cli-")
        self.saved = os.environ.get("XDG_STATE_HOME")
        os.environ["XDG_STATE_HOME"] = self.dir

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("XDG_STATE_HOME", None)
        else:
            os.environ["XDG_STATE_HOME"] = self.saved
        shutil.rmtree(self.dir, ignore_errors=True)
        self.fs.close()

    def run_cli(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(["--local", "--demo", *args])
        return code, out.getvalue()

    def test_status(self):
        code, out = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("Demo RGB Keyboard", out)

    def test_perf(self):
        code, out = self.run_cli("perf", "performance")
        self.assertEqual(code, 0)
        self.assertIn("[Performance]", out)
        code, out = self.run_cli("perf", "turbo")
        self.assertEqual(code, 2)
        self.assertIn("not offered", out)

    def test_fans(self):
        code, out = self.run_cli("fans", "boost", "on")
        self.assertEqual(code, 0)
        self.assertIn("Full fan speed: on", out)
        code, out = self.run_cli("fans", "custom", "1")
        self.assertIn("CPU fan (fan 1): custom curve", out)
        code, out = self.run_cli("fans", "reset")
        self.assertEqual(code, 2)

    def test_charge_limit(self):
        code, out = self.run_cli("charge-limit", "60")
        self.assertEqual(code, 0)
        self.assertIn("Charge limit: 60%", out)
