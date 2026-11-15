#!/usr/bin/env python3
"""Start the two teaching printers once and collect their exit statuses."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


class Lab:
    def __init__(self) -> None:
        work = Path("/work")
        runs = work / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        prefix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-")
        self.directory = Path(tempfile.mkdtemp(prefix=prefix, dir=runs))
        self.children: dict[int, subprocess.Popen] = {}
        self.printers: dict[str, dict] = {}
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.cpu = min(os.sched_getaffinity(0))
        self.work = 2_000_000
        self.stopping = False

    def request_stop(self, _signum, _frame) -> None:
        self.stopping = True

    def save_status(self) -> None:
        status = {
            "run_id": self.directory.name,
            "started_at": self.started_at,
            "cpu": self.cpu,
            "work": self.work,
            "printers": self.printers,
        }
        temporary = self.directory / ".status.json.tmp"
        temporary.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.directory / "status.json")

    def start(self) -> None:
        for name in ("red", "blue"):
            # Logs must stay outside the initially empty label directories.
            with (self.directory / f"{name}.log").open("w", encoding="utf-8") as log:
                child = subprocess.Popen(
                    [
                        "taskset", "-c", str(self.cpu),
                        sys.executable, "/opt/printer.py",
                        "--name", name,
                        "--output", str(self.directory / name),
                        "--interval", "0",
                        "--work", str(self.work),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            self.children[child.pid] = child
            self.printers[name] = {"pid": child.pid, "state": "alive", "exit_code": None}
            self.save_status()

        link = self.directory.parent.parent / f".current-{self.directory.name}"
        link.symlink_to(Path("runs") / self.directory.name)
        link.replace(self.directory.parent.parent / "current")

    def reap(self) -> None:
        changed = False
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            except InterruptedError:
                continue
            if pid == 0:
                break
            child = self.children.pop(pid, None)
            if child is None:
                # PID 1 also collects orphaned descendants of terminal sessions.
                continue
            child.returncode = os.waitstatus_to_exitcode(status)
            exit_code = child.returncode if child.returncode >= 0 else 128 - child.returncode
            for printer in self.printers.values():
                if printer["pid"] == pid:
                    printer.update(state="exited", exit_code=exit_code)
                    changed = True
                    break
        if changed:
            self.save_status()

    def send(self, signum: int) -> None:
        for pid in tuple(self.children):
            try:
                os.kill(pid, signum)
            except ProcessLookupError:
                pass

    def stop(self) -> None:
        self.reap()
        # A stopped process must resume before it can handle SIGTERM and clean up.
        self.send(signal.SIGCONT)
        self.send(signal.SIGTERM)
        deadline = time.monotonic() + 4
        while self.children and time.monotonic() < deadline:
            self.reap()
            time.sleep(0.05)
        if self.children:
            self.send(signal.SIGKILL)
            while self.children:
                self.reap()
                time.sleep(0.05)

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        try:
            self.start()
            while not self.stopping:
                self.reap()
                time.sleep(0.1)
        finally:
            self.stop()


if __name__ == "__main__":
    Lab().run()
