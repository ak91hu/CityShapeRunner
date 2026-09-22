"""Lifecycle management for the loopback-only OpenCode headless server."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..config import LLMConfig

log = logging.getLogger(__name__)


def _opencode_executable(*, platform_name: str | None = None) -> str | None:
    executable = shutil.which("opencode")
    if executable is None or (platform_name or os.name) != "nt":
        return executable
    # npm exposes a .cmd shim on Windows. Popen would own the short-lived cmd
    # wrapper rather than the server binary, leaving the child behind on exit.
    # Prefer the package's installed native executable when it is present.
    if Path(executable).suffix.casefold() in {".bat", ".cmd", ".ps1"}:
        native = (
            Path(executable).parent
            / "node_modules"
            / "opencode-ai"
            / "bin"
            / "opencode.exe"
        )
        if native.is_file():
            return str(native)
    return executable


def _healthy(server_url: str) -> bool:
    try:
        return httpx.get(
            f"{server_url.rstrip('/')}/global/health",
            timeout=1.0,
        ).status_code == 200
    except httpx.HTTPError:
        return False


@contextmanager
def managed_opencode_server(config: LLMConfig) -> Iterator[None]:
    """Start one private server for the process when CLI transport is selected."""

    if config.opencode_transport != "cli" or not config.opencode_key:
        yield
        return
    if _healthy(config.opencode_server_url):
        yield
        return

    parsed = urlparse(config.opencode_server_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.port is None
    ):
        raise RuntimeError(
            "OPENCODE_SERVER_URL must be a loopback HTTP URL with an explicit port"
        )
    executable = _opencode_executable()
    if executable is None:
        raise RuntimeError(
            "OPENCODE_TRANSPORT=cli requires the OpenCode executable"
        )

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [
            executable,
            "serve",
            "--hostname",
            parsed.hostname,
            "--port",
            str(parsed.port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    try:
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("OpenCode headless server stopped during startup")
            if _healthy(config.opencode_server_url):
                log.info(
                    "OpenCode free-model server ready",
                    extra={
                        "event": "llm.opencode.server.ready",
                        "model": config.opencode_model,
                    },
                )
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("OpenCode headless server did not become ready")
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
