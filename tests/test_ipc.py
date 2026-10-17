"""Service socket: requests, errors, events and authorization."""

import os
import shutil
import tempfile
import threading
import unittest

from bytekeys import ipc
from bytekeys.engine import Engine
from bytekeys.hw import demo

from .fakesys import FakeSys, wait_for


class IpcTest(unittest.TestCase):
    def setUp(self):
        self.fs = FakeSys()
        self.tmp = tempfile.mkdtemp(prefix="bk")
        self.engine = Engine(os.path.join(self.tmp, "state"), watch_input=False, mode="service",
                             discovery=lambda opts: demo.discover())
        self.engine.start()
        self.path = os.path.join(self.tmp, "s.sock")
        self.server = ipc.Server(self.engine, self.path)
        self.server.start()
        self.client = ipc.SocketClient(self.path)

    def tearDown(self):
        self.client.close()
        self.server.stop()
        self.engine.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.fs.close()

    def test_round_trip(self):
        hello = self.client.call("hello")
        self.assertEqual(hello["mode"], "service")
        devices = self.client.call("devices")
        self.assertEqual(len(devices), 4)
        views = self.client.call("set", device="demo:rgb", changes={"color": "#00ff00"})
        self.assertEqual(views[0]["state"]["color"], "#00ff00")
        self.assertIn("ByteKeys", self.client.call("report"))

    def test_errors(self):
        with self.assertRaises(ipc.ServiceError) as ctx:
            self.client.call("set", device="demo:rgb", changes={"color": "bogus"})
        self.assertEqual(ctx.exception.code, "invalid")
        with self.assertRaises(ipc.ServiceError) as ctx:
            self.client.call("device", device="nope")
        self.assertEqual(ctx.exception.code, "not_found")
        with self.assertRaises(ipc.ServiceError) as ctx:
            self.client.call("format_disk")
        self.assertEqual(ctx.exception.code, "unknown_method")

    def test_events(self):
        events = []
        got = threading.Event()

        def on_event(kind, data):
            events.append((kind, data))
            if kind == "state" and data.get("device") == "demo:4zone":
                got.set()

        self.client.subscribe(on_event)
        self.client.call("set", device="demo:4zone", changes={"brightness": 50})
        self.assertTrue(got.wait(3))

    def test_authorization(self):
        self.assertTrue(ipc.authorized(os.getuid()))
        sessions = os.path.join(self.tmp, "sessions")
        os.makedirs(sessions)
        with open(os.path.join(sessions, "2"), "w") as f:
            f.write("UID=4242\nACTIVE=1\nREMOTE=0\nCLASS=user\n")
        with open(os.path.join(sessions, "7"), "w") as f:
            f.write("UID=4343\nACTIVE=1\nREMOTE=1\nCLASS=user\n")
        self.assertTrue(ipc._active_local_session(4242, sessions))
        self.assertFalse(ipc._active_local_session(4343, sessions), "remote sessions may not write")
        self.assertFalse(ipc._active_local_session(1, sessions))
        self.assertIsNone(ipc._active_local_session(1, os.path.join(self.tmp, "missing")))


if __name__ == "__main__":
    unittest.main()
