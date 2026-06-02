import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock

import httpx
import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = SERVER_ROOT / "data" / "AccelByteUITools" / "Tools"


sys.path.insert(0, str(TOOLS_ROOT))
try:
    import project_style_context
finally:
    try:
        sys.path.remove(str(TOOLS_ROOT))
    except ValueError:
        pass


@pytest.fixture
def accelbyte_ui_tools():
    module_name = "accelbyte_ui_tools_under_test"
    module_path = SERVER_ROOT / "accelbyte_ui_tools.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        if previous_module is None:
            if sys.modules.get(module_name) is module:
                del sys.modules[module_name]
        else:
            sys.modules[module_name] = previous_module


def _write_project_local_widget_spec(project_root: Path):
    widget_spec_path = (
        project_root / "Plugins" / "AccelByteUITools" / "Tools" / "widget_spec.py"
    )
    widget_spec_path.parent.mkdir(parents=True)
    widget_spec_path.write_text(
        """
from pathlib import Path


class ProjectLocalSpec:
    asset_path = "/Game/ProjectLocal/UI/Generated/WBP_ProjectLocal"

    def widget_count(self):
        return 7

    def variable_widget_names(self):
        return ["ProjectLocalButton"]


def load_spec_file(path):
    marker = Path(path).read_text(encoding="utf-8")
    if "project-local-marker" not in marker:
        raise ValueError("project-local widget_spec.py was not used")
    return ProjectLocalSpec()
""".lstrip(),
        encoding="utf-8",
    )
    return widget_spec_path


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("GET", "http://127.0.0.1"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self.payload


def _write_project_cli(project_root: Path):
    cli_path = (
        project_root
        / "Plugins"
        / "AccelByteUITools"
        / "Tools"
        / "accelbyte_ui_tools.py"
    )
    cli_path.parent.mkdir(parents=True)
    cli_path.write_text("# test cli\n", encoding="utf-8")
    return cli_path


def _generated_root(children: list[dict] | None = None) -> dict:
    content_children = children or [{"type": "TextBlock", "name": "TitleText", "text": "Ready"}]
    for child in content_children:
        child.setdefault("slot", {"h_align": "fill", "v_align": "fill"})
    return {
        "type": "Border",
        "name": "PanelBackground",
        "children": [
            {
                "type": "Overlay",
                "name": "ContentContainer",
                "padding": [20, 20, 20, 20],
                "slot": {"h_align": "fill", "v_align": "fill"},
                "children": content_children,
            }
        ],
    }


def _write_valid_spec(path: Path, *, asset_path: str = "/Game/ByteWars/UI/Generated/WBP_Test"):
    path.write_text(
        json.dumps(
            {
                "asset_path": asset_path,
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(),
            }
        ),
        encoding="utf-8",
    )


def _approve_style_context(project_root: Path) -> None:
    context = project_style_context.discover_project_style(project_root)
    project_style_context.write_style_context(context, project_root)
    project_style_context.approve_style_context(context, project_root)


def _write_style_project(project_root: Path, *, common_ui: bool = True, compatible_list: bool = False) -> None:
    plugins = [{"Name": "CommonUI", "Enabled": True}] if common_ui else [{"Name": "UMG", "Enabled": True}]
    (project_root / "AccelByteWars.uproject").write_text(json.dumps({"Plugins": plugins}), encoding="utf-8")
    styles = project_root / "Content" / "UI" / "Styles"
    styles.mkdir(parents=True, exist_ok=True)
    (styles / "PrimaryButtonStyle.uasset").write_text("", encoding="utf-8")
    (styles / "BodyTextStyle.uasset").write_text("", encoding="utf-8")
    lists = project_root / "Content" / "UI" / "Lists"
    lists.mkdir(parents=True, exist_ok=True)
    (lists / "WBP_PlayerEntry.uasset").write_text("", encoding="utf-8")
    if compatible_list:
        source = project_root / "Source" / "Game" / "UI"
        source.mkdir(parents=True, exist_ok=True)
        (source / "PlayerEntry.h").write_text(
            "class GAME_API UPlayerEntry : public UUserWidget, public IUserObjectListEntry {};",
            encoding="utf-8",
        )


def _valid_common_ui_spec(asset_path: str = "/Game/UI/Generated/WBP_Styled") -> dict:
    return {
        "asset_path": asset_path,
        "parent_class": "/Script/CommonUI.CommonActivatableWidget",
        "ui_mode": "common_ui",
        "root": {
            "type": "Border",
            "name": "PanelBackground",
            "children": [
                {
                    "type": "Overlay",
                    "name": "ContentContainer",
                    "padding": [20, 20, 20, 20],
                    "slot": {"h_align": "fill", "v_align": "fill"},
                    "children": [
                        {
                            "type": "TextBlock",
                            "name": "BodyText",
                            "text": "Ready",
                            "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                            "slot": {"h_align": "fill", "v_align": "fill"},
                        }
                    ],
                }
            ],
        },
    }


def test_resolve_project_root_accepts_directory_with_uproject(tmp_path: Path, accelbyte_ui_tools):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")

    result = accelbyte_ui_tools.resolve_project_root(str(tmp_path))

    assert result == tmp_path.resolve()


def test_resolve_project_root_accepts_uproject_file(tmp_path: Path, accelbyte_ui_tools):
    project_file = tmp_path / "AccelByteWars.uproject"
    project_file.write_text("{}", encoding="utf-8")

    result = accelbyte_ui_tools.resolve_project_root(str(project_file))

    assert result == tmp_path.resolve()


def test_resolve_project_root_resolves_relative_path_against_workspace_root(
    tmp_path: Path, accelbyte_ui_tools
):
    project_root = tmp_path / "Project"
    project_root.mkdir()
    (project_root / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")

    result = accelbyte_ui_tools.resolve_project_root("Project", workspace_root=str(tmp_path))

    assert result == project_root.resolve()


def test_resolve_project_root_rejects_missing_path(tmp_path: Path, accelbyte_ui_tools):
    missing_path = tmp_path / "MissingProject"

    with pytest.raises(ValueError, match="Project path is not a directory"):
        accelbyte_ui_tools.resolve_project_root(str(missing_path))


def test_resolve_project_root_rejects_directory_without_uproject(tmp_path: Path, accelbyte_ui_tools):
    with pytest.raises(ValueError, match="No .uproject file found"):
        accelbyte_ui_tools.resolve_project_root(str(tmp_path))


def test_ensure_path_inside_accepts_child(tmp_path: Path, accelbyte_ui_tools):
    child = tmp_path / "Content" / "Widget.json"

    result = accelbyte_ui_tools.ensure_path_inside(tmp_path, child)

    assert result == child.resolve()


def test_ensure_path_inside_rejects_escape(tmp_path: Path, accelbyte_ui_tools):
    outside = tmp_path.parent / "escape.json"

    with pytest.raises(ValueError, match="outside project root"):
        accelbyte_ui_tools.ensure_path_inside(tmp_path, outside)


def test_accelbyte_ui_validate_accepts_valid_spec(tmp_path: Path, accelbyte_ui_tools):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_Test",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(),
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["asset_path"] == "/Game/ByteWars/UI/Generated/WBP_Test"
    assert result["widget_count"] == 3
    assert result["bindings"] == []


def test_accelbyte_ui_validate_returns_binding_metadata(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "bindings.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_Bindings",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "AGSTextInput",
                            "name": "UsernameInput",
                            "is_variable": True,
                            "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput.WBP_AGS_TextInput_C",
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["variable_widget_names"] == ["UsernameInput"]
    assert result["bindings"][0]["widget_name"] == "UsernameInput"
    assert result["bindings"][0]["cpp_type"] == "UAGSTextInputBase"
    assert "BindWidget" in result["bindings"][0]["bind_meta"]
    assert "BindWidgetOptional" not in result["bindings"][0]["bind_meta"]


def test_parse_backing_bindings_accepts_raw_and_tobjectptr_properties(accelbyte_ui_tools):
    parsed = accelbyte_ui_tools._parse_backing_bindings(
        """
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UTextBlock* TitleText;

        UPROPERTY(BlueprintReadOnly, Category = "UI", meta = (
            BindWidgetOptional,
            BlueprintProtected = true,
            AllowPrivateAccess = true
        ))
        TObjectPtr<UButton> SubmitButton;

        UPROPERTY(BlueprintReadOnly, meta = (BindWidget))
        class UImage* IconImage;

        UPROPERTY(BlueprintReadOnly, meta = (BindWidget))
        TObjectPtr<class UCommonTextBlock> CommonTitleText;
        """
    )

    assert parsed["TitleText"]["cpp_type"] == "UTextBlock"
    assert parsed["SubmitButton"]["cpp_type"] == "UButton"
    assert "BindWidgetOptional" in parsed["SubmitButton"]["meta"]
    assert parsed["IconImage"]["cpp_type"] == "UImage"
    assert parsed["CommonTitleText"]["cpp_type"] == "UCommonTextBlock"


def test_accelbyte_ui_verify_backing_class_requires_bind_widget(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "login.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_LoginPanel",
                "parent_class": "/Script/AccelByteWars.LoginPanelWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "WidgetSwitcher",
                            "name": "StateSwitcher",
                            "is_variable": True,
                            "children": [
                                {"type": "AGSStatusMessage", "name": "IdlePanel", "is_variable": True},
                                {"type": "AGSLoadingIndicator", "name": "LoadingPanel", "is_variable": True},
                                {
                                    "type": "VerticalBox",
                                    "name": "SuccessPanel",
                                    "is_variable": True,
                                    "children": [
                                        {"type": "AGSTextInput", "name": "UsernameInput", "is_variable": True},
                                        {"type": "AGSPasswordInput", "name": "PasswordInput", "is_variable": True},
                                        {"type": "AGSBaseButton", "name": "SubmitButton", "is_variable": True},
                                    ],
                                },
                                {"type": "AGSEmptyState", "name": "EmptyPanel", "is_variable": True},
                                {"type": "AGSErrorState", "name": "ErrorPanel", "is_variable": True},
                            ],
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    header_path = tmp_path / "Source" / "AccelByteWars" / "LoginPanelWidget.h"
    header_path.parent.mkdir(parents=True)
    header_path.write_text(
        """
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UWidgetSwitcher* StateSwitcher;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAGSStatusMessageBase* IdlePanel;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAGSLoadingIndicatorBase* LoadingPanel;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UVerticalBox* SuccessPanel;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAGSTextInputBase* UsernameInput;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAGSTextInputBase* PasswordInput;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAGSButtonBase* SubmitButton;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAGSEmptyStateBase* EmptyPanel;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAGSErrorStateBase* ErrorPanel;
        """,
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "headerPath": str(header_path)}
        )
    )

    assert result["ok"] is True, result
    verified = {item["widget_name"]: item for item in result["verified_backing_bindings"]}
    assert verified["EmptyPanel"]["expected_cpp_type"] == "UAGSEmptyStateBase"
    assert all(item["verified"] for item in verified.values())


def test_accelbyte_ui_verify_backing_class_rejects_optional_and_wrong_types(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "bindings.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_Bindings",
                "parent_class": "/Script/AccelByteWars.LoginPanelWidget",
                "root": _generated_root(
                    [
                        {"type": "AGSTextInput", "name": "UsernameInput", "is_variable": True},
                        {"type": "AGSBaseButton", "name": "SubmitButton", "is_variable": True},
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    header_path = tmp_path / "Source" / "AccelByteWars" / "LoginPanelWidget.h"
    header_path.parent.mkdir(parents=True)
    header_path.write_text(
        """
        UPROPERTY(BlueprintReadOnly, meta = (BindWidgetOptional, BlueprintProtected = true, AllowPrivateAccess = true))
        UEditableTextBox* UsernameInput;
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UButton* SubmitButton;
        """,
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "headerPath": str(header_path)}
        )
    )

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "backing_binding_mismatch"
    verified = {item["widget_name"]: item for item in result["verified_backing_bindings"]}
    assert verified["UsernameInput"]["reason"] == "optional_binding_not_allowed"
    assert verified["SubmitButton"]["reason"] == "wrong_cpp_type"


def test_accelbyte_ui_verify_backing_class_returns_structured_spec_errors(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "bindings.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_Bindings",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root([{"type": "TextBlock", "name": "TitleText", "is_variable": True}]),
            }
        ),
        encoding="utf-8",
    )
    header_path = tmp_path / "Source" / "Game" / "BindingsWidget.h"
    header_path.parent.mkdir(parents=True)
    header_path.write_text("", encoding="utf-8")

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "headerPath": str(header_path),
                "autoApproveStyle": False,
            }
        )
    )

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "style_context_approval_required"


