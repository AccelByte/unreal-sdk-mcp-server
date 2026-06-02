import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def unreal_project_tools():
    module_name = "unreal_project_tools_under_test"
    module_path = SERVER_ROOT / "unreal_project_tools.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_project(root: Path, name: str = "SampleGame") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    uproject = root / f"{name}.uproject"
    uproject.write_text('{"FileVersion": 3, "EngineAssociation": "5.7"}', encoding="utf-8")
    return uproject


def test_restricted_tools_require_user_approval(tmp_path, unreal_project_tools):
    _make_project(tmp_path)

    for handler in (
        unreal_project_tools.unreal_close_editor,
        unreal_project_tools.unreal_build_editor,
        unreal_project_tools.unreal_launch_editor,
    ):
        result = handler({"projectPath": str(tmp_path)})

        assert result["ok"] is False
        assert result["errors"][0]["code"] == "permission_required"


def test_editor_status_filters_processes_by_uproject(tmp_path, monkeypatch, unreal_project_tools):
    uproject = _make_project(tmp_path)
    monkeypatch.setattr(
        unreal_project_tools,
        "_list_unreal_editor_processes",
        lambda: [
            {
                "pid": 10,
                "name": "UnrealEditor.exe",
                "command_line": f'UnrealEditor.exe "{uproject}"',
            },
            {
                "pid": 11,
                "name": "UnrealEditor.exe",
                "command_line": "UnrealEditor.exe D:/Other/Other.uproject",
            },
        ],
    )

    result = unreal_project_tools.unreal_editor_status({"projectPath": str(tmp_path)})

    assert result["ok"] is True
    assert result["running"] is True
    assert [process["pid"] for process in result["processes"]] == [10]


@pytest.mark.parametrize("output", ["security policy banner", '"unexpected string"'])
def test_editor_status_reports_invalid_powershell_process_output(
    tmp_path, monkeypatch, unreal_project_tools, output
):
    _make_project(tmp_path)
    monkeypatch.setattr(unreal_project_tools.sys, "platform", "win32")
    monkeypatch.setattr(
        unreal_project_tools.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(stdout=output, stderr=""),
    )

    result = unreal_project_tools.unreal_editor_status({"projectPath": str(tmp_path)})

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "editor_process_detection_failed"


def test_close_editor_does_not_terminate_when_process_detection_fails(
    tmp_path, monkeypatch, unreal_project_tools
):
    _make_project(tmp_path)

    def fail_detection(_uproject):
        raise unreal_project_tools.EditorProcessDetectionError("malformed process output")

    terminated = []
    monkeypatch.setattr(unreal_project_tools, "_matching_editor_processes", fail_detection)
    monkeypatch.setattr(
        unreal_project_tools,
        "_terminate_process",
        lambda pid, force: terminated.append((pid, force)),
    )

    result = unreal_project_tools.unreal_close_editor(
        {"projectPath": str(tmp_path), "userApproved": True}
    )

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "editor_process_detection_failed"
    assert terminated == []


def test_close_editor_graceful_block_reports_remaining_process(tmp_path, monkeypatch, unreal_project_tools):
    _make_project(tmp_path)
    process = {"pid": 42, "name": "UnrealEditor.exe", "command_line": "SampleGame.uproject"}
    terminated = []
    calls = {"count": 0}

    def fake_matching(_uproject):
        calls["count"] += 1
        return [process]

    monkeypatch.setattr(unreal_project_tools, "_matching_editor_processes", fake_matching)
    monkeypatch.setattr(
        unreal_project_tools,
        "_terminate_process",
        lambda pid, force: terminated.append((pid, force)),
    )

    result = unreal_project_tools.unreal_close_editor(
        {"projectPath": str(tmp_path), "userApproved": True, "timeoutSeconds": 0}
    )

    assert terminated == [(42, False)]
    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["errors"][0]["code"] == "editor_still_running"


