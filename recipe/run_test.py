"""Smoke tests for ``gaphor`` CLI."""

import os
import pytest
import textwrap
import atexit
from subprocess import PIPE, STDOUT
from pathlib import Path
import tempfile
import time
import shutil
import contextlib
import sys
from psutil import Popen, wait_procs, NoSuchProcess
import platform

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
    rc, _ = _run(["gaphor", "install-schemas"])
    assert rc == 0, "failed to install schemas"
    rc, _ = _run((["xvfb-run"] if IS_LINUX else []) + ["gaphor", "self-test"])
    assert rc == 0, "failed self-test"


def _run(args) -> tuple[int, str]:
    """Run a CLI defensively and slowly, because windows."""
    print(f">>> {args}", flush=True)
    proc = Popen(args, stdout=PIPE, stderr=STDOUT, encoding="utf-8")

    def stop() -> None:
        procs: Popen = []
        with contextlib.suppress(NoSuchProcess):
            procs = [*proc.children(), proc]
        if not procs:
            return
        for p in procs:
            p.terminate()
        _, alive = wait_procs(procs, timeout=3)
        for p in alive:
            p.kill()
            p.wait()
        time.sleep(5)

    atexit.register(stop)
    output, _ = proc.communicate()
    print(textwrap.indent(output, "\t"), flush=True)
    stop()
    return proc.returncode, output


if __name__ == "__main__":
    os.environ.update(
        # for linux
        DISPLAY=":1",
        # for windows
        PYTHONIOENCODING="utf-8",
    )

    # extra cwd stuff for windows cleanup issues
    td = Path(tempfile.mkdtemp())
    old_cwd = Path.cwd()
    os.chdir(f"{td}")
    rc = pytest.main(PYTEST_ARGS)
    os.chdir(f"{old_cwd}")
    shutil.rmtree(td, ignore_errors=True)
    sys.exit(rc)