def test_accelbyte_ui_validate_accepts_project_relative_spec_path(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_Relative",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(),
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {"projectPath": str(tmp_path), "specPath": "Content/UI/spec.json"}
        )
    )

    assert result["ok"] is True, result
    assert result["asset_path"] == "/Game/ByteWars/UI/Generated/WBP_Relative"


def test_accelbyte_ui_validate_rejects_spec_outside_project(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    outside = tmp_path.parent / "outside_widget_spec.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="outside project root"):
        asyncio.run(
            accelbyte_ui_tools.accelbyte_ui_validate(
                {"projectPath": str(tmp_path), "specPath": str(outside)}
            )
        )


def test_accelbyte_ui_validate_prefers_project_local_widget_spec(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_local_widget_spec(tmp_path)
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("project-local-marker", encoding="utf-8")

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path)}
        )
    )

    assert result == {
        "ok": True,
        "asset_path": "/Game/ProjectLocal/UI/Generated/WBP_ProjectLocal",
        "widget_count": 7,
        "variable_widget_names": ["ProjectLocalButton"],
        "warnings": [
            {
                "code": "legacy_spec_fallback",
                "message": (
                    "Spec was loaded through a legacy project-local parser because it is not valid JSON. "
                    "Canonical JSON normalization and style-context validation were bypassed."
                ),
                "advisory": True,
            }
        ],
    }


def test_accelbyte_ui_validate_cleans_up_dynamic_module_registration(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_local_widget_spec(tmp_path)
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("project-local-marker", encoding="utf-8")

    before_modules = set(sys.modules)
    asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path)}
        )
    )
    after_modules = set(sys.modules)
    leaked_modules = [
        name
        for name in after_modules - before_modules
        if name.startswith(accelbyte_ui_tools.WIDGET_SPEC_RUNTIME_MODULE_PREFIX)
    ]

    assert "widget_spec_runtime" not in sys.modules
    assert leaked_modules == []


def test_accelbyte_ui_bridge_health_gets_bridge_health(
    monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    get_mock = AsyncMock(return_value=FakeResponse({"ok": True, "service": "AccelByteUITools"}))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.get = get_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_bridge_health(
            {"bridgeUrl": "http://127.0.0.1:9999/"}
        )
    )

    assert result == {"ok": True, "service": "AccelByteUITools"}
    get_mock.assert_awaited_once_with(
        "http://127.0.0.1:9999/accelbyte-ui-tools/health"
    )


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("bridge unavailable"),
        httpx.TimeoutException("bridge timed out"),
    ],
)
def test_accelbyte_ui_bridge_health_reports_unavailable_bridge(
    monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools, error
):
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.get = AsyncMock(side_effect=error)
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(accelbyte_ui_tools.accelbyte_ui_bridge_health({}))

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "bridge_unavailable"


def test_accelbyte_ui_bridge_health_reports_http_error(
    monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.get = AsyncMock(return_value=FakeResponse({}, 500))
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(accelbyte_ui_tools.accelbyte_ui_bridge_health({}))

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "bridge_http_error"


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse([]),
        type(
            "InvalidJsonResponse",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: (_ for _ in ()).throw(json.JSONDecodeError("bad json", "", 0)),
            },
        )(),
    ],
)
def test_accelbyte_ui_bridge_health_reports_invalid_response(
    monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools, response
):
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.get = AsyncMock(return_value=response)
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(accelbyte_ui_tools.accelbyte_ui_bridge_health({}))

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "bridge_invalid_response"


def test_accelbyte_ui_generate_posts_spec_to_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_Test",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(),
            }
        ),
        encoding="utf-8",
    )

    post_mock = AsyncMock(
        return_value=FakeResponse(
            {"ok": True, "asset_path": "/Game/ByteWars/UI/Generated/WBP_Test"}
        )
    )
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "bridgeUrl": "http://127.0.0.1:9999",
                "mode": "bridge",
                "force": True,
            }
        )
    )

    assert result["ok"] is True, result
    post_mock.assert_awaited_once()
    assert post_mock.await_args.args[0] == (
        "http://127.0.0.1:9999/accelbyte-ui-tools/generate"
    )
    expected_root = _generated_root()
    expected_root["style"] = {"background_color": [0.0, 0.0, 0.0, 0.1]}
    assert post_mock.await_args.kwargs["json"] == {
        "force": True,
        "spec": {
            "asset_path": "/Game/ByteWars/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": expected_root,
            "ui_mode": "umg",
        },
    }


