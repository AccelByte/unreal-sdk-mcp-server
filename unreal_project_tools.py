from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.request
from typing import Any

from _unreal_common import DEFAULT_BRIDGE_URL
from _unreal_common import project_file as _project_file
from _unreal_common import resolve_project_root as _project_root


DEFAULT_BUILD_TIMEOUT_SECONDS = 1800
DEFAULT_EDITOR_CLOSE_TIMEOUT_SECONDS = 30


class EditorProcessDetectionError(RuntimeError):
    pass


COMPILE_ERROR_PATTERNS = [
    re.compile(
        r"^(?P<file>[A-Za-z]:\\[^()\r\n]+)\((?P<line>\d+)\)\s*:\s*"
        r"(?P<level>fatal error|error|warning)\s+(?P<code>[A-Z]+\d+)\s*:\s*(?P<message>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<file>[^:\r\n]+):(?P<line>\d+):(?P<column>\d+):\s*"
        r"(?P<level>fatal error|error|warning):\s*(?P<message>.+)$",
        re.IGNORECASE,
    ),
]


def _permission_required(action: str) -> dict[str, Any]:
    return {
        "ok": False,
        "errors": [
            {
                "code": "permission_required",
                "message": f"userApproved: true is required before the tool can {action}.",
            }
        ],
    }


def _read_engine_association(uproject_path: Path) -> str | None:
    try:
        loaded = json.loads(uproject_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = loaded.get("EngineAssociation")
    return value if isinstance(value, str) and value else None


def _engine_association_to_folder_name(engine_association: str | None) -> str | None:
    if not engine_association:
        return None
    match = re.match(r"^(\d+)\.(\d+)", engine_association)
    if not match:
        return None
    return f"UE_{match.group(1)}.{match.group(2)}"


def _engine_root_from_registry(engine_association: str | None) -> Path | None:
    if sys.platform != "win32" or not engine_association:
        return None
    try:
        import winreg
    except ImportError:
        return None

    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Epic Games\Unreal Engine\Builds"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\EpicGames\Unreal Engine\Builds"),
    ]
    for hive, key_name in keys:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _value_type = winreg.QueryValueEx(key, engine_association)
        except OSError:
            continue
        candidate = Path(str(value))
        if candidate.exists():
            return candidate
    return None


def _common_engine_roots(engine_association: str | None = None) -> list[Path]:
    roots: list[Path] = []
    folder_name = _engine_association_to_folder_name(engine_association)
    if sys.platform == "win32":
        bases = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Epic Games",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Epic Games",
        ]
        for base in bases:
            if folder_name:
                roots.append(base / folder_name)
            if base.exists():
                roots.extend(sorted(path for path in base.glob("UE_*") if path.is_dir()))
    elif sys.platform == "darwin":
        base = Path("/Users/Shared/Epic Games")
        if folder_name:
            roots.append(base / folder_name)
        if base.exists():
            roots.extend(sorted(path for path in base.glob("UE_*") if path.is_dir()))
    return roots


def _path_from_engine_root(engine_root: str | Path, relative_path: str) -> Path:
    root = Path(engine_root)
    if root.name == "Engine":
        root = root.parent
    return root / "Engine" / relative_path


