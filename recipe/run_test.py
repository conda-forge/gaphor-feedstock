"""Smoke tests for ``gaphor`` CLI."""

import json
import os
import textwrap
import atexit
from importlib.util import find_spec
from subprocess import PIPE, STDOUT
import tempfile
import contextlib
import sys
from psutil import Popen, wait_procs, NoSuchProcess
import platform
import shutil
from pathlib import Path

PKG_VERSION = os.environ["PKG_VERSION"]
IS_LINUX = platform.system() == "Linux"
PYTEST_ARGS = ["-vvs", "--color=yes", "--tb=long", __file__]


def test_help() -> None:
    """Get the help from CLI."""
    rc, _ = _run(["gaphor", "--help"])
    assert rc == 0, "failed to get help"


def test_version() -> None:
    """Get the version from the CLI."""
    rc, output = _run(["gaphor", "--version"])
    assert rc == 0, "failed to get version"
    assert PKG_VERSION in output, "unexpected version"


def test_self_test() -> None:
    """Install schema and run the self-test CLI."""
    share = Path(sys.prefix) / "Library" / "share"
    if not share.is_dir():
        share = Path(sys.prefix) / "share"
    schemas_dir = share / "glib-2.0" / "schemas"
    rc, _ = _run(["gaphor", "install-schemas", "--schemas-dir", str(schemas_dir)])
    assert rc == 0, "failed to install schemas"
    os.environ["GSETTINGS_SCHEMA_DIR"] = str(schemas_dir)
    rc, _ = _run_self_test()
    assert rc == 0, "failed self-test"


def test_menu_launcher() -> None:
    """Ship the menuinst launcher and platform icon."""
    menu = Path(sys.prefix) / "Menu"
    icons = {"Linux": "gaphor.png", "Darwin": "gaphor.icns", "Windows": "gaphor.ico"}
    for name in ("gaphor.json", icons[platform.system()]):
        assert (menu / name).is_file(), f"missing {name}"
    items = json.loads((menu / "gaphor.json").read_text(encoding="utf-8"))["menu_items"]
    assert isinstance(items, list), "menu_items is not a list"


def test_translations() -> None:
    """Ship compiled translation catalogues."""
    package = Path(find_spec("gaphor").origin).parent
    mo_file = package / "locale" / "de" / "LC_MESSAGES" / "gaphor.mo"
    assert mo_file.is_file(), "missing German translation"


def _run_self_test() -> tuple[int, str]:
    command = ["gaphor", "self-test"]
    if not IS_LINUX:
        return _run(command)
    if shutil.which("xvfb-run"):
        return _run(["xvfb-run", *command])
    if shutil.which("mutter"):
        display = "wayland-gaphor-test"
        env = {
            **os.environ,
            "GDK_BACKEND": "wayland",
            "WAYLAND_DISPLAY": display,
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR")
            or tempfile.gettempdir(),
        }
        compositor = [
            "dbus-run-session",
            "--",
            "mutter",
            "--headless",
            "--wayland",
            "--no-x11",
            "--virtual-monitor=1024x768",
            "--wayland-display",
            display,
            "--",
            *command,
        ]
        return _run(compositor, env=env)
    raise RuntimeError(
        "self-test requires xvfb-run or mutter on Linux; see recipe/yum_requirements.txt"
    )


def _run(args, env=None) -> tuple[int, str]:
    """Run a CLI defensively and slowly, because windows."""
    print(f">>> {args}", flush=True)
    proc = Popen(args, stdout=PIPE, stderr=STDOUT, encoding="utf-8", env=env)
    atexit.register(_stop, proc)
    output, _ = proc.communicate()
    log_file = Path("gaphor-self-test.txt")
    if args == ["gaphor", "self-test"] and log_file.is_file():
        output += log_file.read_text(encoding="utf-8")
    print(textwrap.indent(output, "\t"), flush=True)
    _stop(proc)
    return proc.returncode, output


def _stop(proc: Popen) -> None:
    procs: list[Popen] = []
    with contextlib.suppress(NoSuchProcess):
        procs = [*proc.children(), proc]
    print(f"... {len(procs)} processes need stopping")
    if not procs:
        return
    for p in procs:
        p.terminate()
    _, alive = wait_procs(procs, timeout=3)
    for p in alive:
        p.kill()
        p.wait()
    print("... return codes", [p.returncode for p in procs], flush=True)


if __name__ == "__main__":
    # extra cwd stuff for windows cleanup issues
    with tempfile.TemporaryDirectory() as td:
        test_proc = Popen([sys.executable, "-m", "pytest", *PYTEST_ARGS], cwd=td)
        test_proc.wait()
    sys.exit(test_proc.returncode)
