"""Details for the About tab: version, project URL, installation type, headsetcontrol version."""
import re
import shutil
import subprocess
from pathlib import Path

from .autostart import DATA_HOME
from .i18n import N_

from . import __version__

USER_VENV = DATA_HOME / "g733-tray" / "venv"  # install.sh puts the program here
GITHUB_URL = "https://github.com/Spider19996/HeadsetControl-G733-Tray"
LICENSE = "MIT"
MIN_HEADSETCONTROL = (4, 2, 0)  # older versions do not fully support the G733 or the JSON output

# package managers that can be asked "who owns this file?"
PACKAGE_MANAGERS = (
    ("dpkg", ["dpkg", "-S"], N_("install.deb")),
    ("rpm", ["rpm", "-qf"], N_("install.rpm")),
    ("pacman", ["pacman", "-Qo"], N_("install.arch")),
)


def _owned_by_package(command, path):
    try:
        result = subprocess.run(command + [path], capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def install_kind(module_dir=None, owned_by_package=_owned_by_package, which=shutil.which, user_venv=USER_VENV):
    """Describes how the program was installed (derived from the location of the package)."""
    here = Path(module_dir or Path(__file__).resolve().parent)
    if (here.parent / "pyproject.toml").exists():
        return N_("install.source_tree")
    if here.is_relative_to(user_venv):
        return N_("install.user")
    for binary, command, label in PACKAGE_MANAGERS:
        if which(binary) and owned_by_package(command, str(here / "__init__.py")):
            return label
    if str(here).startswith("/usr/"):
        return N_("install.system")
    return N_("install.pip")


def parse_version(text):
    """(4, 2, 0) from "HeadsetControl 4.2.0"; None if there is no version number in the text."""
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(part or 0) for part in match.groups()) if match else None


def headsetcontrol_too_old(text):
    """True if the version is known and lower than MIN_HEADSETCONTROL."""
    version = parse_version(text)
    return version is not None and version < MIN_HEADSETCONTROL


def headsetcontrol_version():
    """Output of `headsetcontrol --version` (first line), or None if it is not installed."""
    binary = shutil.which("headsetcontrol")
    if not binary:
        return None
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = out.strip().splitlines()
    return lines[0].strip() if lines else None