def test_accelbyte_ui_generate_registers_generated_panel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "panel.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardPanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(),
            }
        ),
        encoding="utf-8",
    )
    post_mock = AsyncMock(return_value=FakeResponse({"ok": True}))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "bridgeUrl": "http://127.0.0.1:9999"}
        )
    )

    registry = project_style_context.load_generated_components_registry(tmp_path)
    assert result["ok"] is True, result
    assert registry["__generated_widgets"][0]["asset_path"] == "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardPanel"
    assert registry["__generated_widgets"][0]["roles"] == ["panel"]


def test_accelbyte_ui_generate_does_not_register_failed_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "panel.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardPanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(),
            }
        ),
        encoding="utf-8",
    )
    post_mock = AsyncMock(return_value=FakeResponse({"ok": False, "errors": [{"code": "failed"}]}))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "bridgeUrl": "http://127.0.0.1:9999"}
        )
    )

    assert result["ok"] is False
    assert project_style_context.load_generated_components_registry(tmp_path) == {}


def test_accelbyte_ui_generate_propagates_stale_live_coding_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "stale.json"
    spec_path.parent.mkdir(parents=True)
    _write_valid_spec(spec_path)

    stale_response = {
        "ok": False,
        "asset_path": "/Game/ByteWars/UI/Generated/WBP_Test",
        "verified_widget_classes": [
            {
                "widget_name": "UsernameInput",
                "expected_widget_class": "/Script/AccelByteUITools.AGSTextInputBase",
                "actual_widget_class": "/Script/AccelByteUITools.AGSTextInputBase_LIVE_CODING",
                "class_stability": "stale_live_coding",
                "verified": False,
            }
        ],
        "errors": [
            {
                "code": "stale_live_coding_class",
                "message": "The editor has stale Live Coding class state for 'AGSTextInputBase LIVE CODING'. Restart the editor or run a full rebuild, then regenerate.",
            }
        ],
    }
    post_mock = AsyncMock(return_value=FakeResponse(stale_response))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "bridgeUrl": "http://127.0.0.1:9999",
                "mode": "bridge",
            }
        )
    )

    assert result == stale_response
    assert result["errors"][0]["code"] == "stale_live_coding_class"
    assert result["verified_widget_classes"][0]["class_stability"] == "stale_live_coding"


def test_accelbyte_ui_generate_posts_normalized_ags_spec_to_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_ThemeSafe",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "TextBlock",
                            "name": "TitleText",
                            "text": "Leaderboard",
                            "style": {"color": [0.9, 0.9, 0.9, 1.0]},
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )

    post_mock = AsyncMock(return_value=FakeResponse({"ok": True}))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "bridgeUrl": "http://127.0.0.1:9999",
                "mode": "bridge",
            }
        )
    )

    posted_spec = post_mock.await_args.kwargs["json"]["spec"]
    assert result["ok"] is True, result
    assert posted_spec["root"]["children"][0]["children"][0]["style"]["color"] == [0.05, 0.06, 0.08, 1.0]


def test_accelbyte_ui_validate_can_write_normalized_spec(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    normalized_path = tmp_path / "Saved" / "Generated" / "Spec" / "normalized.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_Normalized",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "TextBlock",
                            "name": "TitleText",
                            "text": "Title",
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert result["ok"] is True, result
    assert result["normalized_spec_path"] == str(normalized_path.resolve())
    assert normalized["root"]["children"][0]["children"][0]["style"]["color"] == [0.05, 0.06, 0.08, 1.0]


def test_accelbyte_ui_generate_auto_falls_back_to_commandlet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_cli(tmp_path)
    spec_path = tmp_path / "Content" / "UI" / "spec.json"
    spec_path.parent.mkdir(parents=True)
    _write_valid_spec(spec_path)

    async def fail_bridge(*args, **kwargs):
        raise httpx.ConnectError("bridge unavailable")

    run_calls = []

    def fake_run(command, **kwargs):
        run_calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True, "mode": "commandlet"}),
            stderr="",
        )

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fail_bridge, raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "mode": "auto",
                "force": True,
                "editorExe": "D:/UE/UnrealEditor-Cmd.exe",
            }
        )
    )

    assert result == {"ok": True, "mode": "commandlet"}
    command, kwargs = run_calls[0]
    assert "generate" in command
    normalized_spec = tmp_path / "Saved" / "AccelByteUITools" / "spec.normalized.json"
    assert str(normalized_spec.resolve()) in command
    assert "--force" in command
    assert ["--editor-exe", "D:/UE/UnrealEditor-Cmd.exe"] == command[-2:]
    assert kwargs["cwd"] == tmp_path.resolve()
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False


def test_accelbyte_ui_generate_auto_rejects_commandlet_for_project_cpp_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_cli(tmp_path)
    spec_path = tmp_path / "Content" / "UI" / "script_backed.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_LoginPanel",
                "parent_class": "/Script/AccelByteWars.LoginPanelWidget",
                "root": _generated_root([{"type": "TextBlock", "name": "TitleText", "text": "Login"}]),
            }
        ),
        encoding="utf-8",
    )

    async def fail_bridge(*args, **kwargs):
        raise httpx.ConnectError("bridge unavailable")

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fail_bridge, raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: pytest.fail("commandlet fallback should not run"),
    )

    with pytest.raises(RuntimeError, match="Bridge generation is required"):
        asyncio.run(
            accelbyte_ui_tools.accelbyte_ui_generate(
                {
                    "projectPath": str(tmp_path),
                    "specPath": str(spec_path),
                    "mode": "auto",
                    "force": True,
                }
            )
        )


def test_accelbyte_ui_generate_validates_normalized_spec_before_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "invalid_generated_ags.json"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_Invalid",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root([{"type": "Button", "name": "NativeButton"}]),
            }
        ),
        encoding="utf-8",
    )

    async def post_bridge(*args, **kwargs):
        pytest.fail("invalid specs must not be posted to the bridge")

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_bridge, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "bridgeUrl": "http://127.0.0.1:9999",
                "mode": "bridge",
            }
        )
    )

    assert result["ok"] is False
    assert any("Button" in error["message"] or "AGSUI/Core" in error["message"] for error in result["errors"])


def test_accelbyte_ui_docs_do_not_recommend_direct_bridge_post():
    readme = (SERVER_ROOT / "data" / "AccelByteUITools" / "README.md").read_text(
        encoding="utf-8"
    )
    ags_docs = (
        SERVER_ROOT.parent
        / "ab-external-marketplace"
        / "plugins"
        / "accelbyte-ai-plugins"
        / "skills"
        / "ags"
        / "references"
        / "sdks"
        / "game-engine"
        / "unreal"
        / "ui"
        / "generate-ui.md"
    ).read_text(encoding="utf-8")

    assert "Invoke-WebRequest" not in readme
    assert "127.0.0.1:48757" not in readme
    assert "do not bypass this tool by sending raw JSON directly to the bridge" in ags_docs


def test_accelbyte_ui_generate_auto_does_not_fall_back_on_bridge_protocol_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_cli(tmp_path)
    spec_path = tmp_path / "spec.json"
    _write_valid_spec(spec_path)

    async def fail_bridge(*args, **kwargs):
        raise ValueError("Bridge response must be a JSON object")

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fail_bridge, raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: pytest.fail("commandlet fallback should not run"),
    )

    with pytest.raises(ValueError, match="Bridge response"):
        asyncio.run(
            accelbyte_ui_tools.accelbyte_ui_generate(
                {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "auto"}
            )
        )


def test_accelbyte_ui_generate_commandlet_normalizes_cli_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_cli(tmp_path)
    spec_path = tmp_path / "spec.json"
    _write_valid_spec(spec_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 1, stdout="", stderr="commandlet failed"
        ),
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "commandlet"}
        )
    )

    assert result == {
        "ok": False,
        "errors": [{"code": "cli_failed", "message": "commandlet failed"}],
    }


def test_accelbyte_ui_generate_commandlet_preserves_json_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_cli(tmp_path)
    spec_path = tmp_path / "spec.json"
    _write_valid_spec(spec_path)
    payload = {"ok": False, "errors": [{"code": "bad_spec", "message": "Invalid spec"}]}

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 1, stdout=json.dumps(payload), stderr="ignored"
        ),
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "commandlet"}
        )
    )

    assert result == payload


def test_accelbyte_ui_validate_rejects_ags_button_when_project_style_exists(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path)
    spec_path = tmp_path / "Content" / "UI" / "bad_button.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec = _valid_common_ui_spec()
    spec["root"]["children"][0]["children"].append(
        {
            "type": "AGSButton",
            "name": "SubmitButton",
            "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonButton.WBP_AGS_CommonButton_C",
            "slot": {"h_align": "fill", "v_align": "fill"},
        }
    )
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate({"projectPath": str(tmp_path), "specPath": str(spec_path)})
    )

    assert result["ok"] is False
    assert any(error["code"] == "project_button_required" for error in result["errors"])


