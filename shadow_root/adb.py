"""ADB-backed helpers used by the local nScreen agent runner."""

from __future__ import annotations

import shlex
import subprocess
from typing import Callable

from .config import ShadowConfig


class AdbClient:
    def __init__(
        self,
        config: ShadowConfig,
        *,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
        popen_factory: Callable[..., subprocess.Popen[str]] | None = None,
    ) -> None:
        self.config = config
        self.runner = runner or self._run
        self.popen_factory = popen_factory or subprocess.Popen

    def shell(self, command: str | list[str], *, root: bool = False) -> str:
        args = self._adb_args(["shell", *self._shell_args(command, root=root)])
        completed = self.runner(args)
        if completed.returncode != 0:
            output = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(output or f"adb command failed: {' '.join(args)}")
        return completed.stdout

    def push_file(self, local_path: str, remote_path: str) -> str:
        result = self.runner(self._adb_args(["push", str(local_path), str(remote_path)]))
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(output or f"adb push failed: {remote_path}")
        return remote_path

    def start_android_agent(self, remote_jar: str, main_class: str, args: list[str]) -> subprocess.Popen[str]:
        classpath = f"CLASSPATH={shlex.quote(remote_jar)}"
        command = " ".join([classpath, "app_process", "/", shlex.quote(main_class), *(shlex.quote(str(arg)) for arg in args)])
        return self.popen_factory(
            self._adb_args(["shell", "su", "-c", command]),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def kill_processes_matching(self, pattern: str, *, root: bool = True) -> None:
        try:
            output = self.shell(["ps", "-A", "-o", "PID,ARGS"], root=root)
        except Exception:
            return
        for line in output.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            pid, args = parts
            if pattern not in args:
                continue
            try:
                self.shell(["kill", "-9", pid], root=root)
            except Exception:
                continue

    def _adb_args(self, args: list[str]) -> list[str]:
        adb_args = [self.config.adb_path]
        if self.config.adb_serial:
            adb_args.extend(["-s", self.config.adb_serial])
        return [*adb_args, *args]

    def _shell_args(self, command: str | list[str], *, root: bool = False) -> list[str]:
        if root:
            if isinstance(command, str):
                shell_command = command
            else:
                shell_command = " ".join(shlex.quote(str(part)) for part in command)
            return ["su", "-c", shell_command]
        if isinstance(command, str):
            return [command]
        return [str(part) for part in command]

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, check=False, text=True, capture_output=True, encoding="utf-8")
