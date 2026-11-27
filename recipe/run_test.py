"""Smoke tests for ``gaphor`` CLI."""

import os
import textwrap
import atexit
from subprocess import PIPE, STDOUT
import tempfile
import contextlib
import sys
from psutil import Popen, wait_procs, NoSuchProcess
import platform
import shutil
from pathlib import Path

import pytest

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


@pytest.mark.skipif(not IS_LINUX, reason="Linux-specific command selection")
def test_self_test_uses_xvfb_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/xvfb-run")
    assert _self_test_command() == ["/usr/bin/xvfb-run", "gaphor", "self-test"]


@pytest.mark.skipif(not IS_LINUX, reason="Linux-specific command selection")
def test_self_test_requires_xvfb_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="xvfb-run"):
        _self_test_command()


def test_self_test() -> None:
    """Install schema and run the self-test CLI."""
    schemas_dir = Path(sys.prefix) / "share" / "glib-2.0" / "schemas"
    rc, _ = _run(["gaphor", "install-schemas", "--schemas-dir", str(schemas_dir)])
    assert rc == 0, "failed to install schemas"
    os.environ["GSETTINGS_SCHEMA_DIR"] = str(schemas_dir)
    rc, _ = _run(_self_test_command())
    assert rc == 0, "failed self-test"


def _self_test_command() -> list[str]:
    command = ["gaphor", "self-test"]
    if not IS_LINUX:
        return command
    xvfb_run = shutil.which("xvfb-run")
    if not xvfb_run:
        raise RuntimeError(
            "self-test requires xvfb-run on Linux; see recipe/yum_requirements.txt"
        )
    return [xvfb_run, *command]


def _run(args) -> tuple[int, str]:
    """Run a CLI defensively and slowly, because windows."""
    print(f">>> {args}", flush=True)
    proc = Popen(args, stdout=PIPE, stderr=STDOUT, encoding="utf-8")

    def stop() -> None:
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

    atexit.register(stop)
    output, _ = proc.communicate()
    print(textwrap.indent(output, "\t"), flush=True)
    stop()
    return proc.returncode, output


if __name__ == "__main__":
    # extra cwd stuff for windows cleanup issues
    with tempfile.TemporaryDirectory() as td:
        test_proc = Popen([sys.executable, "-m", "pytest", *PYTEST_ARGS], cwd=td)
        test_proc.wait()
    sys.exit(test_proc.returncode)