def test_accelbyte_ui_validate_normalizes_common_ui_parent_to_project_base(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    source = tmp_path / "Source" / "AccelByteWars" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "AccelByteWarsActivatableWidget.h").write_text(
        "class ACCELBYTEWARS_API UAccelByteWarsActivatableWidget : public UCommonActivatableWidget {};",
        encoding="utf-8",
    )
    spec_path = tmp_path / "Content" / "UI" / "common_parent.json"
    normalized_path = tmp_path / "Saved" / "common_parent.normalized.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(_valid_common_ui_spec("/Game/UI/Generated/WBP_CommonParent")), encoding="utf-8")
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    assert result["ok"] is True, result
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert normalized["parent_class"] == "/Script/AccelByteWars.AccelByteWarsActivatableWidget"


def test_accelbyte_ui_generate_refuses_style_errors_before_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path)
    spec_path = tmp_path / "Content" / "UI" / "bad_text.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec = _valid_common_ui_spec()
    spec["root"]["children"][0]["children"][0].pop("text_style_class")
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    _approve_style_context(tmp_path)

    async def post_bridge(*args, **kwargs):
        pytest.fail("style-invalid specs must not post to the bridge")

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_bridge, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "bridge"}
        )
    )

    assert result["ok"] is False
    assert any(error["code"] == "missing_project_text_style" for error in result["errors"])


def test_accelbyte_ui_generate_posts_canonicalized_common_ui_text_to_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, compatible_list=True)
    spec_path = tmp_path / "Content" / "UI" / "good_text.json"
    normalized_path = tmp_path / "Saved" / "normalized.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(_valid_common_ui_spec()), encoding="utf-8")
    _approve_style_context(tmp_path)

    post_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_mock, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "mode": "bridge",
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    assert result["ok"] is True, result
    posted_spec = post_mock.await_args.args[2]["spec"]
    text_node = posted_spec["root"]["children"][0]["children"][0]
    assert text_node["class_path"] == "/Script/CommonUI.CommonTextBlock"
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert normalized["root"]["children"][0]["children"][0]["class_path"] == "/Script/CommonUI.CommonTextBlock"


def test_accelbyte_ui_validate_rejects_scrollbox_leaderboard_with_project_rows(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False, compatible_list=True)
    spec_path = tmp_path / "Content" / "UI" / "leaderboard.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_Leaderboard",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "ScrollBox",
                                    "name": "LeaderboardRows",
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate({"projectPath": str(tmp_path), "specPath": str(spec_path)})
    )

    assert result["ok"] is False
    assert any(error["code"] == "runtime_collection_requires_virtualized_list" for error in result["errors"])


def test_accelbyte_ui_validate_uses_project_cpp_class_mapping_for_bindings(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False, compatible_list=True)
    spec_path = tmp_path / "Content" / "UI" / "project_entry_binding.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
                {
                    "asset_path": "/Game/UI/Generated/WBP_ProjectEntryBinding",
                    "parent_class": "/Script/UMG.UserWidget",
                    "root": {
                        "type": "Border",
                        "name": "PanelBackground",
                        "children": [
                            {
                                "type": "Overlay",
                                "name": "ContentContainer",
                                "padding": [20, 20, 20, 20],
                                "slot": {"h_align": "fill", "v_align": "fill"},
                                "children": [
                                    {
                                        "type": "UserWidget",
                                        "name": "PlayerEntry",
                                        "class_path": "/Game/UI/Lists/WBP_PlayerEntry.WBP_PlayerEntry_C",
                                        "is_variable": True,
                                        "slot": {"h_align": "fill", "v_align": "fill"},
                                    }
                                ],
                            }
                        ],
                    },
                }
            ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate({"projectPath": str(tmp_path), "specPath": str(spec_path)})
    )

    assert result["ok"] is True, result
    assert result["bindings"][0]["cpp_type"] == "UPlayerEntry"


def test_accelbyte_ui_verify_backing_class_uses_project_cpp_class_mapping(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False, compatible_list=True)
    spec_path = tmp_path / "Content" / "UI" / "project_entry_binding.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_ProjectEntryBinding",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "UserWidget",
                                    "name": "PlayerEntry",
                                    "class_path": "/Game/UI/Lists/WBP_PlayerEntry.WBP_PlayerEntry_C",
                                    "is_variable": True,
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    header_path = tmp_path / "Source" / "Game" / "ProjectEntryBindingWidget.h"
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(
        """
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UPlayerEntry* PlayerEntry;
        """,
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "headerPath": str(header_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["bindings"][0]["cpp_type"] == "UPlayerEntry"


def test_accelbyte_ui_verify_backing_class_project_class_path_overrides_ags_alias(
    tmp_path: Path, accelbyte_ui_tools, monkeypatch
):
    _write_style_project(tmp_path, common_ui=True)
    button_source = tmp_path / "Source" / "Game" / "UI"
    button_source.mkdir(parents=True, exist_ok=True)
    (button_source / "AccelByteWarsButtonBase.h").write_text(
        "class GAME_API UAccelByteWarsButtonBase : public UCommonButtonBase {};",
        encoding="utf-8",
    )
    button_asset = tmp_path / "Content" / "UI" / "Common"
    button_asset.mkdir(parents=True, exist_ok=True)
    (button_asset / "W_MenuButton.uasset").write_text("", encoding="utf-8")

    spec_path = tmp_path / "Content" / "UI" / "project_button_binding.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_ProjectButtonBinding",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "AGSBaseButton",
                                    "name": "Btn_Back",
                                    "class_path": "/Game/UI/Common/W_MenuButton.W_MenuButton_C",
                                    "is_variable": True,
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    header_path = tmp_path / "Source" / "Game" / "ProjectStateBindingWidget.h"
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(
        """
        UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
        UAccelByteWarsButtonBase* Btn_Back;
        """,
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    async def fake_bridge_verify(*_args, **_kwargs):
        raise httpx.ConnectError("bridge unavailable")

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fake_bridge_verify)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "headerPath": str(header_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["bindings"][0]["cpp_type"] == "UAccelByteWarsButtonBase"
    assert result["bindings"][0]["resolution_source"] == "style_context"
    assert result["warnings"][0]["code"] == "bridge_verify_only_unavailable"


def test_accelbyte_ui_generate_verify_only_uses_bridge_resolved_binding(
    tmp_path: Path, accelbyte_ui_tools, monkeypatch
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "project_button_binding.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_ProjectButtonBinding",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "AGSBaseButton",
                            "name": "Btn_Back",
                            "class_path": "/Game/UI/Generated/W_MenuButton.W_MenuButton_C",
                            "is_variable": True,
                            "slot": {"h_align": "fill", "v_align": "fill"},
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )

    async def fake_post_bridge(url, route, payload, *, client=None):
        assert route == "/accelbyte-ui-tools/resolve"
        assert "verify_only" not in payload
        return {
            "ok": True,
            "resolve_only": True,
            "verify_only": True,
            "expected_collection_entries": [],
            "verified_widget_classes": [
                {
                    "widget_name": "Btn_Back",
                    "expected_widget_class": "/Script/AccelByteWars.AccelByteWarsButtonBase",
                    "actual_widget_class": "",
                    "class_stability": "stable",
                    "verified": True,
                }
            ],
        }

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fake_post_bridge)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "verify-only"}
        )
    )

    assert result["ok"] is True, result
    assert result["verify_only"] is True
    assert result["resolve_only"] is True
    assert result["bindings"][0]["cpp_type"] == "UAccelByteWarsButtonBase"
    assert result["bindings"][0]["expected_unreal_class"] == "/Script/AccelByteWars.AccelByteWarsButtonBase"
    assert result["bindings"][0]["resolution_source"] == "bridge"
    assert result["compatibility_alias"] == "accelbyte_ui_resolve"


