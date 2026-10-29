import os
import stat
import tempfile
import unittest

from PyQt6.QtCore import QEventLoop, QTimer

from g733_tray import headsetcontrol
from tests import qt

FAKE = """#!/bin/sh
case "$*" in
  *-b*) echo '{"devices":[{"battery":{"status":"BATTERY_AVAILABLE","level":66}}]}' ;;
esac
exit 0
"""


class WrapperReentrancy(unittest.TestCase):
    def setUp(self):
        self.app = qt.app()
        self.dir = tempfile.TemporaryDirectory()
        path = os.path.join(self.dir.name, "fake-headsetcontrol")
        with open(path, "w") as f:
            f.write(FAKE)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        self.original = headsetcontrol.BINARY
        headsetcontrol.BINARY = path

    def tearDown(self):
        headsetcontrol.BINARY = self.original
        self.dir.cleanup()

    def run_until(self, done, timeout_ms=5000):
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        check = QTimer()
        check.timeout.connect(lambda: loop.quit() if done() else None)
        check.start(20)
        loop.exec()

    def test_callback_may_start_next_command(self):
        """The reconciliation after setting the light (started in the callback) must not get lost."""
        hc = headsetcontrol.Headsetcontrol()
        results = []
        hc.set_light(True, lambda ok: hc.battery(lambda status, error: results.append((status, error))))
        self.run_until(lambda: results)
        self.assertEqual(len(results), 1, "result of the call started in the callback is missing")
        status, error = results[0]
        self.assertIsNone(error)
        self.assertEqual(status.level, 66)

    def test_commands_run_in_order(self):
        hc = headsetcontrol.Headsetcontrol()
        order = []
        hc.set_light(True, lambda ok: order.append("licht"))
        hc.battery(lambda status, error: order.append("akku"))
        hc.set_sidetone(10, lambda ok: order.append("sidetone"))
        self.run_until(lambda: len(order) == 3)
        self.assertEqual(order, ["licht", "akku", "sidetone"])


if __name__ == "__main__":
    unittest.main()
