"""Provenance of a run: what code, configuration and environment produced a log.

Every record written with provenance carries an invocation id (one per command launch), the exact configuration and its
hash, the git commit, and package versions. Logs written before this existed have none; ``netwing.reproduce`` then
falls back to splitting a file by time gap. Nothing here changes what a run does.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from importlib import metadata
from pathlib import Path
from typing import Any


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=Path(__file__).resolve().parent, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return ""


def config_hash(config: dict[str, Any], model: str) -> str:
    """Stable SHA-256 of the configuration plus model (key order does not matter)."""
    blob = json.dumps({"config": config, "model": model}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def build(config: dict[str, Any], model: str, temperature: float | None = None) -> dict[str, Any]:
    """Provenance block for one invocation. ``temperature=None`` means the API default (the agent never sets one)."""
    commit = _git("rev-parse", "HEAD")
    return {
        "invocation_id": uuid.uuid4().hex,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "config": config,
        "config_hash": config_hash(config, model),
        "model": model,
        "temperature": temperature,
        "git_commit": commit,
        "git_dirty": bool(commit and _git("status", "--porcelain", "--untracked-files=no")),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "netwing_version": _version("netwing"),
        "anthropic_version": _version("anthropic"),
    }