def test_accelbyte_ui_resolve_returns_bridge_resolved_binding_and_collection_entries(
    tmp_path: Path, accelbyte_ui_tools, monkeypatch
):
    _write_style_project(tmp_path, common_ui=True, compatible_list=True)
    button_source = tmp_path / "Source" / "Game" / "UI"
    button_source.mkdir(parents=True, exist_ok=True)
    (button_source / "AccelByteWarsButtonBase.h").write_text(
        "class GAME_API UAccelByteWarsButtonBase : public UCommonButtonBase {};",
        encoding="utf-8",
    )
    button_asset = tmp_path / "Content" / "UI" / "Common"
    button_asset.mkdir(parents=True, exist_ok=True)
    (button_asset / "W_MenuButton.uasset").write_text("", encoding="utf-8")
    _approve_style_context(tmp_path)
    spec_path = tmp_path / "Content" / "UI" / "project_button_binding.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_ProjectButtonBinding",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "AGSBaseButton",
                            "name": "Btn_Back",
                            "class_path": "/Game/UI/Common/W_MenuButton.W_MenuButton_C",
                            "is_variable": True,
                            "slot": {"h_align": "fill", "v_align": "fill"},
                        },
                        {
                            "type": "ListView",
                            "name": "PlayerList",
                            "is_variable": True,
                            "entry_widget_class": "/Game/UI/Lists/WBP_PlayerEntry.WBP_PlayerEntry_C",
                            "slot": {"h_align": "fill", "v_align": "fill"},
                        },
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )

    async def fake_post_bridge(url, route, payload, *, client=None):
        assert route == "/accelbyte-ui-tools/resolve"
        assert payload["spec"]["asset_path"] == "/Game/UI/Generated/WBP_ProjectButtonBinding"
        return {
            "ok": True,
            "resolve_only": True,
            "expected_collection_entries": [
                {
                    "widget_name": "PlayerList",
                    "expected_entry_widget_class": "/Game/UI/Lists/WBP_PlayerEntry.WBP_PlayerEntry_C",
                }
            ],
            "verified_widget_classes": [
                {
                    "widget_name": "Btn_Back",
                    "expected_widget_class": "/Script/AccelByteWars.AccelByteWarsButtonBase",
                    "actual_widget_class": "",
                    "class_stability": "stable",
                    "verified": True,
                }
            ],
        }

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fake_post_bridge)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_resolve(
            {"projectPath": str(tmp_path), "specPath": str(spec_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["resolve_only"] is True
    assert result["bindings"][0]["cpp_type"] == "UAccelByteWarsButtonBase"
    assert result["bindings"][0]["resolution_source"] == "bridge"
    assert result["verified_widget_classes"][0]["expected_widget_class"] == "/Script/AccelByteWars.AccelByteWarsButtonBase"
    assert result["expected_collection_entries"] == [
        {
            "widget_name": "PlayerList",
            "expected_entry_widget_class": "/Game/UI/Lists/WBP_PlayerEntry.WBP_PlayerEntry_C",
        }
    ]
    assert {item["code"] for item in result["rebuild_advisories"]} == {
        "new_uclasses_before_rebuild",
        "uproperty_type_change_intermediate_cache",
    }


def test_accelbyte_ui_resolve_bridge_unavailable_keeps_style_context_mapping(
    tmp_path: Path, accelbyte_ui_tools, monkeypatch
):
    _write_style_project(tmp_path, common_ui=True)
    button_source = tmp_path / "Source" / "Game" / "UI"
    button_source.mkdir(parents=True, exist_ok=True)
    (button_source / "AccelByteWarsButtonBase.h").write_text(
        "class GAME_API UAccelByteWarsButtonBase : public UCommonButtonBase {};",
        encoding="utf-8",
    )
    button_asset = tmp_path / "Content" / "UI" / "Common"
    button_asset.mkdir(parents=True, exist_ok=True)
    (button_asset / "W_MenuButton.uasset").write_text("", encoding="utf-8")
    spec_path = tmp_path / "Content" / "UI" / "project_button_binding.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_ProjectButtonBinding",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "AGSBaseButton",
                            "name": "Btn_Back",
                            "class_path": "/Game/UI/Common/W_MenuButton.W_MenuButton_C",
                            "is_variable": True,
                            "slot": {"h_align": "fill", "v_align": "fill"},
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    async def fake_bridge_resolve(*_args, **_kwargs):
        raise httpx.ConnectError("bridge unavailable")

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fake_bridge_resolve)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_resolve(
            {"projectPath": str(tmp_path), "specPath": str(spec_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["bindings"][0]["cpp_type"] == "UAccelByteWarsButtonBase"
    assert result["bindings"][0]["resolution_source"] == "style_context"
    assert result["warnings"][0]["code"] == "bridge_verify_only_unavailable"


def test_accelbyte_ui_verify_backing_class_accepts_tobjectptr_binding_and_final_common_ui_parent(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    source = tmp_path / "Source" / "AccelByteWars" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "AccelByteWarsActivatableWidget.h").write_text(
        "class ACCELBYTEWARS_API UAccelByteWarsActivatableWidget : public UCommonActivatableWidget {};",
        encoding="utf-8",
    )
    header_path = source / "StoreWidget.h"
    header_path.write_text(
        """
        class ACCELBYTEWARS_API UStoreWidget : public UAccelByteWarsActivatableWidget
        {
            GENERATED_BODY()

            UPROPERTY(BlueprintReadOnly, Category = "Store", meta = (
                BindWidget,
                BlueprintProtected = true,
                AllowPrivateAccess = true
            ))
            TObjectPtr<UCommonTextBlock> BodyText;
        };
        """,
        encoding="utf-8",
    )
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "store.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_Store",
                "parent_class": "/Script/AccelByteWars.StoreWidget",
                "ui_mode": "common_ui",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "TextBlock",
                                    "name": "BodyText",
                                    "text": "Store",
                                    "is_variable": True,
                                    "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "headerPath": str(header_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["asset_path"] == "/Game/UI/Generated/WBP_Store"
    assert result["bindings"][0]["cpp_type"] == "UCommonTextBlock"
    assert result["verified_backing_bindings"][0]["actual_cpp_type"] == "UCommonTextBlock"


def test_accelbyte_ui_verify_backing_class_accepts_final_generated_list_entry_parent(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    source = tmp_path / "Source" / "Game" / "AGS" / "UI" / "Generated" / "Leaderboard"
    source.mkdir(parents=True, exist_ok=True)
    (source / "AccelByteWarsWidgetEntry.h").write_text(
        "class GAME_API UAccelByteWarsWidgetEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )
    header_path = source / "LeaderboardEntryWidget.h"
    header_path.write_text(
        """
        class GAME_API ULeaderboardEntryWidget : public UAccelByteWarsWidgetEntry
        {
            GENERATED_BODY()

            UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
            UCommonTextBlock* Tb_Rank;
        };
        """,
        encoding="utf-8",
    )
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "leaderboard_entry.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_LeaderboardEntry",
                "parent_class": "/Script/Game.LeaderboardEntryWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "TextBlock",
                            "name": "Tb_Rank",
                            "is_variable": True,
                            "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "headerPath": str(header_path)}
        )
    )

    assert result["ok"] is True, result
    assert result["asset_path"] == "/Game/AGS/UI/Generated/WBP_AGS_LeaderboardEntry"
    assert result["bindings"][0]["widget_name"] == "Tb_Rank"


def test_accelbyte_ui_verify_backing_class_rejects_temporary_fallback_parent(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    source = tmp_path / "Source" / "AccelByteWars" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    header_path = source / "LeaderboardWidget.h"
    header_path.write_text(
        """
        class ACCELBYTEWARS_API ULeaderboardWidget : public UCommonActivatableWidget
        {
            GENERATED_BODY()

            UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
            UCommonTextBlock* BodyText;
        };
        """,
        encoding="utf-8",
    )
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "leaderboard.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_Leaderboard",
                "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
                "ui_mode": "common_ui",
                "root": _generated_root([{"type": "TextBlock", "name": "BodyText", "is_variable": True}]),
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "headerPath": str(header_path)}
        )
    )

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "final_parent_required"
    assert "Do not temporarily switch" in result["errors"][0]["message"]
    assert "/Script/AccelByteWars.LeaderboardWidget" in result["errors"][0]["message"]


def test_accelbyte_ui_generate_keeps_final_script_backed_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    source = tmp_path / "Source" / "AccelByteWars" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "AccelByteWarsActivatableWidget.h").write_text(
        "class ACCELBYTEWARS_API UAccelByteWarsActivatableWidget : public UCommonActivatableWidget {};",
        encoding="utf-8",
    )
    (source / "StoreWidget.h").write_text(
        "class ACCELBYTEWARS_API UStoreWidget : public UAccelByteWarsActivatableWidget {};",
        encoding="utf-8",
    )
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "store.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_Store",
                "parent_class": "/Script/AccelByteWars.StoreWidget",
                "ui_mode": "common_ui",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "TextBlock",
                                    "name": "Tb_Title",
                                    "text": "Store",
                                    "is_variable": True,
                                    "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)
    post_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_mock, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "bridge"}
        )
    )

    posted_spec = post_mock.await_args.args[2]["spec"]
    assert result["ok"] is True, result
    assert posted_spec["parent_class"] == "/Script/AccelByteWars.StoreWidget"
    assert result["parent_class"] == "/Script/AccelByteWars.StoreWidget"


