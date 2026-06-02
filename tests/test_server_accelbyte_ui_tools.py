import asyncio
import importlib.util
import json
from pathlib import Path
import re
import sys


SERVER_ROOT = Path(__file__).resolve().parents[1]


def _load_server_module():
    module_name = "unreal_sdk_mcp_server_under_test"
    module_path = SERVER_ROOT / "server.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    sys.path.insert(0, str(SERVER_ROOT))
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SERVER_ROOT))
        if previous_module is None:
            if sys.modules.get(module_name) is module:
                del sys.modules[module_name]
        else:
            sys.modules[module_name] = previous_module


def test_list_tools_includes_accelbyte_ui_tools():
    server_module = _load_server_module()

    tools = asyncio.run(server_module.list_tools())
    tool_names = {tool.name for tool in tools}

    assert {
        "accelbyte_ui_bridge_health",
        "accelbyte_ui_validate",
        "accelbyte_ui_generate",
        "accelbyte_ui_resolve",
        "accelbyte_ui_verify_backing_class",
        "accelbyte_ui_patch",
        "select_ags_recipe",
    }.issubset(tool_names)


def test_list_tools_includes_live_coding_compile_tool():
    server_module = _load_server_module()

    tools = asyncio.run(server_module.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "unreal_live_coding_compile" in tool_names
    assert {
        "unreal_editor_status",
        "unreal_close_editor",
        "unreal_build_editor",
        "unreal_launch_editor",
    }.issubset(tool_names)


def test_unreal_lifecycle_tool_schemas_require_approval_for_actions():
    server_module = _load_server_module()

    tools = asyncio.run(server_module.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert by_name["unreal_editor_status"].inputSchema["required"] == ["projectPath"]
    for tool_name in ("unreal_close_editor", "unreal_build_editor", "unreal_launch_editor"):
        assert "userApproved" in by_name[tool_name].inputSchema["required"]
        assert by_name[tool_name].inputSchema["properties"]["userApproved"]["type"] == "boolean"


def test_verify_backing_class_schema_exposes_auto_approve_style():
    server_module = _load_server_module()

    tools = asyncio.run(server_module.list_tools())
    verify_tool = next(tool for tool in tools if tool.name == "accelbyte_ui_verify_backing_class")

    assert verify_tool.inputSchema["properties"]["autoApproveStyle"]["default"] is True
    assert "final generated C++ parent class" in verify_tool.description


def test_generate_schema_exposes_verify_only_mode():
    server_module = _load_server_module()

    tools = asyncio.run(server_module.list_tools())
    generate_tool = next(tool for tool in tools if tool.name == "accelbyte_ui_generate")

    mode_schema = generate_tool.inputSchema["properties"]["mode"]
    assert "verify-only" in mode_schema["enum"]
    assert "without creating assets" in mode_schema["description"]


def test_resolve_schema_exposes_preflight_tool():
    server_module = _load_server_module()

    tools = asyncio.run(server_module.list_tools())
    resolve_tool = next(tool for tool in tools if tool.name == "accelbyte_ui_resolve")

    assert resolve_tool.inputSchema["required"] == ["projectPath", "specPath"]
    assert resolve_tool.inputSchema["properties"]["auto_approve_style"]["default"] is True
    assert "without creating assets" in resolve_tool.description
    assert "before writing script-backed C++ headers" in resolve_tool.description


def test_patch_schema_documents_set_widget_properties_operation():
    server_module = _load_server_module()

    tools = asyncio.run(server_module.list_tools())
    patch_tool = next(tool for tool in tools if tool.name == "accelbyte_ui_patch")

    assert "set_widget_properties" in patch_tool.description
    assert "widget_name" in patch_tool.inputSchema["properties"]["patchPath"]["description"]


def test_call_tool_dispatches_accelbyte_ui_async_handler(monkeypatch):
    server_module = _load_server_module()
    calls = []

    async def fake_generate(arguments):
        calls.append(arguments)
        return {"ok": True, "source": "fake-handler"}

    monkeypatch.setattr(server_module, "accelbyte_ui_generate", fake_generate)

    response = asyncio.run(
        server_module.call_tool(
            "accelbyte_ui_generate",
            {"projectPath": "D:/Project", "specPath": "Content/UI/spec.json"},
        )
    )

    assert calls == [{"projectPath": "D:/Project", "specPath": "Content/UI/spec.json"}]
    assert len(response) == 1
    assert json.loads(response[0].text) == {"ok": True, "source": "fake-handler"}


def test_call_tool_dispatches_accelbyte_ui_resolve_handler(monkeypatch):
    server_module = _load_server_module()
    calls = []

    async def fake_resolve(arguments):
        calls.append(arguments)
        return {"ok": True, "source": "resolve-handler"}

    monkeypatch.setattr(server_module, "accelbyte_ui_resolve", fake_resolve)

    response = asyncio.run(
        server_module.call_tool(
            "accelbyte_ui_resolve",
            {"projectPath": "D:/Project", "specPath": "Content/UI/spec.json"},
        )
    )

    assert calls == [{"projectPath": "D:/Project", "specPath": "Content/UI/spec.json"}]
    assert len(response) == 1
    assert json.loads(response[0].text) == {"ok": True, "source": "resolve-handler"}


def test_select_ags_recipe_reports_missing_loader_as_clean_error(monkeypatch):
    server_module = _load_server_module()
    selector_path = server_module._TOOLS_DIR / "ags_recipe_selector.py"
    monkeypatch.setattr(server_module.importlib.util, "spec_from_file_location", lambda *_args: None)

    response = asyncio.run(server_module.call_tool("select_ags_recipe", {"request": "login"}))

    assert json.loads(response[0].text) == {
        "error": f"Could not load ags_recipe_selector from {selector_path}"
    }


def test_call_tool_dispatches_select_ags_recipe_handler(monkeypatch):
    server_module = _load_server_module()
    calls = []

    def fake_select(arguments):
        calls.append(arguments)
        return {"layout": "fake-layout"}

    monkeypatch.setattr(server_module, "_handle_select_ags_recipe", fake_select)

    response = asyncio.run(server_module.call_tool("select_ags_recipe", {"request": "login"}))

    assert calls == [{"request": "login"}]
    assert json.loads(response[0].text) == {"layout": "fake-layout"}


def test_select_ags_recipe_returns_known_login_recipe():
    server_module = _load_server_module()

    result = server_module._handle_select_ags_recipe({"request": "login"})

    assert result["layout"] == "AGS_CenteredPanel"
    assert result["reason"] == "auth"
    assert result["recipe_name"] == "ags_login_panel.json"
    assert result["recipe_spec"]["asset_path"] == "/Game/AGS/UI/Generated/WBP_AGS_LoginPanel"


def test_select_ags_recipe_does_not_leak_runtime_module():
    server_module = _load_server_module()
    sys.modules.pop("ags_recipe_selector", None)

    result = server_module._handle_select_ags_recipe({"request": "login"})

    assert result["layout"]
    assert "ags_recipe_selector" not in sys.modules


def test_select_ags_recipe_restores_existing_runtime_module():
    server_module = _load_server_module()
    previous_module = object()
    sys.modules["ags_recipe_selector"] = previous_module
    try:
        server_module._handle_select_ags_recipe({"request": "login"})

        assert sys.modules["ags_recipe_selector"] is previous_module
    finally:
        if sys.modules.get("ags_recipe_selector") is previous_module:
            del sys.modules["ags_recipe_selector"]


def test_call_tool_dispatches_live_coding_compile_handler(monkeypatch):
    server_module = _load_server_module()
    calls = []

    async def fake_compile(arguments):
        calls.append(arguments)
        return {"ok": True, "source": "live-coding-handler"}

    monkeypatch.setattr(server_module, "unreal_live_coding_compile", fake_compile)

    response = asyncio.run(
        server_module.call_tool(
            "unreal_live_coding_compile",
            {"bridgeUrl": "http://127.0.0.1:9999", "waitForCompletion": False},
        )
    )

    assert calls == [{"bridgeUrl": "http://127.0.0.1:9999", "waitForCompletion": False}]
    assert len(response) == 1
    assert json.loads(response[0].text) == {"ok": True, "source": "live-coding-handler"}


def test_call_tool_dispatches_unreal_lifecycle_handlers(monkeypatch):
    server_module = _load_server_module()
    calls = []
    thread_calls = []

    async def fake_to_thread(handler, arguments):
        thread_calls.append((handler, arguments))
        return handler(arguments)

    def fake_status(arguments):
        calls.append(("status", arguments))
        return {"ok": True, "source": "status-handler"}

    def fake_close(arguments):
        calls.append(("close", arguments))
        return {"ok": True, "source": "close-handler"}

    def fake_build(arguments):
        calls.append(("build", arguments))
        return {"ok": True, "source": "build-handler"}

    def fake_launch(arguments):
        calls.append(("launch", arguments))
        return {"ok": True, "source": "launch-handler"}

    monkeypatch.setattr(server_module, "unreal_editor_status", fake_status)
    monkeypatch.setattr(server_module, "unreal_close_editor", fake_close)
    monkeypatch.setattr(server_module, "unreal_build_editor", fake_build)
    monkeypatch.setattr(server_module, "unreal_launch_editor", fake_launch)
    monkeypatch.setattr(server_module.asyncio, "to_thread", fake_to_thread)

    for tool_name in (
        "unreal_editor_status",
        "unreal_close_editor",
        "unreal_build_editor",
        "unreal_launch_editor",
    ):
        response = asyncio.run(
            server_module.call_tool(tool_name, {"projectPath": "D:/Project", "userApproved": True})
        )
        assert json.loads(response[0].text)["ok"] is True

    assert calls == [
        ("status", {"projectPath": "D:/Project", "userApproved": True}),
        ("close", {"projectPath": "D:/Project", "userApproved": True}),
        ("build", {"projectPath": "D:/Project", "userApproved": True}),
        ("launch", {"projectPath": "D:/Project", "userApproved": True}),
    ]
    assert thread_calls == [
        (fake_status, {"projectPath": "D:/Project", "userApproved": True}),
        (fake_close, {"projectPath": "D:/Project", "userApproved": True}),
        (fake_build, {"projectPath": "D:/Project", "userApproved": True}),
        (fake_launch, {"projectPath": "D:/Project", "userApproved": True}),
    ]


def test_sse_server_allows_loopback_ports_with_cors_regex(monkeypatch):
    server_module = _load_server_module()
    middleware_calls = []

    def fake_cors_middleware(app, **kwargs):
        middleware_calls.append((app, kwargs))
        return app

    class FakeUvicornServer:
        def __init__(self, config):
            self.config = config

        async def serve(self):
            return None

    monkeypatch.setattr(server_module, "CORSMiddleware", fake_cors_middleware)
    monkeypatch.setattr(server_module.uvicorn, "Server", FakeUvicornServer)

    asyncio.run(server_module._start_sse_server(3000))

    assert len(middleware_calls) == 1
    assert middleware_calls[0][1] == {
        "allow_origin_regex": r"http://(?:localhost|127\.0\.0\.1|\[::1\]):\d+",
        "allow_headers": ["Content-Type"],
        "expose_headers": ["Content-Type"],
    }
    origin_regex = re.compile(middleware_calls[0][1]["allow_origin_regex"])
    assert origin_regex.fullmatch("http://localhost:3000")
    assert origin_regex.fullmatch("http://127.0.0.1:3000")
    assert origin_regex.fullmatch("http://[::1]:3000")
    assert origin_regex.fullmatch("http://example.com:3000") is None
    assert origin_regex.fullmatch("https://localhost:3000") is None


def test_ags_widget_skill_allows_and_requires_live_coding_tool():
    skill_paths = [
        SERVER_ROOT.parent
        / "ab-external-marketplace"
        / "plugins"
        / "accelbyte-ai-plugins"
        / "skills"
        / "ags"
        / "subskills"
        / "generate-ui.md",
        SERVER_ROOT.parent
        / "ab-external-marketplace"
        / "content"
        / "skills"
        / "ags"
        / "subskills"
        / "generate-ui.md",
    ]

    for skill_path in skill_paths:
        skill_text = skill_path.read_text(encoding="utf-8")
        assert "mcp__accelbyte-unreal-sdk__unreal_live_coding_compile" in skill_text
        assert "call `unreal_live_coding_compile` with `waitForCompletion: true`" in skill_text
        assert "waitForCompletion: false" not in skill_text
        assert "wait for the user to confirm the editor compile finished" not in skill_text
        assert "unreal_build_editor" in skill_text
        assert "unreal_close_editor" in skill_text
        assert "unreal_launch_editor" in skill_text
        assert "current generated UI files" in skill_text
        assert "Ask for explicit user approval before closing Unreal Editor" in skill_text
        assert "Do NOT suggest `Build.bat` as the first/default path" in skill_text
        assert "Report required manual steps" not in skill_text
        assert "Do not tell the user to reparent the Blueprint or edit ListView/TileView/TreeView Entry Widget Class manually" in skill_text


def test_legacy_buildbat_examples_are_not_live_coding_guidance():
    legacy_path = SERVER_ROOT / "docs" / "superpowers" / "specs" / "took_long.md"
    if legacy_path.exists():
        legacy_text = legacy_path.read_text(encoding="utf-8")
        assert "Historical example only" in legacy_text
        assert "unreal_live_coding_compile" in legacy_text
