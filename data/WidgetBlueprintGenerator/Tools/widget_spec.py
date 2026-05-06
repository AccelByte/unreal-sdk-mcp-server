from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any


ALLOWED_ASSET_PREFIXES = ("/Game/ByteWars/UI/Generated/",)
SUPPORTED_CONTAINERS = {"CanvasPanel", "Overlay", "VerticalBox", "HorizontalBox", "SizeBox", "Border"}
SUPPORTED_LEAVES = {"TextBlock", "Button", "EditableTextBox", "Image", "Spacer"}
SUPPORTED_PROJECT_WIDGETS = {"AccelByteWarsButtonBase"}
SUPPORTED_WIDGETS = SUPPORTED_CONTAINERS | SUPPORTED_LEAVES | SUPPORTED_PROJECT_WIDGETS
VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class WidgetNode:
    type: str
    name: str
    is_variable: bool = False
    slot: dict[str, Any] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)
    text: str | None = None
    hint_text: str | None = None
    is_password: bool = False
    brush: str | None = None
    visibility: str | None = None
    children: tuple["WidgetNode", ...] = ()

    def walk(self) -> list["WidgetNode"]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.walk())
        return nodes


@dataclass(frozen=True)
class WidgetSpec:
    asset_path: str
    parent_class: str
    root: WidgetNode

    def widget_count(self) -> int:
        return len(self.root.walk())

    def variable_widget_names(self) -> list[str]:
        return [node.name for node in self.root.walk() if node.is_variable]


def load_spec_file(path: str | Path) -> WidgetSpec:
    with Path(path).open("r", encoding="utf-8") as spec_file:
        return load_spec_from_dict(json.load(spec_file))


def load_spec_from_dict(data: dict[str, Any]) -> WidgetSpec:
    if not isinstance(data, dict):
        raise ValidationError("schema_error", "Spec root must be a JSON object.")

    asset_path = _required_string(data, "asset_path")
    parent_class = _required_string(data, "parent_class")
    root_data = data.get("root")

    if not asset_path.startswith(ALLOWED_ASSET_PREFIXES):
        raise ValidationError(
            "asset_path_denied",
            f"Asset path must start with one of: {', '.join(ALLOWED_ASSET_PREFIXES)}",
        )
    if not parent_class.startswith("/Script/"):
        raise ValidationError("schema_error", "parent_class must start with /Script/.")
    if not isinstance(root_data, dict):
        raise ValidationError("schema_error", "root must be an object.")

    return WidgetSpec(asset_path=asset_path, parent_class=parent_class, root=_parse_node(root_data, "root"))


def _parse_node(data: dict[str, Any], path: str) -> WidgetNode:
    widget_type = _required_string(data, "type", path)
    name = _required_string(data, "name", path)

    if widget_type not in SUPPORTED_WIDGETS:
        raise ValidationError("unsupported_widget", f"{path}.type '{widget_type}' is not supported.")
    if not VALID_NAME.match(name):
        raise ValidationError("schema_error", f"{path}.name '{name}' is not a valid Unreal object name.")

    raw_children = data.get("children", [])
    if raw_children is None:
        raw_children = []
    if not isinstance(raw_children, list):
        raise ValidationError("schema_error", f"{path}.children must be an array.")

    children = tuple(_parse_node(child, f"{path}.children[{index}]") for index, child in enumerate(raw_children))
    if widget_type in SUPPORTED_LEAVES and children:
        raise ValidationError("schema_error", f"{path}.children is not allowed for leaf widget '{widget_type}'.")

    return WidgetNode(
        type=widget_type,
        name=name,
        is_variable=bool(data.get("is_variable", False)),
        slot=_optional_object(data, "slot", path),
        style=_optional_object(data, "style", path),
        text=_optional_string(data, "text", path),
        hint_text=_optional_string(data, "hint_text", path),
        is_password=_optional_bool(data, "is_password", path),
        brush=_optional_string(data, "brush", path),
        visibility=_optional_string(data, "visibility", path),
        children=children,
    )


def _required_string(data: dict[str, Any], key: str, path: str = "spec") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValidationError("schema_error", f"{path}.{key} must be a non-empty string.")
    return value


def _optional_string(data: dict[str, Any], key: str, path: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("schema_error", f"{path}.{key} must be a string.")
    return value


def _optional_object(data: dict[str, Any], key: str, path: str) -> dict[str, Any]:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("schema_error", f"{path}.{key} must be an object.")
    return value


def _optional_bool(data: dict[str, Any], key: str, path: str) -> bool:
    value = data.get(key, False)
    if not isinstance(value, bool):
        raise ValidationError("schema_error", f"{path}.{key} must be a boolean.")
    return value