def test_accelbyte_ui_verify_backing_class_can_disable_style_auto_approval(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    source = tmp_path / "Source" / "AccelByteWars" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "AccelByteWarsActivatableWidget.h").write_text(
        "class ACCELBYTEWARS_API UAccelByteWarsActivatableWidget : public UCommonActivatableWidget {};",
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)
    header_path = source / "StoreWidget.h"
    header_path.write_text(
        """
        class ACCELBYTEWARS_API UStoreWidget : public UAccelByteWarsActivatableWidget
        {
            GENERATED_BODY()

            UPROPERTY(BlueprintReadOnly, meta = (BindWidget, BlueprintProtected = true, AllowPrivateAccess = true))
            TObjectPtr<UCommonTextBlock> BodyText;
        };
        """,
        encoding="utf-8",
    )
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "store.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_Store",
                "parent_class": "/Script/AccelByteWars.StoreWidget",
                "ui_mode": "common_ui",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "TextBlock",
                                    "name": "BodyText",
                                    "text": "Store",
                                    "is_variable": True,
                                    "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_verify_backing_class(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "headerPath": str(header_path),
                "autoApproveStyle": False,
            }
        )
    )

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "style_context_approval_required"


def test_generate_project_core_widgets_reports_partial_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    _approve_style_context(tmp_path)

    async def post_bridge(*args, **kwargs):
        return {"ok": False, "errors": [{"code": "bridge_rejected", "message": "Rejected"}]}

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_bridge, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.generate_project_core_widgets(
            {"projectPath": str(tmp_path), "role": "state_empty"}
        )
    )

    assert result["ok"] is False
    assert result["results"][0]["status"] == "bridge_rejected"
    assert result["errors"][0]["code"] == "core_widget_generation_failed"


def test_generate_project_core_widgets_refreshes_context_for_idle_panel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    _approve_style_context(tmp_path)

    async def post_bridge(*args, **kwargs):
        return {"ok": True}

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_bridge, raising=False)

    generation = asyncio.run(
        accelbyte_ui_tools.generate_project_core_widgets(
            {"projectPath": str(tmp_path), "role": "state_idle"}
        )
    )

    assert generation["ok"] is True
    assert generation["style_context_refreshed"] is True

    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "idle_state_panel.json"
    normalized_path = tmp_path / "Saved" / "idle_state_panel.normalized.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_IdleStatePanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root([{"type": "AGSStatusMessage", "name": "IdleState", "is_variable": True}]),
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    assert result["ok"] is True, result
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    idle_node = normalized["root"]["children"][0]["children"][0]
    assert idle_node["class_path"] == "/Game/AGS/UI/Components/WBP_AGS_ProjectStatusPanel.WBP_AGS_ProjectStatusPanel_C"


def test_generate_project_core_widgets_does_not_apply_common_button_style_to_ags_button(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    styles = tmp_path / "Content" / "UI" / "Styles"
    (styles / "SecondaryButtonStyle.uasset").write_text("", encoding="utf-8")
    _approve_style_context(tmp_path)

    posted_specs = []

    async def post_bridge(*args, **kwargs):
        posted_specs.append(args[2]["spec"])
        return {"ok": True}

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_bridge, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.generate_project_core_widgets(
            {"projectPath": str(tmp_path), "role": "state_error"}
        )
    )

    retry_button = posted_specs[0]["root"]["children"][0]["children"][0]["children"][2]
    assert result["ok"] is True, result
    assert retry_button["name"] == "Btn_Retry"
    assert "button_style_class" not in retry_button


def test_generate_project_core_widgets_uses_project_button_widget_for_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    buttons = tmp_path / "Content" / "UI" / "Buttons"
    buttons.mkdir(parents=True, exist_ok=True)
    (buttons / "WBP_MenuButton.uasset").write_text("", encoding="utf-8")
    _approve_style_context(tmp_path)

    posted_specs = []

    async def post_bridge(*args, **kwargs):
        posted_specs.append(args[2]["spec"])
        return {"ok": True}

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_bridge, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.generate_project_core_widgets(
            {"projectPath": str(tmp_path), "role": "state_error"}
        )
    )

    retry_button = posted_specs[0]["root"]["children"][0]["children"][0]["children"][2]
    assert result["ok"] is True, result
    assert retry_button["class_path"] == "/Game/UI/Buttons/WBP_MenuButton.WBP_MenuButton_C"
    assert retry_button["button_style_class"] == "/Game/UI/Styles/PrimaryButtonStyle.PrimaryButtonStyle_C"


def test_generate_project_core_widgets_retries_partial_existing_asset_with_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    _approve_style_context(tmp_path)
    calls = []

    async def post_bridge(*args, **kwargs):
        payload = args[2]
        calls.append(payload["force"])
        if len(calls) == 1:
            return {"ok": False, "errors": [{"code": "asset_exists", "message": "Asset already exists: /Game/AGS/UI/Components/WBP_AGS_ProjectErrorPanel"}]}
        return {"ok": True}

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_bridge, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.generate_project_core_widgets(
            {"projectPath": str(tmp_path), "role": "state_error"}
        )
    )

    assert result["ok"] is True, result
    assert calls == [False, True]
    assert result["results"][0]["force_retry"] is True


def test_accelbyte_ui_validate_resolves_core_role_and_strips_directive(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    registry_path = tmp_path / "Saved" / "AccelByteUITools" / "generated_project_components.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "state_idle": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStatusPanel",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStatusPanel.WBP_AGS_ProjectStatusPanel_C",
                    "spec_path": "Saved/Generated/Spec/Components/WBP_AGS_ProjectStatusPanel.json",
                },
                "state_loading": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectLoadingPanel",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectLoadingPanel.WBP_AGS_ProjectLoadingPanel_C",
                    "spec_path": "Saved/Generated/Spec/Components/WBP_AGS_ProjectLoadingPanel.json",
                },
                "state_empty": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C",
                    "spec_path": "Saved/Generated/Spec/Components/WBP_AGS_ProjectEmptyPanel.json",
                },
                "state_error": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectErrorPanel",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectErrorPanel.WBP_AGS_ProjectErrorPanel_C",
                    "spec_path": "Saved/Generated/Spec/Components/WBP_AGS_ProjectErrorPanel.json",
                }
            }
        ),
        encoding="utf-8",
    )
    spec_path = tmp_path / "Content" / "UI" / "core_role_panel.json"
    normalized_path = tmp_path / "Saved" / "normalized_core_role.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_CoreRolePanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "WidgetSwitcher",
                                    "name": "StateSwitcher",
                                    "is_variable": True,
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                    "children": [
                                        {"type": "AGSStatusMessage", "name": "IdleState", "is_variable": True},
                                        {"type": "AGSLoadingIndicator", "name": "LoadingState", "is_variable": True},
                                        {"type": "VerticalBox", "name": "SuccessState", "is_variable": True},
                                        {
                                            "type": "UserWidget",
                                            "name": "EmptyState",
                                            "is_variable": True,
                                            "core_role": "state_empty",
                                        },
                                        {"type": "AGSErrorState", "name": "ErrorState", "is_variable": True},
                                    ],
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    empty_state = normalized["root"]["children"][0]["children"][0]["children"][3]
    assert result["ok"] is True, result
    assert empty_state["class_path"] == "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C"
    assert "core_role" not in empty_state
    assert "_core_role" not in empty_state
    empty_binding = next(binding for binding in result["bindings"] if binding["widget_name"] == "EmptyState")
    assert empty_binding["class_path"] == empty_state["class_path"]


def test_accelbyte_ui_generate_posts_core_role_resolution_without_directive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    registry_path = tmp_path / "Saved" / "AccelByteUITools" / "generated_project_components.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "state_error": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectErrorPanel",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectErrorPanel.WBP_AGS_ProjectErrorPanel_C",
                    "spec_path": "Saved/Generated/Spec/Components/WBP_AGS_ProjectErrorPanel.json",
                }
            }
        ),
        encoding="utf-8",
    )
    spec_path = tmp_path / "Content" / "UI" / "core_role_generate.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/UI/Generated/WBP_CoreRoleGenerate",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "UserWidget",
                                    "name": "ErrorPanel",
                                    "is_variable": True,
                                    "_core_role": "state_error",
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    post_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_mock, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "bridge"}
        )
    )

    posted_node = post_mock.await_args.args[2]["spec"]["root"]["children"][0]["children"][0]
    assert result["ok"] is True, result
    assert posted_node["class_path"] == "/Game/AGS/UI/Components/WBP_AGS_ProjectErrorPanel.WBP_AGS_ProjectErrorPanel_C"
    assert "core_role" not in posted_node
    assert "_core_role" not in posted_node


