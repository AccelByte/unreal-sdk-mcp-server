from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_BRIDGE_URL = "http://127.0.0.1:48757"


def bridge_url(args: dict[str, Any]) -> str:
    return str(args.get("bridgeUrl") or DEFAULT_BRIDGE_URL).rstrip("/")


def resolve_project_root(project_path: str | None, workspace_root: str | None = None) -> Path:
    base = Path(workspace_root or ".").resolve()
    raw_path = Path(project_path or base)
    candidate = raw_path if raw_path.is_absolute() else base / raw_path
    candidate = candidate.resolve()
    if candidate.is_file() and candidate.suffix == ".uproject":
        candidate = candidate.parent
    if not candidate.exists() or not candidate.is_dir():
        raise ValueError(f"Project path is not a directory: {candidate}")
    if not list(candidate.glob("*.uproject")):
        raise ValueError(f"No .uproject file found in project root: {candidate}")
    return candidate


def project_file(project_root: Path) -> Path:
    projects = sorted(project_root.glob("*.uproject"))
    if not projects:
        raise ValueError(f"No .uproject file found in project root: {project_root}")
    return projects[0]