def test_build_editor_uses_explicit_buildbat_and_parses_errors(
    tmp_path, monkeypatch, unreal_project_tools
):
    uproject = _make_project(tmp_path)
    build_bat = tmp_path / "Engine" / "Build" / "BatchFiles" / "Build.bat"
    build_bat.parent.mkdir(parents=True)
    build_bat.write_text("@echo off", encoding="utf-8")
    runs = []

    def fake_run(command, **kwargs):
        runs.append((command, kwargs))
        return SimpleNamespace(
            returncode=6,
            stdout=(
                f"{tmp_path}\\Source\\SampleGame\\AGS\\UI\\Generated\\Login\\LoginWidget.cpp"
                "(27): error C2065: 'MissingSymbol': undeclared identifier\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(unreal_project_tools.subprocess, "run", fake_run)

    result = unreal_project_tools.unreal_build_editor(
        {
            "projectPath": str(tmp_path),
            "userApproved": True,
            "buildBatPath": str(build_bat),
        }
    )

    assert result["ok"] is False
    assert result["exit_code"] == 6
    assert runs[0][0] == [
        str(build_bat),
        "SampleGameEditor",
        "Win64",
        "Development",
        f"-Project={uproject}",
        "-WaitMutex",
    ]
    assert result["compile_errors"][0]["code"] == "C2065"
    assert result["compile_errors"][0]["line"] == 27
    assert "stdout" not in result
    assert "stderr" not in result


def test_build_editor_resolves_buildbat_from_environment(
    tmp_path, monkeypatch, unreal_project_tools
):
    _make_project(tmp_path)
    build_bat = tmp_path / "Build.bat"
    build_bat.write_text("@echo off", encoding="utf-8")
    monkeypatch.setenv("UNREAL_BUILD_BAT", str(build_bat))
    monkeypatch.setattr(
        unreal_project_tools.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    result = unreal_project_tools.unreal_build_editor(
        {"projectPath": str(tmp_path), "userApproved": True}
    )

    assert result["ok"] is True
    assert result["command"][0] == str(build_bat)
    assert "stdout" not in result
    assert "stderr" not in result


def test_build_editor_timeout_returns_partial_diagnostics(
    tmp_path, monkeypatch, unreal_project_tools
):
    _make_project(tmp_path)
    build_bat = tmp_path / "Build.bat"
    build_bat.write_text("@echo off", encoding="utf-8")

    def fake_run(command, **kwargs):
        raise unreal_project_tools.subprocess.TimeoutExpired(
            command,
            kwargs["timeout"],
            output=(
                f"{tmp_path}\\Source\\SampleGame\\LoginWidget.cpp"
                "(27): error C2065: 'MissingSymbol': undeclared identifier\n"
            ).encode(),
            stderr=b"Build still running",
        )

    monkeypatch.setattr(unreal_project_tools.subprocess, "run", fake_run)

    result = unreal_project_tools.unreal_build_editor(
        {
            "projectPath": str(tmp_path),
            "userApproved": True,
            "buildBatPath": str(build_bat),
            "timeoutSeconds": 15,
        }
    )

    assert result["ok"] is False
    assert result["exit_code"] is None
    assert "stdout" not in result
    assert "stderr" not in result
    assert result["compile_errors"][0]["code"] == "C2065"
    assert result["errors"] == [{"code": "build_timeout", "message": "Build timed out after 15.0s"}]


def test_launch_editor_uses_explicit_editor_exe(tmp_path, monkeypatch, unreal_project_tools):
    uproject = _make_project(tmp_path)
    editor_exe = tmp_path / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    editor_exe.parent.mkdir(parents=True)
    editor_exe.write_text("", encoding="utf-8")
    popen_calls = []

    class FakeProcess:
        pid = 1234

        def wait(self):
            return 0

    def fake_popen(command, **kwargs):
        popen_calls.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr(unreal_project_tools.subprocess, "Popen", fake_popen)

    result = unreal_project_tools.unreal_launch_editor(
        {
            "projectPath": str(tmp_path),
            "userApproved": True,
            "editorExe": str(editor_exe),
            "extraArgs": ["-log"],
        }
    )

    assert result["ok"] is True
    assert result["pid"] == 1234
    assert popen_calls[0][0] == [str(editor_exe), str(uproject), "-log"]
    assert popen_calls[0][1]["stdin"] is unreal_project_tools.subprocess.DEVNULL
    assert popen_calls[0][1]["stdout"] is unreal_project_tools.subprocess.DEVNULL
    assert popen_calls[0][1]["stderr"] is unreal_project_tools.subprocess.DEVNULL
    assert popen_calls[0][1]["creationflags"] == (
        unreal_project_tools.subprocess.DETACHED_PROCESS
        | unreal_project_tools.subprocess.CREATE_NEW_PROCESS_GROUP
    )


def test_launch_editor_resolves_editor_from_engine_root(tmp_path, monkeypatch, unreal_project_tools):
    _make_project(tmp_path)
    editor_exe = tmp_path / "UE_5.7" / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    editor_exe.parent.mkdir(parents=True)
    editor_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        unreal_project_tools.subprocess,
        "Popen",
        lambda command, **kwargs: SimpleNamespace(pid=77, wait=lambda: 0),
    )

    result = unreal_project_tools.unreal_launch_editor(
        {
            "projectPath": str(tmp_path),
            "userApproved": True,
            "engineRoot": str(tmp_path / "UE_5.7"),
        }
    )

    assert result["ok"] is True
    assert result["command"][0] == str(editor_exe)


def test_launch_editor_uses_posix_session_detach(tmp_path, monkeypatch, unreal_project_tools):
    _make_project(tmp_path)
    editor_exe = tmp_path / "UnrealEditor"
    editor_exe.write_text("", encoding="utf-8")
    popen_calls = []

    def fake_popen(command, **kwargs):
        popen_calls.append((command, kwargs))
        return SimpleNamespace(pid=88, wait=lambda: 0)

    monkeypatch.setattr(unreal_project_tools.sys, "platform", "linux")
    monkeypatch.setattr(unreal_project_tools.subprocess, "Popen", fake_popen)

    result = unreal_project_tools.unreal_launch_editor(
        {
            "projectPath": str(tmp_path),
            "userApproved": True,
            "editorExe": str(editor_exe),
        }
    )

    assert result["ok"] is True
    assert popen_calls[0][1]["start_new_session"] is True
    assert "creationflags" not in popen_calls[0][1]


def test_start_process_waiter_starts_daemon_thread(monkeypatch, unreal_project_tools):
    started = []
    process = SimpleNamespace(wait=lambda: None)

    class FakeThread:
        def __init__(self, *, target, daemon):
            assert target == process.wait
            assert daemon is True

        def start(self):
            started.append(True)

    monkeypatch.setattr(unreal_project_tools.threading, "Thread", FakeThread)

    unreal_project_tools._start_process_waiter(process)

    assert started == [True]