def test_accelbyte_ui_validate_rejects_agsui_entry_fallback_for_generated_project_widget(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False, compatible_list=True)
    spec_path = tmp_path / "Content" / "UI" / "agsui_entry_fallback.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_BadListPanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "ListView",
                                    "name": "LeaderboardList",
                                    "is_variable": True,
                                    "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow.WBP_AGS_PlayerRow_C",
                                    "selection_mode": "none",
                                    "horizontal_entry_spacing": 4,
                                    "vertical_entry_spacing": 4,
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate({"projectPath": str(tmp_path), "specPath": str(spec_path)})
    )

    assert result["ok"] is False
    assert any("project-owned entry widget" in error["message"] for error in result["errors"])


def test_accelbyte_ui_list_entry_candidates_marks_agsui_fallbacks_legacy(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False, compatible_list=True)
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_list_entry_candidates({"projectPath": str(tmp_path)})
    )

    assert result["ok"] is True, result
    assert result["generated_project_widgets_must_use_project_entries"] is True
    assert "will be rejected" in result["warning"]
    assert result["compatible_candidates"]


def test_accelbyte_ui_validate_auto_wires_registered_generated_tile_entry(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    source = tmp_path / "Source" / "Game" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "StoreItemCardEntry.h").write_text(
        "class GAME_API UStoreItemCardEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )
    entry_spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "Entries" / "WBP_AGS_ProjectStoreItemCard.json"
    entry_spec_path.parent.mkdir(parents=True, exist_ok=True)
    entry_spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard",
                "parent_class": "/Script/Game.UStoreItemCardEntry",
                "root": _generated_root(
                    [
                        {"type": "TextBlock", "name": "Tb_ItemName", "text": "Item"},
                        {"type": "TextBlock", "name": "Tb_PriceText", "text": "100"},
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    registry_path = tmp_path / "Saved" / "AccelByteUITools" / "generated_project_components.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "list_row": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard.WBP_AGS_ProjectStoreItemCard_C",
                    "spec_path": "Saved/Generated/Spec/Entries/WBP_AGS_ProjectStoreItemCard.json",
                }
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "store_catalogue.json"
    normalized_path = tmp_path / "Saved" / "Generated" / "Spec" / "store_catalogue.normalized.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_StoreCatalogue",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "TileView",
                            "name": "Tv_AllItems",
                            "is_variable": True,
                            "horizontal_entry_spacing": 4,
                            "vertical_entry_spacing": 4,
                        },
                        {
                            "type": "TileView",
                            "name": "Tv_FeaturedItems",
                            "is_variable": True,
                            "horizontal_entry_spacing": 4,
                            "vertical_entry_spacing": 4,
                        },
                        {
                            "type": "TileView",
                            "name": "Tv_DailyItems",
                            "is_variable": True,
                            "horizontal_entry_spacing": 4,
                            "vertical_entry_spacing": 4,
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert result["ok"] is True, result
    for tile_view in normalized["root"]["children"][0]["children"]:
        assert tile_view["entry_widget_class"] == "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard.WBP_AGS_ProjectStoreItemCard_C"
    assert [binding["cpp_type"] for binding in result["bindings"]] == ["UTileView", "UTileView", "UTileView"]


def test_accelbyte_ui_validate_rejects_generic_entry_for_store_tile_view(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    lists = tmp_path / "Content" / "ByteWars" / "UI" / "Components"
    lists.mkdir(parents=True, exist_ok=True)
    (lists / "W_AccelByteWarsWidgetEntry.uasset").write_text("", encoding="utf-8")
    source = tmp_path / "Source" / "AccelByteWars" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "AccelByteWarsWidgetEntry.h").write_text(
        "class ACCELBYTEWARS_API UAccelByteWarsWidgetEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "store_catalogue.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_Store",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "TileView",
                            "name": "Tv_AllItems",
                            "is_variable": True,
                            "entry_widget_class": "/Game/ByteWars/UI/Components/W_AccelByteWarsWidgetEntry.W_AccelByteWarsWidgetEntry_C",
                            "horizontal_entry_spacing": 4,
                            "vertical_entry_spacing": 4,
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate({"projectPath": str(tmp_path), "specPath": str(spec_path)})
    )

    assert result["ok"] is False
    assert any(error["code"] == "recipe_list_entry_required" for error in result["errors"])


def test_accelbyte_ui_generate_posts_normalized_collection_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    source = tmp_path / "Source" / "Game" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "StoreItemCardEntry.h").write_text(
        "class GAME_API UStoreItemCardEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )
    entry_spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "Entries" / "WBP_AGS_ProjectStoreItemCard.json"
    entry_spec_path.parent.mkdir(parents=True, exist_ok=True)
    entry_spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard",
                "parent_class": "/Script/Game.UStoreItemCardEntry",
                "root": _generated_root(
                    [
                        {"type": "TextBlock", "name": "Tb_ItemName", "text": "Item"},
                        {"type": "TextBlock", "name": "Tb_PriceText", "text": "100"},
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    registry_path = tmp_path / "Saved" / "AccelByteUITools" / "generated_project_components.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "store_item_card": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard.WBP_AGS_ProjectStoreItemCard_C",
                    "spec_path": "Saved/Generated/Spec/Entries/WBP_AGS_ProjectStoreItemCard.json",
                }
            }
        ),
        encoding="utf-8",
    )
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "store_catalogue.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_Store",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "TileView",
                            "name": "Tv_AllItems",
                            "is_variable": True,
                            "horizontal_entry_spacing": 4,
                            "vertical_entry_spacing": 4,
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)
    post_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", post_mock, raising=False)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_generate(
            {"projectPath": str(tmp_path), "specPath": str(spec_path), "mode": "bridge"}
        )
    )

    posted_tile = post_mock.await_args.args[2]["spec"]["root"]["children"][0]["children"][0]
    assert result["ok"] is True, result
    assert posted_tile["entry_widget_class"] == "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard.WBP_AGS_ProjectStoreItemCard_C"
    assert result["expected_collection_entries"] == [
        {
            "widget_name": "Tv_AllItems",
            "expected_entry_widget_class": "/Game/AGS/UI/Components/WBP_AGS_ProjectStoreItemCard.WBP_AGS_ProjectStoreItemCard_C",
        }
    ]


