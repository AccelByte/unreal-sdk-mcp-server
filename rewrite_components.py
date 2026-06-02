"""Rewrite all AGSUI widget component specs with the AccelByte light theme."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).parent / "data/AccelByteUITools/Tools/specs/components/agsui"
TOOLS_DIR = Path(__file__).parent / "data/AccelByteUITools/Tools"
sys.path.insert(0, str(TOOLS_DIR))

from theme_tokens import color, load_theme_tokens, preset, radius, spacing

TOKENS = load_theme_tokens()

# Tokens
BG_PRIMARY = color(TOKENS, "bg.primary")
BG_CARD = color(TOKENS, "bg.card")
BG_SUBTLE = color(TOKENS, "bg.subtle")
BG_INPUT = color(TOKENS, "bg.input")
BG_BUTTON = color(TOKENS, "bg.card")
BG_BUTTON_ACCENT = color(TOKENS, "primary.base")
BG_BUTTON_ACCENT_HOVER = color(TOKENS, "primary.hover")
BG_BUTTON_ACCENT_PRESSED = color(TOKENS, "primary.pressed")
BG_BUTTON_DANGER = color(TOKENS, "danger.base")
BG_BUTTON_DANGER_HOVER = color(TOKENS, "danger.hover")
BG_BUTTON_DANGER_PRESSED = color(TOKENS, "danger.pressed")
BG_ROW = color(TOKENS, "bg.item")
TEXT_PRIMARY = color(TOKENS, "text.primary")
TEXT_MUTED = color(TOKENS, "text.muted")
TEXT_ON_PRIMARY = color(TOKENS, "text.onPrimary")
TEXT_ACTION = color(TOKENS, "text.action")
TEXT_DANGER = color(TOKENS, "text.danger")
TEXT_SUCCESS = color(TOKENS, "text.success")
DIVIDER = color(TOKENS, "divider")
DIVIDER_VISIBLE = DIVIDER
BORDER_SUBTLE = color(TOKENS, "border.subtle")
BORDER_CONTROL = color(TOKENS, "border.control")
BORDER_ACTION = color(TOKENS, "border.action")
TEXT_INPUT_FOREGROUND = color(TOKENS, "text.input")
TEXT_INPUT_HINT = color(TOKENS, "text.hint")
RADIUS_CONTROL = radius(TOKENS, "control")
RADIUS_SURFACE = radius(TOKENS, "surface")
RADIUS_PILL = radius(TOKENS, "pill")

PLACEHOLDER_BRUSH = "/AccelByteUITools/AGSUI/Brushes/T_AGS_AccelByteLogo"

CENTER_SLOT = {"h_align": "center", "v_align": "center"}

PAD_TIGHT = spacing(TOKENS, "tightPadding")
PAD_CONTROL = spacing(TOKENS, "controlPadding")
PAD_ROW = spacing(TOKENS, "rowPadding")
PAD_CARD = spacing(TOKENS, "cardPadding")
PAD_PANEL = spacing(TOKENS, "panelPadding")
ENTRY_SPACING = spacing(TOKENS, "entrySpacing")


def text(name, content, color=None, variable=True):
    node = {"type": "TextBlock", "name": name, "is_variable": variable, "text": content,
            "style": {"color": color or TEXT_PRIMARY}}
    return node


def muted_text(name, content, variable=True):
    return text(name, content, TEXT_MUTED, variable)


def style(bg=None, color=None, radius=None, border_color=None, border_width=None,
          hover_color=None, pressed_color=None, hint_color=None):
    data = {}
    if bg is not None:
        data["background_color"] = bg
    if color is not None:
        data["color"] = color
    if radius is not None:
        data["corner_radius"] = radius
    if border_color is not None:
        data["border_color"] = border_color
    if border_width is not None:
        data["border_width"] = border_width
    if hover_color is not None:
        data["hover_color"] = hover_color
    if pressed_color is not None:
        data["pressed_color"] = pressed_color
    if hint_color is not None:
        data["hint_color"] = hint_color
    return data


def border(name, bg, children, padding=None, variable=False, slot=None, radius=RADIUS_SURFACE,
           border_color=BORDER_SUBTLE, border_width=1):
    node = {"type": "Border", "name": name, "is_variable": variable,
            "style": style(bg=bg, radius=radius, border_color=border_color, border_width=border_width),
            "children": children}
    if padding is not None:
        node["padding"] = padding
    if slot is not None:
        node["slot"] = slot
    return node


def vbox(name, children, variable=False, slot=None):
    node = {"type": "VerticalBox", "name": name, "is_variable": variable, "children": children}
    if slot is not None:
        node["slot"] = slot
    return node


def hbox(name, children, variable=False, slot=None):
    node = {"type": "HorizontalBox", "name": name, "is_variable": variable, "children": children}
    if slot is not None:
        node["slot"] = slot
    return node


def overlay(name, children, variable=False, slot=None):
    node = {"type": "Overlay", "name": name, "is_variable": variable, "children": children}
    if slot is not None:
        node["slot"] = slot
    return node


def sizebox(name, width, height, children, variable=False, slot=None):
    node = {"type": "SizeBox", "name": name, "is_variable": variable, "children": children}
    if width is not None:
        node["width"] = width
    if height is not None:
        node["height"] = height
    if slot is not None:
        node["slot"] = slot
    return node


def listview(name, entry_widget_class, variable=True, slot=None, preview_entries=None, selection_mode="none"):
    node = {
        "type": "ListView",
        "name": name,
        "is_variable": variable,
        "entry_widget_class": entry_widget_class,
        "selection_mode": selection_mode,
        "horizontal_entry_spacing": ENTRY_SPACING,
        "vertical_entry_spacing": ENTRY_SPACING,
        "preview_entries": preview_entries or [{"name": "Item 1"}, {"name": "Item 2"}],
    }
    if slot is not None:
        node["slot"] = slot
    return node


def grid(name, children, variable=True, slot=None):
    node = {"type": "UniformGridPanel", "name": name, "is_variable": variable, "children": children}
    if slot is not None:
        node["slot"] = slot
    return node


BUTTON_ASSET_BY_BG = {
    tuple(BG_BUTTON_ACCENT): "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
    tuple(BG_BUTTON):        "/AccelByteUITools/AGSUI/Core/WBP_AGS_SecondaryButton.WBP_AGS_SecondaryButton_C",
    tuple(BG_BUTTON_DANGER): "/AccelByteUITools/AGSUI/Core/WBP_AGS_DangerButton.WBP_AGS_DangerButton_C",
}

INPUT_ASSET_BY_KIND = {
    "text":     "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput.WBP_AGS_TextInput_C",
    "password": "/AccelByteUITools/AGSUI/Core/WBP_AGS_PasswordInput.WBP_AGS_PasswordInput_C",
    "search":   "/AccelByteUITools/AGSUI/Core/WBP_AGS_SearchInput.WBP_AGS_SearchInput_C",
}


def button(name, label_text, bg, variable=True, slot=None):
    """Class_path reference to the appropriate core button asset.

    `label_text` flows to the instance's UAGSButtonBase::DefaultLabel UPROPERTY,
    which NativePreConstruct pushes into the inner ButtonText widget at both
    edit-time preview and runtime construction."""
    class_path = BUTTON_ASSET_BY_BG[tuple(bg)]
    node = {
        "type": "AGSButton",
        "name": name,
        "class_path": class_path,
        "is_variable": variable,
        "text": label_text,
    }
    if slot is not None:
        node["slot"] = slot
    return node


def input_field(name, kind="text", hint_text=None, variable=True, slot=None):
    """Class_path reference to a core input asset (text / password / search).

    `hint_text` flows to the instance's UAGSTextInputBase::DefaultHintText
    UPROPERTY, propagated to the inner ValueInput at PreConstruct."""
    class_path = INPUT_ASSET_BY_KIND[kind]
    node = {
        "type": "AGSTextInput",
        "name": name,
        "class_path": class_path,
        "is_variable": variable,
    }
    if hint_text is not None:
        node["hint_text"] = hint_text
    if slot is not None:
        node["slot"] = slot
    return node


def button_asset_root(label_text, bg):
    """Root widget for a standalone button asset (WBP_AGS_BaseButton et al.).

    Uses the new UAGSButtonBase bindings: an InteractiveButton (UButton) and a
    ButtonText (UTextBlock) inside it. The asset's parent class C++ subscribes
    to InteractiveButton->OnClicked and exposes it via the OnClicked event.
    """
    is_primary = bg == BG_BUTTON_ACCENT
    is_danger = bg == BG_BUTTON_DANGER
    text_color = TEXT_ON_PRIMARY if (is_primary or is_danger) else TEXT_ACTION
    border_color = BORDER_ACTION if not is_danger else BG_BUTTON_DANGER
    hover_color = BG_BUTTON_ACCENT_HOVER if is_primary else ([0.94, 0.97, 1.0, 1.0] if not is_danger else BG_BUTTON_DANGER_HOVER)
    pressed_color = BG_BUTTON_ACCENT_PRESSED if is_primary else ([0.89, 0.94, 1.0, 1.0] if not is_danger else BG_BUTTON_DANGER_PRESSED)
    label = text("ButtonText", label_text, text_color, variable=True)
    label["slot"] = {"h_align": "center", "v_align": "center"}
    return {
        "type": "Button",
        "name": "InteractiveButton",
        "is_variable": True,
        "padding": PAD_CONTROL,
        "style": style(
            color=bg,
            radius=RADIUS_CONTROL,
            border_color=border_color,
            border_width=1,
            hover_color=hover_color,
            pressed_color=pressed_color,
        ),
        "children": [label],
    }


def fill_slot(ratio=1.0):
    return {"size": {"fill": ratio}}


def auto_slot():
    return {"size": {"auto": True}}


def pad_slot(padding):
    return {"padding": padding}


def merge_slot(*slots):
    """Merge multiple slot dicts."""
    result = {}
    for s in slots:
        if s:
            result.update(s)
    return result


def spec(asset_path, parent_class, root):
    return {"asset_path": asset_path, "parent_class": parent_class, "root": root}


def write(name, data):
    path = ROOT / name
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


# =====================================================================
# GROUP 4A — Core atoms
# =====================================================================

def gen_badge():
    write("core_badge.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_Badge",
        "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
        border("BadgeBackground", BG_BUTTON_ACCENT, [
            {**text("LabelText", "Badge", TEXT_ON_PRIMARY, variable=True),
             "slot": dict(CENTER_SLOT)}
        ], padding=PAD_TIGHT, variable=True, radius=RADIUS_PILL, border_color=BG_BUTTON_ACCENT)
    ))


def gen_avatar():
    write("core_avatar.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_Avatar",
        "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
        sizebox("AvatarFrame", 128, 128, [
            overlay("AvatarOverlay", [
                {"type": "Image", "name": "AvatarImage", "is_variable": True,
                 "brush": PLACEHOLDER_BRUSH,
                 "slot": {"h_align": "fill", "v_align": "fill"}},
                {"type": "TextBlock", "name": "LabelText", "is_variable": True, "text": "",
                 "style": {"color": TEXT_PRIMARY},
                 "slot": {"h_align": "center", "v_align": "bottom"}}
            ], variable=False)
        ], variable=True)
    ))


def gen_divider():
    write("core_divider.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_Divider",
        "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
        sizebox("DividerFrame", None, 2, [
            border("DividerLine", DIVIDER_VISIBLE, [], padding=[0, 0, 0, 0], variable=True, radius=0, border_color=DIVIDER_VISIBLE, border_width=0)
        ], variable=False)
    ))


def gen_currency_pill():
    write("core_currency_pill.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_CurrencyPill",
        "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
        border("PillBackground", BG_CARD, [
            hbox("CurrencyRow", [
                {**text("LabelText", "Currency", TEXT_MUTED, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 8, 0]))},
                {**text("ValueText", "0", TEXT_PRIMARY, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_TIGHT, variable=True, radius=RADIUS_PILL)
    ))


def gen_loading_indicator():
    write("core_loading_indicator.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator",
        "/Script/AccelByteUITools.AGSStateWidgetBase",
        border("LoadingBackground", BG_CARD, [
            {**text("StatusText", "Loading…", TEXT_MUTED, variable=True),
             "slot": {"h_align": "center", "v_align": "center"}}
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


# =====================================================================
# GROUP 4B — Core controls (buttons, inputs)
# =====================================================================

def gen_base_button():
    write("core_base_button.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton",
        "/Script/AccelByteUITools.AGSButtonBase",
        button_asset_root("Button", BG_BUTTON_ACCENT)
    ))


def gen_secondary_button():
    write("core_secondary_button.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_SecondaryButton",
        "/Script/AccelByteUITools.AGSButtonBase",
        button_asset_root("Secondary", BG_BUTTON)
    ))


def gen_danger_button():
    write("core_danger_button.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_DangerButton",
        "/Script/AccelByteUITools.AGSButtonBase",
        button_asset_root("Delete", BG_BUTTON_DANGER)
    ))


def gen_icon_button():
    write("core_icon_button.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_IconButton",
        "/Script/AccelByteUITools.AGSButtonBase",
        sizebox("IconButtonFrame", 40, 40, [
            overlay("IconButtonOverlay", [
                {"type": "Button", "name": "InteractiveButton", "is_variable": True,
                 "style": style(color=BG_BUTTON, radius=RADIUS_CONTROL, border_color=BORDER_SUBTLE,
                                border_width=1, hover_color=BG_SUBTLE, pressed_color=DIVIDER),
                 "slot": {"h_align": "fill", "v_align": "fill"}},
                {"type": "Image", "name": "ButtonIcon", "is_variable": True,
                 "brush": PLACEHOLDER_BRUSH,
                 "slot": {"h_align": "fill", "v_align": "fill", "padding": [4, 4, 4, 4]}}
            ], variable=False)
        ], variable=False)
    ))


def gen_text_input():
    write("core_text_input.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput",
        "/Script/AccelByteUITools.AGSTextInputBase",
        {"type": "EditableTextBox", "name": "ValueInput", "is_variable": True,
         "hint_text": "Enter text",
         "padding": PAD_CONTROL,
         "style": preset(TOKENS, "input")}
    ))


def gen_password_input():
    write("core_password_input.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_PasswordInput",
        "/Script/AccelByteUITools.AGSTextInputBase",
        {"type": "EditableTextBox", "name": "ValueInput", "is_variable": True,
         "hint_text": "Password", "is_password": True,
         "padding": PAD_CONTROL,
         "style": preset(TOKENS, "input")}
    ))


def gen_search_input():
    write("core_search_input.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_SearchInput",
        "/Script/AccelByteUITools.AGSTextInputBase",
        {"type": "EditableTextBox", "name": "ValueInput", "is_variable": True,
         "hint_text": "Search",
         "padding": PAD_CONTROL,
         "style": preset(TOKENS, "input")}
    ))


def gen_section_header():
    write("core_section_header.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_SectionHeader",
        "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
        border("HeaderBackground", BG_CARD, [
            text("LabelText", "Section", TEXT_PRIMARY, variable=True)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


# =====================================================================
# GROUP 4C — State widgets + panels
# =====================================================================

def gen_status_message():
    write("core_status_message.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage",
        "/Script/AccelByteUITools.AGSStatusMessageBase",
        border("StatusBackground", BG_CARD, [
            {**text("StatusText", "Status", TEXT_PRIMARY, variable=True),
             "slot": dict(CENTER_SLOT)}
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_empty_state():
    write("core_empty_state.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState",
        "/Script/AccelByteUITools.AGSStateWidgetBase",
        border("EmptyBackground", BG_CARD, [
            {**vbox("EmptyStack", [
                {**text("LabelText", "Nothing here yet", TEXT_PRIMARY, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 4]),
                                    {"h_align": "center"})},
                {**text("StatusText", "Check back later", TEXT_MUTED, variable=True),
                 "slot": merge_slot(auto_slot(), {"h_align": "center"})}
            ], variable=False),
             "slot": dict(CENTER_SLOT)}
        ], padding=PAD_PANEL, variable=True)
    ))


def gen_error_state():
    write("core_error_state.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState",
        "/Script/AccelByteUITools.AGSStateWidgetBase",
        border("ErrorBackground", BG_CARD, [
            vbox("ErrorStack", [
                {**text("LabelText", "Something went wrong", TEXT_DANGER, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 4]),
                                    {"h_align": "center"})},
                {**text("StatusText", "Please retry.", TEXT_MUTED, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]),
                                    {"h_align": "center"})},
                {**button("RetryButton", "Retry", BG_BUTTON, variable=True),
                 "slot": merge_slot(auto_slot(), {"h_align": "center"})}
            ], variable=False)
        ], padding=PAD_PANEL, variable=True)
    ))


def gen_base_panel():
    write("core_base_panel.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_BasePanel",
        "/Script/AccelByteUITools.AGSStateWidgetBase",
        border("PanelBackground", BG_PRIMARY, [
            vbox("PanelStack", [
                {**text("LabelText", "Panel", TEXT_PRIMARY, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]))},
                vbox("BodySlot", [], variable=True, slot=fill_slot(1.0))
            ], variable=False)
        ], padding=PAD_PANEL, variable=True)
    ))


def gen_modal_panel():
    write("core_modal_panel.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_ModalPanel",
        "/Script/AccelByteUITools.AGSActionPanelBase",
        border("ModalBackground", BG_CARD, [
            {**vbox("ModalStack", [
                {**text("LabelText", "Title", TEXT_PRIMARY, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]))},
                {**text("StatusText", "Body text goes here.", TEXT_MUTED, variable=True),
                 "auto_wrap": True,
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 16]))},
                hbox("ActionRow", [
                    {**button("CancelButton", "Cancel", BG_BUTTON, variable=True),
                     "slot": merge_slot(auto_slot(), pad_slot([0, 0, 8, 0]))},
                    {**button("ConfirmButton", "Confirm", BG_BUTTON_ACCENT, variable=True),
                     "slot": auto_slot()}
                ], variable=False, slot=merge_slot(auto_slot(), {"h_align": "right"}))
            ], variable=False),
             "slot": dict(CENTER_SLOT)}
        ], padding=[24, 20, 24, 20], variable=True)
    ))


def gen_toast():
    write("core_toast.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_Toast",
        "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
        border("ToastBackground", BG_CARD, [
            {**text("LabelText", "Toast message", TEXT_PRIMARY, variable=True),
             "slot": dict(CENTER_SLOT)}
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_key_value_row():
    write("core_key_value_row.json", spec(
        "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow",
        "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
        hbox("KeyValueRow", [
            {**text("LabelText", "Key", TEXT_MUTED, variable=True),
             "slot": auto_slot()},
            {**text("ValueText", "Value", TEXT_PRIMARY, variable=True),
             "slot": merge_slot(fill_slot(1.0), {"h_align": "right"})}
        ], variable=True)
    ))


# =====================================================================
# GROUP 4D — List rows + ListPanel
# =====================================================================

def gen_list_row():
    write("list_row.json", spec(
        "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow",
        "/Script/AccelByteUITools.AGSListRowBase",
        border("RowBackground", BG_ROW, [
            hbox("RowContent", [
                {**text("LabelText", "Item", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**text("ValueText", "—", TEXT_MUTED, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_player_row():
    write("player_row.json", spec(
        "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow",
        "/Script/AccelByteUITools.AGSListRowBase",
        border("RowBackground", BG_ROW, [
            hbox("PlayerRow", [
                {**text("LabelText", "Player", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**text("ValueText", "Online", TEXT_SUCCESS, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_leaderboard_row():
    write("leaderboard_row.json", spec(
        "/AccelByteUITools/AGSUI/Lists/WBP_AGS_LeaderboardRow",
        "/Script/AccelByteUITools.AGSListRowBase",
        border("RowBackground", BG_ROW, [
            hbox("LeaderboardRow", [
                {**text("LabelText", "#1", TEXT_MUTED, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 12, 0]))},
                {**text("ValueText", "Player", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**text("StatusText", "0", TEXT_PRIMARY, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_entitlement_row():
    write("entitlement_row.json", spec(
        "/AccelByteUITools/AGSUI/Lists/WBP_AGS_EntitlementRow",
        "/Script/AccelByteUITools.AGSListRowBase",
        border("RowBackground", BG_ROW, [
            hbox("EntitlementRow", [
                {**text("LabelText", "Entitlement", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**text("ValueText", "Active", TEXT_SUCCESS, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_list_panel():
    write("list_panel.json", spec(
        "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListPanel",
        "/Script/AccelByteUITools.AGSListRowBase",
        border("PanelBackground", BG_PRIMARY, [
            vbox("PanelStack", [
                {**text("LabelText", "List", TEXT_PRIMARY, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]))},
                listview(
                    "ListBody",
                    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C",
                    variable=True,
                    slot=fill_slot(1.0),
                )
            ], variable=False)
        ], padding=PAD_PANEL, variable=True)
    ))


# =====================================================================
# GROUP 4E — Feature rows + cards
# =====================================================================

def feature_row(asset_name, label, value_text, value_color=TEXT_MUTED):
    write(f"feature_{asset_name}.json", spec(
        f"/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_{snake_to_camel(asset_name)}",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("RowBackground", BG_ROW, [
            hbox("RowContent", [
                {**text("LabelText", label, TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**text("ValueText", value_text, value_color, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def snake_to_camel(s):
    return "".join(p.capitalize() for p in s.split("_"))


def gen_friend_row():
    write("feature_friend_row.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendRow",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("RowBackground", BG_ROW, [
            hbox("FriendRow", [
                {**text("LabelText", "Friend", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**text("StatusText", "Online", TEXT_SUCCESS, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 12, 0]))},
                {**button("SubmitButton", "Message", BG_BUTTON, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_party_member_row():
    write("feature_party_member_row.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyMemberRow",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("RowBackground", BG_ROW, [
            hbox("PartyMemberRow", [
                {**text("LabelText", "Member", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**text("StatusText", "Ready", TEXT_SUCCESS, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_block_user_row():
    write("feature_block_user_row.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_BlockUserRow",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("RowBackground", BG_ROW, [
            hbox("BlockedRow", [
                {**text("LabelText", "Blocked user", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**button("CancelButton", "Unblock", BG_BUTTON, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_cloud_save_slot_row():
    write("feature_cloud_save_slot_row.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotRow",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("RowBackground", BG_ROW, [
            hbox("SlotRow", [
                vbox("SlotInfo", [
                    text("LabelText", "Slot name", TEXT_PRIMARY, variable=True),
                    muted_text("StatusText", "Last saved: never", variable=True)
                ], variable=False, slot=fill_slot(1.0)),
                hbox("SlotActions", [
                    {**button("ConfirmButton", "Load", BG_BUTTON, variable=True),
                     "slot": merge_slot(auto_slot(), pad_slot([0, 0, 8, 0]))},
                    {**button("SubmitButton", "Save", BG_BUTTON_ACCENT, variable=True),
                     "slot": auto_slot()}
                ], variable=False, slot=auto_slot())
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_session_row():
    write("feature_session_row.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionRow",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("RowBackground", BG_ROW, [
            hbox("SessionRow", [
                vbox("SessionInfo", [
                    text("LabelText", "Session name", TEXT_PRIMARY, variable=True),
                    muted_text("StatusText", "2/8 players", variable=True)
                ], variable=False, slot=fill_slot(1.0)),
                {**button("ConfirmButton", "Join", BG_BUTTON_ACCENT, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_incoming_friend_row():
    write("feature_incoming_friend_row.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_IncomingFriendRequestRow",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("RowBackground", BG_ROW, [
            hbox("RequestRow", [
                {**text("LabelText", "Friend request", TEXT_PRIMARY, variable=True),
                 "slot": fill_slot(1.0)},
                {**button("ConfirmButton", "Accept", BG_BUTTON_ACCENT, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 8, 0]))},
                {**button("CancelButton", "Decline", BG_BUTTON, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_ROW, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_achievement_card():
    write("feature_achievement_card.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementCard",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("CardBackground", BG_ROW, [
            vbox("CardStack", [
                {**text("LabelText", "Achievement", TEXT_PRIMARY, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 4]))},
                {**muted_text("ValueText", "Description", variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]))},
                {**text("StatusText", "Locked", TEXT_MUTED, variable=True),
                 "slot": auto_slot()}
            ], variable=False)
        ], padding=PAD_CARD, variable=True, border_color=BORDER_CONTROL)
    ))


def gen_store_item_card():
    write("feature_store_item_card.json", spec(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard",
        "/Script/AccelByteUITools.AGSFeatureBlockBase",
        border("CardBackground", BG_ROW, [
            vbox("CardStack", [
                {**text("LabelText", "Item name", TEXT_PRIMARY, variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 4]))},
                {**muted_text("StatusText", "Description", variable=True),
                 "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]))},
                hbox("CardFooter", [
                    {**text("ValueText", "100", TEXT_PRIMARY, variable=True),
                     "slot": fill_slot(1.0)},
                    {**button("SubmitButton", "Buy", BG_BUTTON_ACCENT, variable=True),
                     "slot": auto_slot()}
                ], variable=False, slot=auto_slot())
            ], variable=False)
        ], padding=PAD_CARD, variable=True, border_color=BORDER_CONTROL)
    ))


# =====================================================================
# GROUP 4F — Feature blocks (full panels)
# =====================================================================

def feature_block_skeleton(asset, title, body, parent="/Script/AccelByteUITools.AGSFeatureBlockBase"):
    """Standard feature block: title header + body. Body is a list of child node dicts."""
    return spec(asset, parent, border("BlockBackground", BG_PRIMARY, [
        vbox("BlockStack", [
            {**text("LabelText", title, TEXT_PRIMARY, variable=True),
             "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 12]))},
        ] + body, variable=False)
    ], padding=PAD_PANEL, variable=True))


def list_body(name, row_class, row_count=3):
    """ListView with a native entry class and design-time preview rows."""
    preview_entries = [{"name": f"Item {i}"} for i in range(1, row_count + 1)]
    return listview(name, row_class, variable=True, slot=fill_slot(1.0), preview_entries=preview_entries)


def gen_login_block():
    body = [
        {**input_field("UsernameField", kind="text", hint_text="Username", variable=True),
         "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]))},
        {**input_field("PasswordField", kind="password", hint_text="Password", variable=True),
         "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 12]))},
        {**button("SubmitButton", "Sign in", BG_BUTTON_ACCENT, variable=True),
         "slot": auto_slot()}
    ]
    write("feature_login_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LoginBlock",
        "Sign in", body))


def gen_account_link_block():
    body = [
        {**muted_text("StatusText", "Link your account to continue.", variable=True),
         "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 12]))},
        {**button("SubmitButton", "Link account", BG_BUTTON_ACCENT, variable=True),
         "slot": auto_slot()}
    ]
    write("feature_account_link_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AccountLinkBlock",
        "Account link", body))


def gen_session_expired_block():
    body = [
        {**muted_text("StatusText", "Your session has expired.", variable=True),
         "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 12]))},
        {**button("SubmitButton", "Sign in again", BG_BUTTON_ACCENT, variable=True),
         "slot": auto_slot()}
    ]
    write("feature_session_expired_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionExpiredBlock",
        "Session expired", body))


def gen_friends_list_block():
    body = [list_body("ListBody",
                      "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendRow.WBP_AGS_FriendRow_C")]
    write("feature_friends_list_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendsListBlock",
        "Friends", body))


def gen_party_block():
    body = [list_body("ListBody",
                      "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyMemberRow.WBP_AGS_PartyMemberRow_C")]
    write("feature_party_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyBlock",
        "Party", body))


def gen_matchmaking_status_block():
    body = [
        {**muted_text("StatusText", "Searching for a match…", variable=True),
         "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 12]))},
        {**button("CancelButton", "Cancel", BG_BUTTON, variable=True),
         "slot": auto_slot()}
    ]
    write("feature_matchmaking_status_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_MatchmakingStatusBlock",
        "Matchmaking", body))


def gen_session_browser_block():
    body = [list_body("ListBody",
                      "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionRow.WBP_AGS_SessionRow_C")]
    write("feature_session_browser_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionBrowserBlock",
        "Sessions", body))


def gen_leaderboard_block():
    body = [list_body("ListBody",
                      "/AccelByteUITools/AGSUI/Lists/WBP_AGS_LeaderboardRow.WBP_AGS_LeaderboardRow_C")]
    write("feature_leaderboard_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LeaderboardBlock",
        "Leaderboard", body))


def gen_achievement_grid_block():
    body = [{
        "type": "TileView",
        "name": "AchievementTileView",
        "is_variable": True,
        "entry_widget_class": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementCard.WBP_AGS_AchievementCard_C",
        "selection_mode": "none",
        "orientation": "vertical",
        "entry_width": 256,
        "entry_height": 256,
        "horizontal_entry_spacing": ENTRY_SPACING,
        "vertical_entry_spacing": ENTRY_SPACING,
        "preview_entries": [{"label": f"Achievement {i}"} for i in range(1, 7)],
        "slot": fill_slot(1.0),
    }]
    write("feature_achievement_grid_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementGridBlock",
        "Achievements", body))


def gen_stats_summary_block():
    body = [
        vbox("StatsList", [
            {"type": "KeyValueRow", "name": "Stat_1", "is_variable": False,
             "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow.WBP_AGS_KeyValueRow_C",
             "slot": pad_slot([0, 0, 0, 4])},
            {"type": "KeyValueRow", "name": "Stat_2", "is_variable": False,
             "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow.WBP_AGS_KeyValueRow_C",
             "slot": pad_slot([0, 0, 0, 4])},
            {"type": "KeyValueRow", "name": "Stat_3", "is_variable": False,
             "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow.WBP_AGS_KeyValueRow_C"}
        ], variable=True, slot=fill_slot(1.0))
    ]
    write("feature_stats_summary_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StatsSummaryBlock",
        "Stats", body))


def gen_store_grid_block():
    body = [{
        "type": "TileView",
        "name": "StoreTileView",
        "is_variable": True,
        "entry_widget_class": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard.WBP_AGS_StoreItemCard_C",
        "selection_mode": "none",
        "orientation": "vertical",
        "entry_width": 256,
        "entry_height": 256,
        "horizontal_entry_spacing": ENTRY_SPACING,
        "vertical_entry_spacing": ENTRY_SPACING,
        "preview_entries": [{"label": f"Store Item {i}"} for i in range(1, 7)],
        "slot": fill_slot(1.0),
    }]
    write("feature_store_grid_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreGridBlock",
        "Store", body))


def gen_wallet_balance_block():
    body = [
        hbox("WalletRow", [
            {**text("LabelText", "Coins", TEXT_MUTED, variable=True),
             "slot": fill_slot(1.0)},
            {**text("ValueText", "0", TEXT_PRIMARY, variable=True),
             "slot": auto_slot()}
        ], variable=False, slot=merge_slot(auto_slot(), pad_slot([0, 0, 0, 8]))),
        {**muted_text("StatusText", "Balance is live.", variable=True),
         "slot": auto_slot()}
    ]
    write("feature_wallet_balance_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_WalletBalanceBlock",
        "Wallet", body))


def gen_entitlements_block():
    body = [list_body("ListBody",
                      "/AccelByteUITools/AGSUI/Lists/WBP_AGS_EntitlementRow.WBP_AGS_EntitlementRow_C")]
    write("feature_entitlements_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_EntitlementsBlock",
        "Entitlements", body))


def gen_cloud_save_slots_block():
    body = [list_body("ListBody",
                      "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotRow.WBP_AGS_CloudSaveSlotRow_C")]
    write("feature_cloud_save_slots_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotsBlock",
        "Cloud saves", body))


def gen_notification_list_block():
    body = [list_body("ListBody",
                      "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C")]
    write("feature_notification_list_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_NotificationListBlock",
        "Notifications", body))


def gen_generic_async_action_block():
    body = [
        {**muted_text("StatusText", "Working on it…", variable=True),
         "slot": merge_slot(auto_slot(), pad_slot([0, 0, 0, 12]))},
        hbox("ActionRow", [
            {**button("CancelButton", "Cancel", BG_BUTTON, variable=True),
             "slot": merge_slot(auto_slot(), pad_slot([0, 0, 8, 0]))},
            {**button("RetryButton", "Retry", BG_BUTTON_ACCENT, variable=True),
             "slot": auto_slot()}
        ], variable=False, slot=merge_slot(auto_slot(), {"h_align": "right"}))
    ]
    write("feature_generic_async_action_block.json", feature_block_skeleton(
        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_GenericAsyncActionBlock",
        "Action", body))


def main():
    # 4a Core atoms
    gen_badge()
    gen_avatar()
    gen_divider()
    gen_currency_pill()
    gen_loading_indicator()

    # 4b Core controls
    gen_base_button()
    gen_secondary_button()
    gen_danger_button()
    gen_icon_button()
    gen_text_input()
    gen_password_input()
    gen_search_input()
    gen_section_header()

    # 4c State widgets + panels
    gen_status_message()
    gen_empty_state()
    gen_error_state()
    gen_base_panel()
    gen_modal_panel()
    gen_toast()
    gen_key_value_row()

    # 4d List rows
    gen_list_row()
    gen_player_row()
    gen_leaderboard_row()
    gen_entitlement_row()
    gen_list_panel()

    # 4e Feature rows + cards
    gen_friend_row()
    gen_party_member_row()
    gen_block_user_row()
    gen_cloud_save_slot_row()
    gen_session_row()
    gen_incoming_friend_row()
    gen_achievement_card()
    gen_store_item_card()

    # 4f Feature blocks
    gen_login_block()
    gen_account_link_block()
    gen_session_expired_block()
    gen_friends_list_block()
    gen_party_block()
    gen_matchmaking_status_block()
    gen_session_browser_block()
    gen_leaderboard_block()
    gen_achievement_grid_block()
    gen_stats_summary_block()
    gen_store_grid_block()
    gen_wallet_balance_block()
    gen_entitlements_block()
    gen_cloud_save_slots_block()
    gen_notification_list_block()
    gen_generic_async_action_block()

    print("Rewrote 49 component specs.")


if __name__ == "__main__":
    main()
