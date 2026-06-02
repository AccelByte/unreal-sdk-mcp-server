import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("POST", "http://127.0.0.1"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self.payload


@pytest.fixture
def live_coding_tools():
    module_name = "live_coding_tools_under_test"
    module_path = SERVER_ROOT / "live_coding_tools.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unreal_live_coding_compile_posts_to_default_bridge(monkeypatch, live_coding_tools):
    post_mock = AsyncMock(return_value=FakeResponse({"ok": True, "status": "success"}))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(live_coding_tools.unreal_live_coding_compile({}))

    assert result == {"ok": True, "status": "success"}
    post_mock.assert_awaited_once()
    assert post_mock.await_args.args[0] == (
        "http://127.0.0.1:48757/unreal/live-coding/compile"
    )
    assert post_mock.await_args.kwargs["json"] == {"waitForCompletion": True}


def test_unreal_live_coding_compile_uses_custom_bridge_and_timeout(monkeypatch, live_coding_tools):
    timeout_values = []

    def client_factory(timeout):
        timeout_values.append(timeout)
        client_mock = AsyncMock()
        client_mock.__aenter__.return_value.post = AsyncMock(
            return_value=FakeResponse({"ok": True, "status": "no_changes"})
        )
        client_mock.__aexit__.return_value = None
        return client_mock

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    result = asyncio.run(
        live_coding_tools.unreal_live_coding_compile(
            {
                "bridgeUrl": "http://127.0.0.1:9999/",
                "waitForCompletion": False,
                "timeoutSeconds": 7,
            }
        )
    )

    assert result == {"ok": True, "status": "no_changes"}
    assert timeout_values == [7.0]


def test_unreal_live_coding_compile_rejects_non_object_response(monkeypatch, live_coding_tools):
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = AsyncMock(return_value=FakeResponse(["ok"]))
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    with pytest.raises(ValueError, match="JSON object"):
        asyncio.run(live_coding_tools.unreal_live_coding_compile({}))


def test_unreal_live_coding_compile_propagates_http_errors(monkeypatch, live_coding_tools):
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = AsyncMock(return_value=FakeResponse({}, 500))
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(live_coding_tools.unreal_live_coding_compile({}))


def test_unreal_live_coding_compile_adds_appended_diagnostics_on_failure(
    monkeypatch, tmp_path, live_coding_tools
):
    log_path = tmp_path / "Log.txt"
    log_path.write_text("old output\n", encoding="utf-8")

    async def post(*_args, **_kwargs):
        with log_path.open("a", encoding="utf-8") as log:
            log.write("Widget.cpp(12): error C2065: broken\nResult: Failed (CompileFailed)\n")
        return FakeResponse({"ok": False, "status": "failure"})

    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)
    monkeypatch.setattr(live_coding_tools, "_unreal_build_tool_log_path", lambda: log_path)

    result = asyncio.run(live_coding_tools.unreal_live_coding_compile({}))

    assert result["ok"] is False
    assert result["status"] == "failure"
    assert result["ubt_result"] == "failed"
    assert result["ubt_result_detail"] == "CompileFailed"
    assert result["result_source"] == "unreal_build_tool_log"
    assert result["recent_diagnostic_log"] == [
        "Widget.cpp(12): error C2065: broken",
        "Result: Failed (CompileFailed)",
    ]


@pytest.mark.parametrize(
    ("result_line", "expected_ok", "expected_status"),
    [
        ("Result: Succeeded\n", True, "success"),
        ("Result: Failed (CompileFailed)\n", False, "failure"),
    ],
)
def test_unreal_live_coding_compile_recovers_appended_result_after_http_timeout(
    monkeypatch,
    tmp_path,
    live_coding_tools,
    result_line,
    expected_ok,
    expected_status,
):
    log_path = tmp_path / "Log.txt"
    log_path.write_text("old output\n", encoding="utf-8")

    async def post(*_args, **_kwargs):
        with log_path.open("a", encoding="utf-8") as log:
            log.write(result_line)
        raise httpx.TimeoutException("bridge timed out")

    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)
    monkeypatch.setattr(live_coding_tools, "_unreal_build_tool_log_path", lambda: log_path)

    result = asyncio.run(
        live_coding_tools.unreal_live_coding_compile({"timeoutSeconds": 120})
    )

    assert result["ok"] is expected_ok
    assert result["status"] == expected_status
    assert result["bridge_timed_out"] is True
    assert result["result_source"] == "unreal_build_tool_log"
    assert result["requested_timeout_seconds"] == 120.0
    assert result["http_timeout_seconds"] == 105


def test_unreal_live_coding_compile_ignores_stale_preexisting_result(
    monkeypatch, tmp_path, live_coding_tools
):
    log_path = tmp_path / "Log.txt"
    log_path.write_text("Result: Succeeded\n", encoding="utf-8")
    monotonic_values = iter([0.0, 2.0])

    async def post(*_args, **_kwargs):
        raise httpx.TimeoutException("bridge timed out")

    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)
    monkeypatch.setattr(live_coding_tools, "_unreal_build_tool_log_path", lambda: log_path)
    monkeypatch.setattr(live_coding_tools, "_monotonic", lambda: next(monotonic_values))

    result = asyncio.run(
        live_coding_tools.unreal_live_coding_compile({"timeoutSeconds": 1})
    )

    assert result["ok"] is False
    assert result["status"] == "timed_out_but_compile_may_still_be_running"
    assert "ubt_result" not in result


def test_unreal_live_coding_compile_reports_timeout_without_new_final_result(
    monkeypatch, tmp_path, live_coding_tools
):
    log_path = tmp_path / "Log.txt"
    log_path.write_text("old output\n", encoding="utf-8")
    monotonic_values = iter([0.0, 2.0])

    async def post(*_args, **_kwargs):
        with log_path.open("a", encoding="utf-8") as log:
            log.write("LiveCoding compile still active\n")
        raise httpx.TimeoutException("bridge timed out")

    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)
    monkeypatch.setattr(live_coding_tools, "_unreal_build_tool_log_path", lambda: log_path)
    monkeypatch.setattr(live_coding_tools, "_monotonic", lambda: next(monotonic_values))

    result = asyncio.run(
        live_coding_tools.unreal_live_coding_compile({"timeoutSeconds": 1})
    )

    assert result["ok"] is False
    assert result["status"] == "timed_out_but_compile_may_still_be_running"
    assert result["recent_diagnostic_log"] == ["LiveCoding compile still active"]
