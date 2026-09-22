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


def _log_unavailable(config: LLMConfig, reason: str, *, exc_info: bool = False) -> None:
    """Record a degraded AI runtime without taking down the web service."""

    log.warning(
        "OpenCode free-model server unavailable; using deterministic fallback",
        extra={
            "event": "llm.opencode.server.unavailable",
            "model": config.opencode_model,
            "reason": reason,
        },
        exc_info=exc_info,
    )


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Stop an OpenCode child without leaving it to consume app resources."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


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
    if not config.opencode_server_autostart:
        log.info(
            "OpenCode server autostart disabled; using deterministic fallback",
            extra={
                "event": "llm.opencode.server.autostart_disabled",
                "model": config.opencode_model,
            },
        )
        yield
        return

    parsed = urlparse(config.opencode_server_url)
    try:
        server_port = parsed.port
    except ValueError:
        server_port = None
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or server_port is None
    ):
        _log_unavailable(
            config,
            "OPENCODE_SERVER_URL must be a loopback HTTP URL with an explicit port",
        )
        yield
        return
    if _healthy(config.opencode_server_url):
        yield
        return
    executable = _opencode_executable()
    if executable is None:
        _log_unavailable(
            config,
            "OPENCODE_TRANSPORT=cli requires the OpenCode executable",
        )
        yield
        return

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            [
                executable,
                "serve",
                "--hostname",
                parsed.hostname,
                "--port",
                str(server_port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    except OSError as error:
        _log_unavailable(config, str(error), exc_info=True)
        yield
        return
    try:
        deadline = time.monotonic() + 20.0
        startup_error = "OpenCode headless server did not become ready"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                startup_error = "OpenCode headless server stopped during startup"
                break
            if _healthy(config.opencode_server_url):
                log.info(
                    "OpenCode free-model server ready",
                    extra={
                        "event": "llm.opencode.server.ready",
                        "model": config.opencode_model,
                    },
                )
                startup_error = ""
                break
            time.sleep(0.2)
        if startup_error:
            _log_unavailable(config, startup_error)
            _stop_process(process)
        yield
    finally:
        _stop_process(process)