def test_accelbyte_ui_validate_auto_wires_recipe_matching_leaderboard_entry(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    source = tmp_path / "Source" / "Game" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "GenericPlayerEntry.h").write_text(
        "class GAME_API UGenericPlayerEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )
    (source / "LeaderboardEntry.h").write_text(
        "class GAME_API ULeaderboardEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )
    entries_dir = tmp_path / "Saved" / "Generated" / "Spec" / "Entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    generic_spec_path = entries_dir / "WBP_AGS_ProjectPlayerEntry.json"
    generic_spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectPlayerEntry",
                "parent_class": "/Script/Game.UGenericPlayerEntry",
                "root": _generated_root(
                    [
                        {"type": "TextBlock", "name": "Tb_PlayerName", "text": "Player"},
                        {"type": "TextBlock", "name": "Tb_Status", "text": "Online"},
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    leaderboard_spec_path = entries_dir / "WBP_AGS_ProjectLeaderboardEntry.json"
    leaderboard_spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectLeaderboardEntry",
                "parent_class": "/Script/Game.ULeaderboardEntry",
                "root": _generated_root(
                    [
                        {"type": "TextBlock", "name": "Tb_RankText", "text": "#1"},
                        {"type": "TextBlock", "name": "Tb_PlayerName", "text": "Player"},
                        {"type": "TextBlock", "name": "Tb_ScoreText", "text": "1000"},
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    registry_path = tmp_path / "Saved" / "AccelByteUITools" / "generated_project_components.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "list_row": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectPlayerEntry",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectPlayerEntry.WBP_AGS_ProjectPlayerEntry_C",
                    "spec_path": "Saved/Generated/Spec/Entries/WBP_AGS_ProjectPlayerEntry.json",
                },
                "leaderboard_entry": {
                    "asset_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectLeaderboardEntry",
                    "class_path": "/Game/AGS/UI/Components/WBP_AGS_ProjectLeaderboardEntry.WBP_AGS_ProjectLeaderboardEntry_C",
                    "spec_path": "Saved/Generated/Spec/Entries/WBP_AGS_ProjectLeaderboardEntry.json",
                },
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "leaderboard.json"
    normalized_path = tmp_path / "Saved" / "Generated" / "Spec" / "leaderboard.normalized.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_LeaderboardPanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "ListView",
                            "name": "LeaderboardRows",
                            "is_variable": True,
                            "horizontal_entry_spacing": 4,
                            "vertical_entry_spacing": 4,
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    list_view = normalized["root"]["children"][0]["children"][0]
    assert result["ok"] is True, result
    assert (
        list_view["entry_widget_class"]
        == "/Game/AGS/UI/Components/WBP_AGS_ProjectLeaderboardEntry.WBP_AGS_ProjectLeaderboardEntry_C"
    )


def test_accelbyte_ui_validate_rejects_generated_entry_without_list_entry_parent(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    source = tmp_path / "Source" / "Game" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "StoreItemCardEntry.h").write_text(
        "class GAME_API UStoreItemCardEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)
    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "bad_store_item_card.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_StoreItemCard",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root([{"type": "TextBlock", "name": "Tb_ItemName", "text": "Item"}]),
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate({"projectPath": str(tmp_path), "specPath": str(spec_path)})
    )

    assert result["ok"] is False
    assert any(error["code"] == "collection_entry_parent_required" for error in result["errors"])


def test_accelbyte_ui_validate_normalizes_generated_entry_subfolder_to_project_style_umg(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=True)
    source = tmp_path / "Source" / "AccelByteWars" / "UI"
    source.mkdir(parents=True, exist_ok=True)
    (source / "AccelByteWarsWidgetEntry.h").write_text(
        "class ACCELBYTEWARS_API UAccelByteWarsWidgetEntry : public UUserWidget, public IUserObjectListEntry {};",
        encoding="utf-8",
    )

    spec_path = tmp_path / "Saved" / "Generated" / "Spec" / "Entries" / "leaderboard_entry.json"
    normalized_path = tmp_path / "Saved" / "Generated" / "Spec" / "Entries" / "leaderboard_entry.normalized.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardEntry",
                "parent_class": "/Script/AccelByteWars.AccelByteWarsWidgetEntry",
                "ui_mode": "common_ui",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "style": {"background_color": [0.0, 0.0, 0.0, 0.1]},
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [16, 10, 16, 10],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "HorizontalBox",
                                    "name": "RowContent",
                                    "slot": {"h_align": "fill", "v_align": "center"},
                                    "children": [
                                        {
                                            "type": "TextBlock",
                                            "name": "Tb_Rank",
                                            "is_variable": True,
                                            "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                                        },
                                        {
                                            "type": "TextBlock",
                                            "name": "Tb_PlayerName",
                                            "is_variable": True,
                                            "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                                        },
                                        {
                                            "type": "TextBlock",
                                            "name": "Tb_Score",
                                            "is_variable": True,
                                            "text_style_class": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C",
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate(
            {
                "projectPath": str(tmp_path),
                "specPath": str(spec_path),
                "writeNormalizedSpecPath": str(normalized_path),
            }
        )
    )

    assert result["ok"] is True, result
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    content = normalized["root"]["children"][0]
    assert normalized["ui_mode"] == "umg"
    assert normalized["root"]["style"]["background_color"] == [0.0, 0.0, 0.0, 0.1]
    assert content["padding"] == [16, 10, 16, 10]


def test_accelbyte_ui_validate_rejects_complex_catalogue_without_project_prerequisites(
    tmp_path: Path, accelbyte_ui_tools
):
    _write_style_project(tmp_path, common_ui=False)
    spec_path = tmp_path / "Content" / "UI" / "store_catalogue.json"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_StoreCatalogue",
                "parent_class": "/Script/UMG.UserWidget",
                "root": _generated_root(
                    [
                        {
                            "type": "WidgetSwitcher",
                            "name": "StateSwitcher",
                            "is_variable": True,
                            "children": [
                                {"type": "AGSStatusMessage", "name": "IdleState", "is_variable": True},
                                {"type": "AGSLoadingIndicator", "name": "LoadingState", "is_variable": True},
                                {
                                    "type": "VerticalBox",
                                    "name": "SuccessState",
                                    "is_variable": True,
                                    "children": [
                                        {"type": "AGSSecondaryButton", "name": "Btn_TabWeapons", "is_variable": True},
                                        {
                                            "type": "TileView",
                                            "name": "StoreItemsTileView",
                                            "is_variable": True,
                                            "entry_widget_class": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard.WBP_AGS_StoreItemCard_C",
                                            "horizontal_entry_spacing": 4,
                                            "vertical_entry_spacing": 4,
                                        },
                                    ],
                                },
                                {"type": "AGSEmptyState", "name": "EmptyState", "is_variable": True},
                                {"type": "AGSErrorState", "name": "ErrorState", "is_variable": True},
                            ],
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    _approve_style_context(tmp_path)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_validate({"projectPath": str(tmp_path), "specPath": str(spec_path)})
    )
    codes = {error["code"] for error in result["errors"]}

    assert result["ok"] is False
    assert "project_tab_button_required" in codes
    assert "project_list_entry_required" in codes
    assert "no_compatible_project_list_entry" in codes
    assert "project_core_widget_required" in codes


def test_accelbyte_ui_patch_posts_patch_to_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    patch_path = tmp_path / "patch.json"
    patch_payload = {
        "asset_path": "/Game/ByteWars/UI/Generated/WBP_Test",
        "operations": [{"op": "set_text", "target": "Title", "text": "Updated"}],
    }
    patch_path.write_text(json.dumps(patch_payload), encoding="utf-8")

    post_mock = AsyncMock(return_value=FakeResponse({"ok": True, "patched": True}))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_patch(
            {
                "projectPath": str(tmp_path),
                "patchPath": str(patch_path),
                "bridgeUrl": "http://127.0.0.1:9999",
            }
        )
    )

    assert result == {"ok": True, "patched": True}
    post_mock.assert_awaited_once_with(
        "http://127.0.0.1:9999/accelbyte-ui-tools/patch",
        json=patch_payload,
    )


def test_accelbyte_ui_patch_posts_set_widget_properties_patch_to_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    patch_path = tmp_path / "patch_panel_background.json"
    patch_payload = {
        "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_LeaderboardPanel",
        "op": "set_widget_properties",
        "widget_name": "PanelBackground",
        "properties": {"style": {"background_color": [0, 0, 0, 0.1]}},
    }
    patch_path.write_text(json.dumps(patch_payload), encoding="utf-8")

    post_mock = AsyncMock(return_value=FakeResponse({"ok": True, "updated_widget_names": ["PanelBackground"]}))
    client_mock = AsyncMock()
    client_mock.__aenter__.return_value.post = post_mock
    client_mock.__aexit__.return_value = None
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout: client_mock)

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_patch(
            {
                "projectPath": str(tmp_path),
                "patchPath": str(patch_path),
                "bridgeUrl": "http://127.0.0.1:9999",
            }
        )
    )

    assert result == {"ok": True, "updated_widget_names": ["PanelBackground"]}
    post_mock.assert_awaited_once_with(
        "http://127.0.0.1:9999/accelbyte-ui-tools/patch",
        json=patch_payload,
    )


def test_accelbyte_ui_patch_rejects_invalid_set_widget_properties_patch(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    patch_path = tmp_path / "bad_patch.json"
    patch_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_LeaderboardPanel",
                "op": "set_widget_properties",
                "widget_name": "PanelBackground",
            }
        ),
        encoding="utf-8",
    )

    result = asyncio.run(
        accelbyte_ui_tools.accelbyte_ui_patch(
            {"projectPath": str(tmp_path), "patchPath": str(patch_path)}
        )
    )

    assert result["ok"] is False
    assert result["errors"][0]["code"] == "invalid_patch"
    assert "properties" in result["errors"][0]["message"]


def test_accelbyte_ui_patch_rejects_patch_outside_project(
    tmp_path: Path, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    outside = tmp_path.parent / "outside_widget_patch.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="outside project root"):
        asyncio.run(
            accelbyte_ui_tools.accelbyte_ui_patch(
                {"projectPath": str(tmp_path), "patchPath": str(outside)}
            )
        )


def test_accelbyte_ui_patch_auto_does_not_fall_back_on_bridge_protocol_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, accelbyte_ui_tools
):
    (tmp_path / "AccelByteWars.uproject").write_text("{}", encoding="utf-8")
    _write_project_cli(tmp_path)
    patch_path = tmp_path / "patch.json"
    patch_path.write_text(
        json.dumps(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_Test",
                "operations": [{"op": "set_text", "target": "Title", "text": "Updated"}],
            }
        ),
        encoding="utf-8",
    )

    async def fail_bridge(*args, **kwargs):
        raise ValueError("Bridge response must be a JSON object")

    monkeypatch.setattr(accelbyte_ui_tools, "_post_bridge", fail_bridge, raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: pytest.fail("commandlet fallback should not run"),
    )

    with pytest.raises(ValueError, match="Bridge response"):
        asyncio.run(
            accelbyte_ui_tools.accelbyte_ui_patch(
                {"projectPath": str(tmp_path), "patchPath": str(patch_path), "mode": "auto"}
            )
        )
