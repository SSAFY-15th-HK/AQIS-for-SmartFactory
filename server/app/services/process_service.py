from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass


@dataclass
class ProcessStatus:
    running: bool
    pid: int | None
    command: str
    started_at: float | None
    stopped_at: float | None
    returncode: int | None


class AqisProcessService:
    def __init__(self, start_command: str) -> None:
        self.start_command = start_command
        self._process: subprocess.Popen | None = None
        self._started_at: float | None = None
        self._stopped_at: float | None = None

    def start(self) -> dict:
        if self.is_running():
            return {"status": "already_running", "process": self.status()}

        self._process = subprocess.Popen(
            ["bash", "-lc", self.start_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
        )
        self._started_at = time.time()
        self._stopped_at = None
        return {"status": "started", "process": self.status()}

    def stop(self, timeout_sec: float = 8.0) -> dict:
        if not self._process:
            self._stopped_at = time.time()
            return {"status": "not_running", "process": self.status()}

        if self._process.poll() is None:
            os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            try:
                self._process.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                self._process.wait(timeout=2.0)

        self._stopped_at = time.time()
        return {"status": "stopped", "process": self.status()}

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def status(self) -> dict:
        pid = self._process.pid if self._process else None
        return ProcessStatus(
            running=self.is_running(),
            pid=pid,
            command=self.start_command,
            started_at=self._started_at,
            stopped_at=self._stopped_at,
            returncode=self._process.poll() if self._process else None,
        ).__dict__
