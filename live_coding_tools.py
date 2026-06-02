from __future__ import annotations

import asyncio
import os
from pathlib import Path
import re
import time
from typing import Any

import httpx

from _unreal_common import DEFAULT_BRIDGE_URL, bridge_url as _bridge_url

LIVE_CODING_ROUTE = "/unreal/live-coding/compile"
DEFAULT_TIMEOUT_SECONDS = 120
MAX_HTTP_TIMEOUT_SECONDS = 105
DEFAULT_LOG_TAIL_LINES = 160
DEFAULT_POLL_INTERVAL_SECONDS = 0.5


def _monotonic() -> float:
    return time.monotonic()


def _timeout_seconds(args: dict[str, Any]) -> float:
    value = args.get("timeoutSeconds", DEFAULT_TIMEOUT_SECONDS)
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeoutSeconds must be a number") from exc
    if timeout <= 0:
        raise ValueError("timeoutSeconds must be greater than 0")
    return timeout


def _unreal_build_tool_log_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "UnrealBuildTool" / "Log.txt"
    return Path.home() / "AppData" / "Local" / "UnrealBuildTool" / "Log.txt"


def _snapshot_unreal_build_tool_log() -> tuple[bool, str | None]:
    log_path = _unreal_build_tool_log_path()
    try:
        return log_path.exists(), log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return log_path.exists(), None


def _is_useful_build_diagnostic_line(line: str) -> bool:
    lowered = line.lower()
    return (
        " error " in lowered
        or ": error" in lowered
        or "fatal error" in lowered
        or "compilationresultexception" in lowered
        or "result: failed" in lowered
        or "result: succeeded" in lowered
        or "livecoding" in lowered
        or "exceeds the number of allowed actions" in lowered
        or ".cpp(" in lowered
        or ".h(" in lowered
    )


def _read_appended_unreal_build_tool_log(
    initial_snapshot: tuple[bool, str | None],
    max_recent_lines: int = DEFAULT_LOG_TAIL_LINES,
) -> dict[str, Any]:
    log_path = _unreal_build_tool_log_path()
    report: dict[str, Any] = {"diagnostic_log_path": str(log_path)}
    try:
        current_log = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        report["diagnostic_message"] = f"UnrealBuildTool log could not be read: {exc}"
        return report

    log_existed, initial_log = initial_snapshot
    if initial_log is None and not log_existed:
        appended_log = current_log
    elif initial_log is None:
        report["diagnostic_message"] = (
            "UnrealBuildTool log existed but could not be snapshotted before compilation; "
            "new output could not be isolated safely."
        )
        return report
    elif current_log.startswith(initial_log):
        appended_log = current_log[len(initial_log) :]
    else:
        report["diagnostic_message"] = (
            "UnrealBuildTool log was replaced or truncated during compilation; "
            "new output could not be isolated safely."
        )
        return report

    appended_lines = appended_log.splitlines()
    recent_lines = appended_lines[-max_recent_lines:]
    report["diagnostic_summary"] = [
        line for line in recent_lines if _is_useful_build_diagnostic_line(line)
    ][:40]
    report["recent_diagnostic_log"] = recent_lines

    for line in reversed(recent_lines):
        result_match = re.search(r"Result:\s*(Succeeded|Failed)(?:\s*\(([^)]+)\))?", line)
        if not result_match:
            continue

        result = result_match.group(1).lower()
        detail = result_match.group(2)
        report["ubt_result"] = result
        if detail:
            report["ubt_result_detail"] = detail
        report["ok"] = result == "succeeded"
        report["status"] = "success" if result == "succeeded" else "failure"
        report["result_source"] = "unreal_build_tool_log"
        break

    return report


def _with_timeout_context(
    report: dict[str, Any],
    *,
    requested_timeout_seconds: float,
    http_timeout_seconds: float,
) -> dict[str, Any]:
    return {
        **report,
        "bridge_timed_out": True,
        "requested_timeout_seconds": requested_timeout_seconds,
        "http_timeout_seconds": http_timeout_seconds,
    }


async def unreal_live_coding_compile(args: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = _timeout_seconds(args)
    http_timeout_seconds = min(timeout_seconds, MAX_HTTP_TIMEOUT_SECONDS)
    initial_log = _snapshot_unreal_build_tool_log()
    started_at = _monotonic()
    payload = {
        "waitForCompletion": bool(args.get("waitForCompletion", True)),
    }

    try:
        async with httpx.AsyncClient(timeout=http_timeout_seconds) as client:
            response = await client.post(f"{_bridge_url(args)}{LIVE_CODING_ROUTE}", json=payload)
            response.raise_for_status()
            loaded = response.json()
            if not isinstance(loaded, dict):
                raise ValueError("Live Coding bridge response must be a JSON object")
            if loaded.get("status") == "failure" or loaded.get("ok") is False:
                return {**loaded, **_read_appended_unreal_build_tool_log(initial_log)}
            return loaded
    except httpx.TimeoutException:
        while True:
            log_report = _read_appended_unreal_build_tool_log(initial_log)
            if "ubt_result" in log_report:
                return _with_timeout_context(
                    {
                        **log_report,
                        "message": (
                            "Live Coding bridge did not return before the MCP transport-safe timeout, "
                            "but UnrealBuildTool wrote a final result."
                        ),
                    },
                    requested_timeout_seconds=timeout_seconds,
                    http_timeout_seconds=http_timeout_seconds,
                )

            if _monotonic() - started_at >= timeout_seconds:
                return _with_timeout_context(
                    {
                        "ok": False,
                        "status": "timed_out_but_compile_may_still_be_running",
                        "message": (
                            "Live Coding bridge did not return before the total attempt timeout, "
                            "and UnrealBuildTool has not written a new final result yet."
                        ),
                        **log_report,
                    },
                    requested_timeout_seconds=timeout_seconds,
                    http_timeout_seconds=http_timeout_seconds,
                )

            await asyncio.sleep(DEFAULT_POLL_INTERVAL_SECONDS)