def _existing_path(path_value: str | Path | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    return candidate if candidate.exists() else None


def _resolve_engine_tool(
    args: dict[str, Any],
    project_file: Path,
    *,
    explicit_key: str,
    env_key: str,
    relative_path: str,
    tool_label: str,
) -> tuple[Path | None, list[str]]:
    attempted: list[str] = []

    explicit = _existing_path(args.get(explicit_key))
    if explicit:
        return explicit, attempted
    if args.get(explicit_key):
        attempted.append(str(args[explicit_key]))

    env_path = _existing_path(os.environ.get(env_key))
    if env_path:
        return env_path, attempted
    if os.environ.get(env_key):
        attempted.append(os.environ[env_key])

    for root_value in (args.get("engineRoot"), os.environ.get("UE_ROOT")):
        if root_value:
            candidate = _path_from_engine_root(root_value, relative_path)
            if candidate.exists():
                return candidate, attempted
            attempted.append(str(candidate))

    engine_association = _read_engine_association(project_file)
    registry_root = _engine_root_from_registry(engine_association)
    if registry_root:
        candidate = _path_from_engine_root(registry_root, relative_path)
        if candidate.exists():
            return candidate, attempted
        attempted.append(str(candidate))

    for root in _common_engine_roots(engine_association):
        candidate = _path_from_engine_root(root, relative_path)
        if candidate.exists():
            return candidate, attempted
        attempted.append(str(candidate))

    attempted_text = "; ".join(dict.fromkeys(attempted)) or "no candidate paths found"
    return None, [
        (
            f"{tool_label} could not be resolved. Pass {explicit_key}, set {env_key}, "
            f"or set UE_ROOT. Tried: {attempted_text}"
        )
    ]


def _powershell_executable() -> str:
    return os.environ.get(
        "POWERSHELL_EXE",
        r"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe",
    )


def _list_unreal_editor_processes() -> list[dict[str, Any]]:
    if sys.platform == "win32":
        script = (
            "Get-CimInstance Win32_Process "
            "-Filter \"Name = 'UnrealEditor.exe' OR Name = 'UnrealEditor-Cmd.exe'\" | "
            "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        )
        completed = subprocess.run(
            [_powershell_executable(), "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (completed.stdout or "").strip()
        if not output:
            return []
        try:
            loaded = json.loads(output)
        except json.JSONDecodeError as exc:
            raise EditorProcessDetectionError(f"Could not parse PowerShell process output: {exc}") from exc
        if isinstance(loaded, dict):
            loaded = [loaded]
        if not isinstance(loaded, list):
            raise EditorProcessDetectionError("PowerShell process output must be a JSON object or array")
        return [
            {
                "pid": int(item.get("ProcessId") or 0),
                "name": item.get("Name") or "",
                "command_line": item.get("CommandLine") or "",
            }
            for item in loaded
            if isinstance(item, dict)
        ]

    completed = subprocess.run(
        ["ps", "-eo", "pid=,comm=,args="],
        capture_output=True,
        text=True,
        check=False,
    )
    processes: list[dict[str, Any]] = []
    for line in (completed.stdout or "").splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 2:
            continue
        pid, name = parts[0], parts[1]
        command_line = parts[2] if len(parts) > 2 else name
        if "UnrealEditor" in name or "UnrealEditor" in command_line:
            processes.append({"pid": int(pid), "name": name, "command_line": command_line})
    return processes


def _process_matches_project(process: dict[str, Any], uproject_path: Path) -> bool:
    command_line = str(process.get("command_line") or "").lower()
    normalized_project = str(uproject_path).lower()
    return normalized_project in command_line or uproject_path.name.lower() in command_line


def _matching_editor_processes(uproject_path: Path) -> list[dict[str, Any]]:
    return [
        process
        for process in _list_unreal_editor_processes()
        if _process_matches_project(process, uproject_path)
    ]


def _terminate_process(pid: int, *, force: bool) -> None:
    if sys.platform == "win32":
        if force:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True, check=False)
            return
        script = (
            f"$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
            "if ($p) { [void]$p.CloseMainWindow() }"
        )
        subprocess.run(
            [_powershell_executable(), "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        return

    signal_arg = "-KILL" if force else "-TERM"
    subprocess.run(["kill", signal_arg, str(pid)], capture_output=True, text=True, check=False)


def _parse_compile_errors(output: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for line in output.splitlines():
        stripped = line.strip()
        for pattern in COMPILE_ERROR_PATTERNS:
            match = pattern.match(stripped)
            if not match:
                continue
            item = match.groupdict()
            item["line"] = int(item["line"])
            if item.get("column"):
                item["column"] = int(item["column"])
            diagnostics.append(item)
            break
    return diagnostics


def _normalize_subprocess_output(output: str | bytes | None) -> str:
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output or ""


def _editor_process_detection_failed(exc: EditorProcessDetectionError) -> dict[str, Any]:
    return {
        "ok": False,
        "errors": [
            {
                "code": "editor_process_detection_failed",
                "message": str(exc),
            }
        ],
    }


def unreal_editor_status(args: dict[str, Any]) -> dict[str, Any]:
    project_root = _project_root(args.get("projectPath"), args.get("workspaceRoot"))
    uproject_path = _project_file(project_root)
    try:
        processes = _matching_editor_processes(uproject_path)
    except EditorProcessDetectionError as exc:
        return _editor_process_detection_failed(exc)
    return {
        "ok": True,
        "running": bool(processes),
        "project": str(uproject_path),
        "processes": processes,
    }


def unreal_close_editor(args: dict[str, Any]) -> dict[str, Any]:
    if args.get("userApproved") is not True:
        return _permission_required("close Unreal Editor")

    project_root = _project_root(args.get("projectPath"), args.get("workspaceRoot"))
    uproject_path = _project_file(project_root)
    force = bool(args.get("force", False))
    timeout_seconds = float(args.get("timeoutSeconds") or DEFAULT_EDITOR_CLOSE_TIMEOUT_SECONDS)
    try:
        initial_processes = _matching_editor_processes(uproject_path)
    except EditorProcessDetectionError as exc:
        return _editor_process_detection_failed(exc)

    for process in initial_processes:
        _terminate_process(int(process["pid"]), force=force)

    deadline = time.monotonic() + max(timeout_seconds, 0)
    try:
        remaining = _matching_editor_processes(uproject_path)
        while remaining and time.monotonic() < deadline:
            time.sleep(0.5)
            remaining = _matching_editor_processes(uproject_path)
    except EditorProcessDetectionError as exc:
        return _editor_process_detection_failed(exc)

    if remaining:
        return {
            "ok": False,
            "closed": False,
            "blocked": True,
            "project": str(uproject_path),
            "initial_processes": initial_processes,
            "remaining_processes": remaining,
            "errors": [
                {
                    "code": "editor_still_running",
                    "message": "Unreal Editor is still running. Ask for separate approval before forcing it closed.",
                }
            ],
        }

    return {
        "ok": True,
        "closed": bool(initial_processes),
        "project": str(uproject_path),
        "initial_processes": initial_processes,
        "remaining_processes": [],
    }


def unreal_build_editor(args: dict[str, Any]) -> dict[str, Any]:
    if args.get("userApproved") is not True:
        return _permission_required("rebuild the Unreal editor target")

    project_root = _project_root(args.get("projectPath"), args.get("workspaceRoot"))
    uproject_path = _project_file(project_root)
    build_bat, errors = _resolve_engine_tool(
        args,
        uproject_path,
        explicit_key="buildBatPath",
        env_key="UNREAL_BUILD_BAT",
        relative_path=r"Build\BatchFiles\Build.bat",
        tool_label="Build.bat",
    )
    if build_bat is None:
        return {"ok": False, "errors": [{"code": "build_bat_not_found", "message": message} for message in errors]}

    target = str(args.get("target") or f"{uproject_path.stem}Editor")
    platform = str(args.get("platform") or "Win64")
    configuration = str(args.get("configuration") or "Development")
    timeout_seconds = float(args.get("timeoutSeconds") or DEFAULT_BUILD_TIMEOUT_SECONDS)
    command = [
        str(build_bat),
        target,
        platform,
        configuration,
        f"-Project={uproject_path}",
        "-WaitMutex",
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _normalize_subprocess_output(exc.stdout)
        stderr = _normalize_subprocess_output(exc.stderr)
        return {
            "ok": False,
            "exit_code": None,
            "command": command,
            "project": str(uproject_path),
            "compile_errors": _parse_compile_errors(stdout + "\n" + stderr),
            "errors": [
                {
                    "code": "build_timeout",
                    "message": f"Build timed out after {timeout_seconds}s",
                }
            ],
        }

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    diagnostics = _parse_compile_errors(stdout + "\n" + stderr)
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "command": command,
        "project": str(uproject_path),
        "compile_errors": diagnostics,
    }


def unreal_launch_editor(args: dict[str, Any]) -> dict[str, Any]:
    if args.get("userApproved") is not True:
        return _permission_required("launch Unreal Editor")

    project_root = _project_root(args.get("projectPath"), args.get("workspaceRoot"))
    uproject_path = _project_file(project_root)
    editor_exe, errors = _resolve_engine_tool(
        args,
        uproject_path,
        explicit_key="editorExe",
        env_key="UNREAL_EDITOR_EXE",
        relative_path=r"Binaries\Win64\UnrealEditor.exe",
        tool_label="UnrealEditor.exe",
    )
    if editor_exe is None:
        return {"ok": False, "errors": [{"code": "editor_exe_not_found", "message": message} for message in errors]}

    extra_args = args.get("extraArgs") or []
    if not isinstance(extra_args, list):
        return {
            "ok": False,
            "errors": [
                {
                    "code": "invalid_extra_args",
                    "message": "extraArgs must be an array of strings.",
                }
            ],
        }
    command = [str(editor_exe), str(uproject_path), *[str(value) for value in extra_args]]
    popen_kwargs: dict[str, Any] = {
        "cwd": str(project_root),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    _start_process_waiter(process)
    result: dict[str, Any] = {
        "ok": True,
        "launched": True,
        "pid": process.pid,
        "command": command,
        "project": str(uproject_path),
    }

    if args.get("waitForBridge", False):
        bridge_ready_timeout = int(args.get("bridgeReadyTimeoutSeconds", 300))
        bridge_base = str(args.get("bridgeUrl") or DEFAULT_BRIDGE_URL).rstrip("/")
        health_url = f"{bridge_base}/accelbyte-ui-tools/health"
        deadline = time.monotonic() + bridge_ready_timeout
        bridge_ok = False
        while time.monotonic() < deadline:
            time.sleep(3)
            if _check_bridge_health(health_url):
                bridge_ok = True
                break
        result["bridge_ready"] = bridge_ok
        if not bridge_ok:
            result["bridge_warning"] = (
                f"Bridge did not become ready within {bridge_ready_timeout}s"
            )

    return result


def _check_bridge_health(health_url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(health_url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data.get("ok"))
    except Exception:
        return False


def _start_process_waiter(process: subprocess.Popen[Any]) -> None:
    threading.Thread(target=process.wait, daemon=True).start()
