from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

try:
    from .theme_tokens import load_theme_tokens
except ImportError:
    from theme_tokens import load_theme_tokens


CONTROL_STYLE_KEYS = {
    "background_color",
    "border_color",
    "border_width",
    "color",
    "corner_radius",
    "hint_color",
    "hover_color",
    "pressed_color",
}
CONTROL_PADDING_TYPES = {"Button", "EditableTextBox"}
COLLECTION_TYPES = {"ListView", "TileView"}
PROJECT_PANEL_BACKGROUND_COLOR = [0.0, 0.0, 0.0, 0.1]
LEGACY_AGS_PANEL_BACKGROUND_COLOR = [1.0, 1.0, 1.0, 1.0]
CORE_CONTROL_PADDING_TYPES = {
    "AGSBaseButton",
    "AGSButton",
    "AGSSecondaryButton",
    "AGSDangerButton",
    "AGSIconButton",
    "AGSTextInput",
    "AGSPasswordInput",
    "AGSSearchInput",
}
FLOW_CHILD_SLOT_PADDING = {
    "VerticalBox": [0, 0, 0, 8],
    "HorizontalBox": [0, 0, 8, 0],
    "WrapBox": [0, 0, 8, 8],
}


def normalize_theme(
    spec: dict[str, Any],
    *,
    tokens: dict[str, Any] | None = None,
    generated_ags_only: bool = True,
    style_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a copy of a widget spec with default AGS theme tokens applied."""

    normalized = deepcopy(spec)
    confidence = "high" if style_context is None else str(style_context.get("confidence", "low"))
    use_project_style = _resolve_project_style(
        str(normalized.get("style_mode", "auto")),
        confidence,
    )
    if generated_ags_only and not _is_generated_ags_spec(normalized):
        if _is_project_generated_spec(normalized):
            _normalize_project_panel_background(normalized)
        return normalized
    if generated_ags_only and _is_collection_entry_spec(normalized):
        if use_project_style:
            _normalize_project_panel_background(normalized)
        return normalized

    theme = tokens or load_theme_tokens()
    root = normalized.get("root")
    if isinstance(root, dict):
        _normalize_node(root, theme, use_project_style=use_project_style)
    return normalized


def normalize_theme_file(
    spec_path: str | Path,
    *,
    output_path: str | Path | None = None,
    tokens: dict[str, Any] | None = None,
    generated_ags_only: bool = True,
    style_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(spec_path)
    normalized = normalize_theme(
        json.loads(path.read_text(encoding="utf-8")),
        tokens=tokens,
        generated_ags_only=generated_ags_only,
        style_context=style_context,
    )
    if output_path is not None:
        write_normalized_spec(normalized, output_path)
    return normalized


def write_normalized_spec(spec: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return path


def _is_generated_ags_spec(spec: dict[str, Any]) -> bool:
    return str(spec.get("asset_path", "")).startswith("/Game/AGS/UI/Generated/")


def _is_project_generated_spec(spec: dict[str, Any]) -> bool:
    asset_path = str(spec.get("asset_path", ""))
    return asset_path.startswith("/Game/") and "/UI/Generated/" in asset_path


def _is_collection_entry_spec(spec: dict[str, Any]) -> bool:
    asset_name = str(spec.get("asset_path", "")).rsplit("/", 1)[-1]
    compact = re.sub(r"[^a-z0-9]", "", asset_name.casefold())
    return (
        compact.endswith(("entry", "row", "card", "tileitem", "listitem"))
        or any(keyword in compact for keyword in ("itemcard", "entrywidget", "rowwidget", "cardwidget"))
    )


def _normalize_project_panel_background(spec: dict[str, Any]) -> None:
    root = spec.get("root")
    if not isinstance(root, dict):
        return
    if root.get("type") != "Border" or root.get("name") != "PanelBackground":
        return
    style = _style(root)
    if "background_color" not in style:
        style["background_color"] = deepcopy(PROJECT_PANEL_BACKGROUND_COLOR)


def _resolve_project_style(style_mode: str, confidence: str) -> bool:
    if style_mode == "agsui":
        return False
    if style_mode == "project":
        return True
    return confidence in {"medium", "high"}


def _normalize_node(
    node: dict[str, Any],
    tokens: dict[str, Any],
    path: str = "root",
    *,
    use_project_style: bool = True,
) -> None:
    widget_type = str(node.get("type", ""))
    class_path = str(node.get("class_path", ""))
    name = str(node.get("name", ""))

    if widget_type == "TextBlock":
        style = _style(node)
        style["color"] = deepcopy(tokens["colors"]["text"]["primary"])
    elif widget_type == "EditableTextBox":
        node["style"] = _merge_control_style(tokens["presets"]["input"], node.get("style"))
        node.setdefault("padding", deepcopy(tokens["spacing"]["controlPadding"]))
    elif widget_type == "Button":
        preset_name = _button_preset_name(widget_type, name, class_path)
        node["style"] = _merge_control_style(tokens["presets"][preset_name], node.get("style"))
        node.setdefault("padding", deepcopy(tokens["spacing"]["controlPadding"]))
    elif widget_type == "Border":
        preset_name = _border_preset_name(name)
        existing_background_color = None
        has_explicit_background = False
        existing_style = node.get("style")
        is_root_panel_background = path == "root" and name == "PanelBackground"
        if is_root_panel_background and isinstance(existing_style, dict):
            existing_background_color = existing_style.get("background_color")
            has_explicit_background = "background_color" in existing_style
        node["style"] = _merge_control_style(tokens["presets"][preset_name], node.get("style"))
        if is_root_panel_background:
            if use_project_style:
                if has_explicit_background and existing_background_color is not None:
                    node["style"]["background_color"] = deepcopy(existing_background_color)
                else:
                    node["style"]["background_color"] = deepcopy(PROJECT_PANEL_BACKGROUND_COLOR)
            elif existing_background_color is not None:
                node["style"]["background_color"] = deepcopy(existing_background_color)
        if preset_name == "panel":
            node.setdefault("padding", deepcopy(tokens["spacing"]["panelPadding"]))
        elif preset_name == "card":
            node.setdefault("padding", deepcopy(tokens["spacing"]["cardPadding"]))
    elif widget_type in CORE_CONTROL_PADDING_TYPES:
        node.setdefault("padding", deepcopy(tokens["spacing"]["controlPadding"]))

    if widget_type in COLLECTION_TYPES:
        node.setdefault("horizontal_entry_spacing", tokens["spacing"]["entrySpacing"])
        node.setdefault("vertical_entry_spacing", tokens["spacing"]["entrySpacing"])

    child_slot_padding = FLOW_CHILD_SLOT_PADDING.get(widget_type)
    for index, child in enumerate(node.get("children", []) or []):
        if isinstance(child, dict):
            if child_slot_padding is not None:
                slot = child.get("slot")
                if not isinstance(slot, dict):
                    slot = {}
                    child["slot"] = slot
                slot.setdefault("padding", deepcopy(child_slot_padding))
            _normalize_node(child, tokens, f"{path}.children[{index}]", use_project_style=use_project_style)


def _style(node: dict[str, Any]) -> dict[str, Any]:
    style = node.get("style")
    if not isinstance(style, dict):
        style = {}
        node["style"] = style
    return style


def _merge_control_style(preset: dict[str, Any], existing: Any) -> dict[str, Any]:
    style = deepcopy(preset)
    if isinstance(existing, dict):
        for key, value in existing.items():
            if key not in CONTROL_STYLE_KEYS:
                style[key] = deepcopy(value)
    return style


def _is_missing_or_legacy_panel_background(value: Any) -> bool:
    return value is None or _same_color(value, LEGACY_AGS_PANEL_BACKGROUND_COLOR)


def _same_color(actual: Any, expected: list[float]) -> bool:
    if not isinstance(actual, list) or len(actual) != len(expected):
        return False
    for actual_value, expected_value in zip(actual, expected):
        if not isinstance(actual_value, (int, float)) or isinstance(actual_value, bool):
            return False
        if abs(float(actual_value) - expected_value) > 0.000001:
            return False
    return True


def _button_preset_name(widget_type: str, name: str, class_path: str) -> str:
    combined = f"{widget_type} {name} {class_path}".casefold()
    if "danger" in combined or "delete" in combined or "remove" in combined:
        return "dangerButton"
    if "secondary" in combined or "cancel" in combined or "tab" in combined:
        return "secondaryButton"
    return "primaryButton"


def _border_preset_name(name: str) -> str:
    lowered = name.casefold()
    if "card" in lowered or "item" in lowered or "row" in lowered:
        return "card"
    return "panel"
