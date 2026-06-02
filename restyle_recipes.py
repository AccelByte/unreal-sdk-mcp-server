"""
Prepend a full-stretch Border background to every recipe's RootCanvas.

Strategy: keep all existing CanvasPanel children (state widgets with anchor slots)
intact. Just add a Border as the FIRST child so it renders as the back layer.
In UE5 CanvasPanel, children render in order: first = back, last = front.

The Border uses the AccelByte light theme root background while preserving the
responsive anchor layout we built earlier.

For ags_tabbed_social_panel.json (single VBox child), same approach: Border at
back, VBox renders on top.
"""

import json
from pathlib import Path
import sys

RECIPE_DIR = Path(__file__).parent / "data/WidgetBlueprintGenerator/Tools/specs/recipes"
TOOLS_DIR = Path(__file__).parent / "data/WidgetBlueprintGenerator/Tools"
sys.path.insert(0, str(TOOLS_DIR))

from theme_tokens import color, load_theme_tokens, radius, spacing

TOKENS = load_theme_tokens()

BG_PRIMARY = color(TOKENS, "bg.primary")
BG_CARD = color(TOKENS, "bg.card")
BG_SUBTLE = color(TOKENS, "bg.subtle")
TEXT_PRIMARY = color(TOKENS, "text.primary")
TEXT_MUTED = color(TOKENS, "text.muted")
BORDER_SUBTLE = color(TOKENS, "border.subtle")
RADIUS_SURFACE = radius(TOKENS, "surface")
ENTRY_SPACING = spacing(TOKENS, "entrySpacing")

SKIP = set()  # all recipes get the treatment

BACKGROUND_BORDER = {
    "type": "Border",
    "name": "PanelBackground",
    "is_variable": False,
    "padding": [0, 0, 0, 0],
    "style": {"background_color": BG_PRIMARY},
    "slot": {
        "anchors": [0, 0, 1, 1],
        "offsets": [0, 0, 0, 0],
        "alignment": [0, 0]
    }
}

COLOR_MAP = {
    (0.08, 0.08, 0.10, 1.0): BG_PRIMARY,
    (0.08, 0.08, 0.1, 1.0): BG_PRIMARY,
    (0.13, 0.13, 0.16, 1.0): BG_CARD,
    (0.11, 0.11, 0.14, 1.0): BG_SUBTLE,
    (0.92, 0.92, 0.92, 1.0): TEXT_PRIMARY,
    (0.65, 0.65, 0.68, 1.0): TEXT_MUTED,
}


def already_has_background(children):
    return any(c.get("name") == "PanelBackground" for c in children)


def normalize_color(value):
    if not isinstance(value, list) or len(value) < 4:
        return value
    key = tuple(round(float(channel), 2) for channel in value[:4])
    return COLOR_MAP.get(key, value)


def restyle_node(node):
    if not isinstance(node, dict):
        return
    style = node.get("style")
    if isinstance(style, dict):
        for key in ("background_color", "color", "hint_color", "border_color", "hover_color", "pressed_color"):
            if key in style:
                style[key] = normalize_color(style[key])
        if node.get("type") == "Border":
            style.setdefault("corner_radius", RADIUS_SURFACE)
            style.setdefault("border_color", BORDER_SUBTLE)
            style.setdefault("border_width", 1)
    if node.get("type") in {"ListView", "TileView"}:
        node.setdefault("horizontal_entry_spacing", ENTRY_SPACING)
        node.setdefault("vertical_entry_spacing", ENTRY_SPACING)
    if node.get("entry_widget_class") == "/WidgetBlueprintGenerator/AGSUI/Lists/WBP_AGS_FriendRow.WBP_AGS_FriendRow_C":
        node["entry_widget_class"] = "/WidgetBlueprintGenerator/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C"
    for child in node.get("children", []):
        restyle_node(child)


def convert(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    data["parent_class"] = "/Script/WidgetBlueprintGenerator.AGSPanelBase"
    root = data["root"]
    restyle_node(root)
    if root.get("type") != "CanvasPanel":
        print(f"  restyled (no CanvasPanel root): {path.name}")
        path.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return
    children = root.get("children", [])
    if already_has_background(children):
        print(f"  restyled (already has PanelBackground): {path.name}")
        path.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return
    # Prepend the background Border
    root["children"] = [BACKGROUND_BORDER] + children
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    print(f"  prepended Border background: {path.name}")


def main():
    converted = 0
    for path in sorted(RECIPE_DIR.glob("*.json")):
        if path.name in SKIP:
            print(f"  skipped: {path.name}")
            continue
        convert(path)
        converted += 1
    print(f"\nProcessed {converted} recipe files.")


if __name__ == "__main__":
    main()
