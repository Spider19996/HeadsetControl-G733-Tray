"""Logging: log file (cleared at every program start) and optionally output in the terminal (--verbose)."""
import logging
import logging.handlers
import os
import sys
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "g733-tray"
LOG_PATH = STATE_DIR / "g733-tray.log"
TEST_LOG_PATH = STATE_DIR / "g733-tray-test.log"  # separate file so a test run does not clear the real log
MAX_BYTES = 1_000_000  # safeguard for very long runtimes; enough for many days

_active_path = None


def log_path():
    """Path of the current log file, or None if it could not be created."""
    return _active_path


def setup(verbose=False, test_mode=False):
    """Sets up logging. Without --verbose: file at INFO, terminal only warnings.
    With --verbose: file and terminal at DEBUG."""
    global _active_path
    logger = logging.getLogger("g733")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(formatter)
    logger.addHandler(console)

    path = TEST_LOG_PATH if test_mode else LOG_PATH
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text("")  # clear at every start
        path.with_name(path.name + ".1").unlink(missing_ok=True)
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=1, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        _active_path = path
    except OSError as err:
        _active_path = None
        logger.warning("log file %s not writable: %s", path, err)
    return _active_path
