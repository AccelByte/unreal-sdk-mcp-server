from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any

try:
    from .theme_tokens import load_theme_tokens
except ImportError:
    from theme_tokens import load_theme_tokens


GENERATED_UI_ASSET_PATH = re.compile(r"^/Game/(?:[A-Za-z0-9_]+/)*UI/(?:Generated|Components)/(?:[A-Za-z0-9_]+/)*[A-Za-z_][A-Za-z0-9_]*$")
PLUGIN_AGSUI_ASSET_PATH = re.compile(
    r"^/AccelByteUITools/AGSUI/(?:Core|Lists|FeatureBlocks)/[A-Za-z_][A-Za-z0-9_]*$"
)
SUPPORTED_CONTAINERS = {
    "CanvasPanel",
    "Overlay",
    "VerticalBox",
    "HorizontalBox",
    "SizeBox",
    "Border",
    "Button",
    "SafeZone",
    "ScaleBox",
    "ScrollBox",
    "ListView",
    "TileView",
    "TreeView",
    "WidgetSwitcher",
    "UniformGridPanel",
    "WrapBox",
}
SUPPORTED_LEAVES = {"TextBlock", "EditableTextBox", "Image", "Spacer"}
SUPPORTED_PROJECT_WIDGETS = {"AccelByteWarsButtonBase"}
SUPPORTED_WIDGETS = SUPPORTED_CONTAINERS | SUPPORTED_LEAVES | SUPPORTED_PROJECT_WIDGETS
VALID_STYLE_MODES = {"auto", "agsui", "project"}
VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
VALID_CLASS_PATH = re.compile(
    r"^/(?:"
    r"Script/[A-Za-z0-9_]+\.[A-Za-z0-9_]+"          # /Script/Module.ClassName  (native C++ class)
    r"|[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*\.[A-Za-z0-9_]+_C"  # /Root/Path/Asset.Asset_C (blueprint asset)
    r")$"
)
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
GENERATED_AGS_REQUIRED_CORE_CONTROL_TYPES = {
    "AGSBaseButton",
    "AGSButton",
    "AGSSecondaryButton",
    "AGSDangerButton",
    "AGSIconButton",
    "AGSTextInput",
    "AGSPasswordInput",
    "AGSSearchInput",
}
GENERATED_AGS_FORBIDDEN_NATIVE_CONTROL_TYPES = {"Button", "EditableTextBox"}
GENERATED_AGS_FORBIDDEN_ALIAS_PREFIXES = (
    "/AccelByteUITools/AGSUI/FeatureBlocks/",
    "/AccelByteUITools/AGSUI/Lists/",
)
STALE_DARK_COLORS = {
    (0.08, 0.08, 0.1, 1.0),
    (0.13, 0.13, 0.16, 1.0),
    (0.11, 0.11, 0.14, 1.0),
}
PROJECT_PANEL_BACKGROUND_COLOR = [0.0, 0.0, 0.0, 0.1]

COMMON_UI_PARENT_CLASSES = frozenset({
    "/Script/AccelByteUITools.AGSCommonActivatableBase",
    "/Script/CommonUI.CommonActivatableWidget",
    "/Script/CommonUI.CommonUserWidget",
})

COMMON_UI_ALIAS_OVERRIDES: dict[str, str] = {
    "AGSBaseButton":      "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonButton.WBP_AGS_CommonButton_C",
    "AGSButton":          "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonButton.WBP_AGS_CommonButton_C",
    "AGSSecondaryButton": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonSecondaryButton.WBP_AGS_CommonSecondaryButton_C",
    "AGSDangerButton":    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonDangerButton.WBP_AGS_CommonDangerButton_C",
    "AGSIconButton":      "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonIconButton.WBP_AGS_CommonIconButton_C",
    "TextBlock":          "/Script/CommonUI.CommonTextBlock",
}

AGS_COMPONENT_ALIASES: dict[str, str] = {
    # Core atoms
    "AGSBadge":                   "/AccelByteUITools/AGSUI/Core/WBP_AGS_Badge.WBP_AGS_Badge_C",
    "AGSAvatar":                  "/AccelByteUITools/AGSUI/Core/WBP_AGS_Avatar.WBP_AGS_Avatar_C",
    "AGSDivider":                 "/AccelByteUITools/AGSUI/Core/WBP_AGS_Divider.WBP_AGS_Divider_C",
    "AGSCurrencyPill":            "/AccelByteUITools/AGSUI/Core/WBP_AGS_CurrencyPill.WBP_AGS_CurrencyPill_C",
    "AGSSectionHeader":           "/AccelByteUITools/AGSUI/Core/WBP_AGS_SectionHeader.WBP_AGS_SectionHeader_C",
    "AGSLoadingIndicator":        "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator.WBP_AGS_LoadingIndicator_C",
    "AGSStatusMessage":           "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C",
    "AGSEmptyState":              "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState.WBP_AGS_EmptyState_C",
    "AGSErrorState":              "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState.WBP_AGS_ErrorState_C",
    "AGSToast":                   "/AccelByteUITools/AGSUI/Core/WBP_AGS_Toast.WBP_AGS_Toast_C",
    "AGSKeyValueRow":             "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow.WBP_AGS_KeyValueRow_C",
    # Buttons
    "AGSBaseButton":              "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
    "AGSButton":                  "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
    "AGSSecondaryButton":         "/AccelByteUITools/AGSUI/Core/WBP_AGS_SecondaryButton.WBP_AGS_SecondaryButton_C",
    "AGSDangerButton":            "/AccelByteUITools/AGSUI/Core/WBP_AGS_DangerButton.WBP_AGS_DangerButton_C",
    "AGSIconButton":              "/AccelByteUITools/AGSUI/Core/WBP_AGS_IconButton.WBP_AGS_IconButton_C",
    # Inputs
    "AGSTextInput":               "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput.WBP_AGS_TextInput_C",
    "AGSPasswordInput":           "/AccelByteUITools/AGSUI/Core/WBP_AGS_PasswordInput.WBP_AGS_PasswordInput_C",
    "AGSSearchInput":             "/AccelByteUITools/AGSUI/Core/WBP_AGS_SearchInput.WBP_AGS_SearchInput_C",
    # Panels
    "AGSBasePanel":               "/AccelByteUITools/AGSUI/Core/WBP_AGS_BasePanel.WBP_AGS_BasePanel_C",
    "AGSModalPanel":              "/AccelByteUITools/AGSUI/Core/WBP_AGS_ModalPanel.WBP_AGS_ModalPanel_C",
    # Lists
    "AGSListRow":                 "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C",
    "AGSPlayerRow":               "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow.WBP_AGS_PlayerRow_C",
    "AGSLeaderboardRow":          "/AccelByteUITools/AGSUI/Lists/WBP_AGS_LeaderboardRow.WBP_AGS_LeaderboardRow_C",
    "AGSEntitlementRow":          "/AccelByteUITools/AGSUI/Lists/WBP_AGS_EntitlementRow.WBP_AGS_EntitlementRow_C",
    "AGSListPanel":               "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListPanel.WBP_AGS_ListPanel_C",
    # FeatureBlock rows / cards
    "AGSFriendRow":               "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendRow.WBP_AGS_FriendRow_C",
    "AGSPartyMemberRow":          "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyMemberRow.WBP_AGS_PartyMemberRow_C",
    "AGSBlockUserRow":            "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_BlockUserRow.WBP_AGS_BlockUserRow_C",
    "AGSCloudSaveSlotRow":        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotRow.WBP_AGS_CloudSaveSlotRow_C",
    "AGSSessionRow":              "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionRow.WBP_AGS_SessionRow_C",
    "AGSIncomingFriendRow":       "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_IncomingFriendRow.WBP_AGS_IncomingFriendRow_C",
    "AGSIncomingFriendRequestRow":"/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_IncomingFriendRow.WBP_AGS_IncomingFriendRow_C",
    "AGSAchievementCard":         "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementCard.WBP_AGS_AchievementCard_C",
    "AGSStoreItemCard":           "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard.WBP_AGS_StoreItemCard_C",
    # FeatureBlock panels
    "AGSLoginBlock":              "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LoginBlock.WBP_AGS_LoginBlock_C",
    "AGSAccountLinkBlock":        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AccountLinkBlock.WBP_AGS_AccountLinkBlock_C",
    "AGSSessionExpiredBlock":     "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionExpiredBlock.WBP_AGS_SessionExpiredBlock_C",
    "AGSMatchmakingStatusBlock":  "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_MatchmakingStatusBlock.WBP_AGS_MatchmakingStatusBlock_C",
    "AGSWalletBalanceBlock":      "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_WalletBalanceBlock.WBP_AGS_WalletBalanceBlock_C",
    "AGSGenericAsyncActionBlock": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_GenericAsyncActionBlock.WBP_AGS_GenericAsyncActionBlock_C",
    "AGSFriendsListBlock":        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendsListBlock.WBP_AGS_FriendsListBlock_C",
    "AGSPartyBlock":              "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyBlock.WBP_AGS_PartyBlock_C",
    "AGSSessionBrowserBlock":     "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionBrowserBlock.WBP_AGS_SessionBrowserBlock_C",
    "AGSLeaderboardBlock":        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LeaderboardBlock.WBP_AGS_LeaderboardBlock_C",
    "AGSNotificationListBlock":   "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_NotificationListBlock.WBP_AGS_NotificationListBlock_C",
    "AGSEntitlementsBlock":       "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_EntitlementsBlock.WBP_AGS_EntitlementsBlock_C",
    "AGSCloudSaveSlotsBlock":     "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotsBlock.WBP_AGS_CloudSaveSlotsBlock_C",
    "AGSStatsSummaryBlock":       "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StatsSummaryBlock.WBP_AGS_StatsSummaryBlock_C",
    "AGSAchievementGridBlock":    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementGridBlock.WBP_AGS_AchievementGridBlock_C",
    "AGSStoreGridBlock":          "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreGridBlock.WBP_AGS_StoreGridBlock_C",
}

EXPECTED_STATE_SWITCHER_CHILDREN = (
    ("Idle",    "AGSStatusMessage"),
    ("Loading", "AGSLoadingIndicator"),
    ("Success", None),
    ("Empty",   "AGSEmptyState"),
    ("Error",   "AGSErrorState"),
)
EXPECTED_STATE_CORE_ROLES = {
    "Idle": "state_idle",
    "Loading": "state_loading",
    "Empty": "state_empty",
    "Error": "state_error",
}
FALLBACK_STATE_PANEL_NAMES = {"IdlePanel", "LoadingPanel", "SuccessPanel", "EmptyPanel", "ErrorPanel"}
SUCCESS_STATE_CONTAINER_TYPES = {
    "CanvasPanel",
    "Overlay",
    "VerticalBox",
    "HorizontalBox",
    "SizeBox",
    "Border",
    "SafeZone",
    "ScaleBox",
    "ScrollBox",
    "WidgetSwitcher",
    "UniformGridPanel",
    "WrapBox",
}
STATE_CORE_ROLE_VALUES = set(EXPECTED_STATE_CORE_ROLES.values())
STATE_CHILD_NAME_PARTS = tuple(state_name.casefold() for state_name, _expected_type in EXPECTED_STATE_SWITCHER_CHILDREN)
FOCUSED_PARENT_REQUIRED_BINDINGS: dict[str, tuple[frozenset[str], str]] = {
    "/Script/AccelByteUITools.AGSButtonBase": (
        frozenset({"InteractiveButton", "ButtonText"}),
        "UAGSButtonBase widgets must include stable bindings: InteractiveButton and ButtonText.",
    ),
    "/Script/AccelByteUITools.AGSTextInputBase": (
        frozenset({"ValueInput"}),
        "UAGSTextInputBase widgets must include stable binding: ValueInput.",
    ),
}
FOCUSED_PARENT_ANY_BINDINGS: dict[str, tuple[frozenset[str], str]] = {
    "/Script/AccelByteUITools.AGSLabelValueWidgetBase": (
        frozenset({"LabelText", "ValueText"}),
        "UAGSLabelValueWidgetBase widgets must include at least one stable binding: LabelText or ValueText.",
    ),
    "/Script/AccelByteUITools.AGSActionPanelBase": (
        frozenset({"ConfirmButton", "CancelButton", "RetryButton"}),
        "UAGSActionPanelBase widgets must include at least one stable action binding: ConfirmButton, CancelButton, or RetryButton.",
    ),
}
FOCUSED_COMPONENT_CONTRACT_ASSET_PATHS = {
    path.rsplit(".", 1)[0]
    for alias, path in AGS_COMPONENT_ALIASES.items()
    if alias
    in {
        "AGSBaseButton",
        "AGSButton",
        "AGSSecondaryButton",
        "AGSDangerButton",
        "AGSTextInput",
        "AGSPasswordInput",
        "AGSSearchInput",
        "AGSStatusMessage",
        "AGSEmptyState",
        "AGSErrorState",
        "AGSModalPanel",
        "AGSKeyValueRow",
        "AGSSectionHeader",
        "AGSToast",
        "AGSBadge",
        "AGSAvatar",
        "AGSCurrencyPill",
    }
}


@dataclass(frozen=True)
class BindingMetadata:
    widget_name: str
    spec_type: str
    class_path: str | None
    cpp_type: str
    include: str
    bind_meta: str
    expected_unreal_class: str
    resolution_source: str = "static_contract"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "widget_name": self.widget_name,
            "spec_type": self.spec_type,
            "class_path": self.class_path,
            "cpp_type": self.cpp_type,
            "include": self.include,
            "bind_meta": self.bind_meta,
            "expected_unreal_class": self.expected_unreal_class,
            "resolution_source": self.resolution_source,
        }


@dataclass(frozen=True)
class BindingContract:
    cpp_type: str
    include: str
    expected_unreal_class: str


NATIVE_BINDING_CONTRACTS: dict[str, BindingContract] = {
    "Button": BindingContract("UButton", '"Components/Button.h"', "/Script/UMG.Button"),
    "TextBlock": BindingContract("UTextBlock", '"Components/TextBlock.h"', "/Script/UMG.TextBlock"),
    "EditableTextBox": BindingContract("UEditableTextBox", '"Components/EditableTextBox.h"', "/Script/UMG.EditableTextBox"),
    "WidgetSwitcher": BindingContract("UWidgetSwitcher", '"Components/WidgetSwitcher.h"', "/Script/UMG.WidgetSwitcher"),
    "ScrollBox": BindingContract("UScrollBox", '"Components/ScrollBox.h"', "/Script/UMG.ScrollBox"),
    "ListView": BindingContract("UListView", '"Components/ListView.h"', "/Script/UMG.ListView"),
    "TileView": BindingContract("UTileView", '"Components/TileView.h"', "/Script/UMG.TileView"),
    "TreeView": BindingContract("UTreeView", '"Components/TreeView.h"', "/Script/UMG.TreeView"),
    "VerticalBox": BindingContract("UVerticalBox", '"Components/VerticalBox.h"', "/Script/UMG.VerticalBox"),
    "HorizontalBox": BindingContract("UHorizontalBox", '"Components/HorizontalBox.h"', "/Script/UMG.HorizontalBox"),
    "Image": BindingContract("UImage", '"Components/Image.h"', "/Script/UMG.Image"),
    "Border": BindingContract("UBorder", '"Components/Border.h"', "/Script/UMG.Border"),
    "Overlay": BindingContract("UOverlay", '"Components/Overlay.h"', "/Script/UMG.Overlay"),
    "CanvasPanel": BindingContract("UCanvasPanel", '"Components/CanvasPanel.h"', "/Script/UMG.CanvasPanel"),
    "SizeBox": BindingContract("USizeBox", '"Components/SizeBox.h"', "/Script/UMG.SizeBox"),
    "SafeZone": BindingContract("USafeZone", '"Components/SafeZone.h"', "/Script/UMG.SafeZone"),
    "ScaleBox": BindingContract("UScaleBox", '"Components/ScaleBox.h"', "/Script/UMG.ScaleBox"),
    "UniformGridPanel": BindingContract("UUniformGridPanel", '"Components/UniformGridPanel.h"', "/Script/UMG.UniformGridPanel"),
    "WrapBox": BindingContract("UWrapBox", '"Components/WrapBox.h"', "/Script/UMG.WrapBox"),
    "Spacer": BindingContract("USpacer", '"Components/Spacer.h"', "/Script/UMG.Spacer"),
}

AGS_CORE_BINDING_CONTRACTS: dict[str, BindingContract] = {
    "AGSAvatar": BindingContract("UAGSAvatarBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSAvatarBase"),
    "AGSIconButton": BindingContract("UAGSIconButtonBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSIconButtonBase"),
    "AGSBaseButton": BindingContract("UAGSButtonBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSButtonBase"),
    "AGSButton": BindingContract("UAGSButtonBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSButtonBase"),
    "AGSSecondaryButton": BindingContract("UAGSButtonBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSButtonBase"),
    "AGSDangerButton": BindingContract("UAGSButtonBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSButtonBase"),
    "AGSTextInput": BindingContract("UAGSTextInputBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSTextInputBase"),
    "AGSPasswordInput": BindingContract("UAGSTextInputBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSTextInputBase"),
    "AGSSearchInput": BindingContract("UAGSTextInputBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSTextInputBase"),
    "AGSStatusMessage": BindingContract("UAGSStatusMessageBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSStatusMessageBase"),
    "AGSLoadingIndicator": BindingContract("UAGSLoadingIndicatorBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSLoadingIndicatorBase"),
    "AGSEmptyState": BindingContract("UAGSEmptyStateBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSEmptyStateBase"),
    "AGSErrorState": BindingContract("UAGSErrorStateBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSErrorStateBase"),
    "AGSModalPanel": BindingContract("UAGSActionPanelBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSActionPanelBase"),
    "AGSBasePanel": BindingContract("UAGSBasePanelBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSBasePanelBase"),
    "AGSBadge": BindingContract("UAGSLabelValueWidgetBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSLabelValueWidgetBase"),
    "AGSCurrencyPill": BindingContract("UAGSLabelValueWidgetBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSLabelValueWidgetBase"),
    "AGSKeyValueRow": BindingContract("UAGSLabelValueWidgetBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSLabelValueWidgetBase"),
    "AGSSectionHeader": BindingContract("UAGSLabelValueWidgetBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSLabelValueWidgetBase"),
    "AGSToast": BindingContract("UAGSLabelValueWidgetBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSLabelValueWidgetBase"),
    "AGSDivider": BindingContract("UAGSLabelValueWidgetBase", '"AGSUI/AGSWidgetBase.h"', "/Script/AccelByteUITools.AGSLabelValueWidgetBase"),
}
AGS_CORE_BINDING_CONTRACTS_BY_PATH = {
    AGS_COMPONENT_ALIASES[alias]: contract
    for alias, contract in AGS_CORE_BINDING_CONTRACTS.items()
    if alias in AGS_COMPONENT_ALIASES
}

COMMON_UI_BINDING_CONTRACTS: dict[str, BindingContract] = {
    "AGSBaseButton":      BindingContract("UAGSCommonButtonBase",     '"AGSUI/AGSCommonWidgetBase.h"', "/Script/AccelByteUITools.AGSCommonButtonBase"),
    "AGSButton":          BindingContract("UAGSCommonButtonBase",     '"AGSUI/AGSCommonWidgetBase.h"', "/Script/AccelByteUITools.AGSCommonButtonBase"),
    "AGSSecondaryButton": BindingContract("UAGSCommonButtonBase",     '"AGSUI/AGSCommonWidgetBase.h"', "/Script/AccelByteUITools.AGSCommonButtonBase"),
    "AGSDangerButton":    BindingContract("UAGSCommonButtonBase",     '"AGSUI/AGSCommonWidgetBase.h"', "/Script/AccelByteUITools.AGSCommonButtonBase"),
    "AGSIconButton":      BindingContract("UAGSCommonIconButtonBase", '"AGSUI/AGSCommonWidgetBase.h"', "/Script/AccelByteUITools.AGSCommonIconButtonBase"),
    "TextBlock":          BindingContract("UCommonTextBlock",         '"CommonTextBlock.h"',           "/Script/CommonUI.CommonTextBlock"),
}
COMMON_UI_BINDING_CONTRACTS_BY_PATH: dict[str, BindingContract] = {
    COMMON_UI_ALIAS_OVERRIDES[alias]: contract
    for alias, contract in COMMON_UI_BINDING_CONTRACTS.items()
    if alias in COMMON_UI_ALIAS_OVERRIDES
}

BIND_WIDGET_META = "BindWidget, BlueprintProtected = true, AllowPrivateAccess = true"
BIND_WIDGET_OPTIONAL_META = "BindWidgetOptional, BlueprintProtected = true, AllowPrivateAccess = true"
COMMON_TEXT_BLOCK_CLASS_PATH = "/Script/CommonUI.CommonTextBlock"


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
    padding: tuple[float, float, float, float] | None = None
    slot: dict[str, Any] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)
    text: str | None = None
    hint_text: str | None = None
    is_password: bool = False
    brush: str | None = None
    visibility: str | None = None
    class_path: str | None = None
    button_style_class: str | None = None
    text_style_class: str | None = None
    style_asset: str | None = None
    entry_widget_class: str | None = None
    selection_mode: str | None = None
    orientation: str | None = None
    entry_width: float | None = None
    entry_height: float | None = None
    horizontal_entry_spacing: float | None = None
    vertical_entry_spacing: float | None = None
    preview_entries: tuple[dict[str, Any], ...] = ()
    optional_binding: bool = False
    core_role: str | None = None
    children: tuple["WidgetNode", ...] = ()

    def walk(self) -> list["WidgetNode"]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.walk())
        return nodes

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type,
            "name": self.name,
        }
        if self.is_variable:
            data["is_variable"] = True
        if self.padding is not None:
            data["padding"] = list(self.padding)
        if self.slot:
            data["slot"] = dict(self.slot)
        if self.style:
            data["style"] = dict(self.style)
        if self.text is not None:
            data["text"] = self.text
        if self.hint_text is not None:
            data["hint_text"] = self.hint_text
        if self.is_password:
            data["is_password"] = True
        if self.brush is not None:
            data["brush"] = self.brush
        if self.visibility is not None:
            data["visibility"] = self.visibility
        if self.class_path is not None:
            data["class_path"] = self.class_path
        if self.button_style_class is not None:
            data["button_style_class"] = self.button_style_class
        if self.text_style_class is not None:
            data["text_style_class"] = self.text_style_class
        if self.style_asset is not None:
            data["style_asset"] = self.style_asset
        if self.entry_widget_class is not None:
            data["entry_widget_class"] = self.entry_widget_class
        if self.selection_mode is not None:
            data["selection_mode"] = self.selection_mode
        if self.orientation is not None:
            data["orientation"] = self.orientation
        if self.entry_width is not None:
            data["entry_width"] = self.entry_width
        if self.entry_height is not None:
            data["entry_height"] = self.entry_height
        if self.horizontal_entry_spacing is not None:
            data["horizontal_entry_spacing"] = self.horizontal_entry_spacing
        if self.vertical_entry_spacing is not None:
            data["vertical_entry_spacing"] = self.vertical_entry_spacing
        if self.preview_entries:
            data["preview_entries"] = [dict(entry) for entry in self.preview_entries]
        if self.optional_binding:
            data["optional_binding"] = True
        if self.core_role is not None:
            data["core_role"] = self.core_role
        if self.children:
            data["children"] = [child.to_dict() for child in self.children]
        return data


@dataclass(frozen=True)
class WidgetSpec:
    asset_path: str
    parent_class: str
    root: WidgetNode
    ui_mode: str = "umg"
    style_mode: str = "auto"
    project_class_mapping: dict[str, str] = field(default_factory=dict)

    def widget_count(self) -> int:
        return len(self.root.walk())

    def variable_widget_names(self) -> list[str]:
        return [node.name for node in self.root.walk() if node.is_variable]

    def bindings(self) -> list[BindingMetadata]:
        return [
            binding
            for node in self.root.walk()
            if node.is_variable
            for binding in [_binding_metadata_for_node(node, self.ui_mode, self.project_class_mapping)]
        ]

    def to_dict(self) -> dict[str, Any]:
        data = {
            "asset_path": self.asset_path,
            "parent_class": self.parent_class,
            "ui_mode": self.ui_mode,
            "root": self.root.to_dict(),
        }
        if self.style_mode != "auto":
            data["style_mode"] = self.style_mode
        return data


def load_spec_file(
    path: str | Path,
    *,
    enforce_generated_ags_policy: bool | None = None,
    project_class_mapping: dict[str, str] | None = None,
) -> WidgetSpec:
    with Path(path).open("r", encoding="utf-8") as spec_file:
        return load_spec_from_dict(
            json.load(spec_file),
            enforce_generated_ags_policy=enforce_generated_ags_policy,
            project_class_mapping=project_class_mapping,
        )


def load_spec_from_dict(
    data: dict[str, Any],
    *,
    enforce_generated_ags_policy: bool | None = None,
    project_class_mapping: dict[str, str] | None = None,
    extra_parent_classes: frozenset[str] | None = None,
) -> WidgetSpec:
    if not isinstance(data, dict):
        raise ValidationError("schema_error", "Spec root must be a JSON object.")

    asset_path = _required_string(data, "asset_path")
    parent_class = _required_string(data, "parent_class")
    root_data = data.get("root")

    ui_mode = data.get("ui_mode", "umg")
    if ui_mode not in {"umg", "common_ui"}:
        raise ValidationError("schema_error", "ui_mode must be 'umg' or 'common_ui'.")
    style_mode = data.get("style_mode", "auto")
    if style_mode not in VALID_STYLE_MODES:
        raise ValidationError("invalid_style_mode", "style_mode must be one of: agsui, auto, project.")

    if not GENERATED_UI_ASSET_PATH.match(asset_path) and not PLUGIN_AGSUI_ASSET_PATH.match(asset_path):
        raise ValidationError(
            "asset_path_denied",
            "Asset path must be under a project UI/Generated or UI/Components folder, or /AccelByteUITools/AGSUI plugin content.",
        )
    if not parent_class.startswith("/Script/"):
        raise ValidationError("schema_error", "parent_class must start with /Script/.")
    if not isinstance(root_data, dict):
        raise ValidationError("schema_error", "root must be an object.")

    extra_parent_classes = extra_parent_classes or frozenset()
    allowed_parent_classes = COMMON_UI_PARENT_CLASSES | extra_parent_classes
    if ui_mode == "common_ui" and parent_class not in allowed_parent_classes:
        raise ValidationError(
            "schema_error",
            f"ui_mode 'common_ui' requires parent_class to be one of: "
            + ", ".join(sorted(allowed_parent_classes))
            + f". Got '{parent_class}'.",
        )
    if ui_mode == "umg" and parent_class in COMMON_UI_PARENT_CLASSES and parent_class not in extra_parent_classes:
        raise ValidationError(
            "schema_error",
            f"parent_class '{parent_class}' is a Common UI base class. "
            "Set ui_mode: 'common_ui' to target Common UI.",
        )

    if enforce_generated_ags_policy is None:
        enforce_generated_ags_policy = asset_path.startswith("/Game/AGS/UI/Generated/") and not _is_collection_entry_asset_path(asset_path)
    spec = WidgetSpec(
        asset_path=asset_path,
        parent_class=parent_class,
        root=_parse_node(root_data, "root", enforce_generated_ags_policy, ui_mode, style_mode),
        ui_mode=ui_mode,
        style_mode=style_mode,
        project_class_mapping=dict(project_class_mapping or {}),
    )
    spec = _normalize_entry_spec_root(spec)
    _validate_spec(spec, enforce_generated_ags_policy, project_class_mapping)
    return spec


def canonicalize_spec(
    data: dict[str, Any],
    *,
    enforce_generated_ags_policy: bool | None = None,
    project_class_mapping: dict[str, str] | None = None,
    extra_parent_classes: frozenset[str] | None = None,
) -> dict[str, Any]:
    return load_spec_from_dict(
        data,
        enforce_generated_ags_policy=enforce_generated_ags_policy,
        project_class_mapping=project_class_mapping,
        extra_parent_classes=extra_parent_classes,
    ).to_dict()


def _validate_text_style_classes(spec: WidgetSpec) -> None:
    for node in spec.root.walk():
        if node.type == "TextBlock" and node.text_style_class is not None:
            if node.class_path != COMMON_TEXT_BLOCK_CLASS_PATH:
                raise ValidationError(
                    "text_style_requires_common_text_block",
                    f"Widget '{node.name}' declares text_style_class but class_path is "
                    f"'{node.class_path}' instead of '{COMMON_TEXT_BLOCK_CLASS_PATH}'. "
                    "Add \"class_path\": \"/Script/CommonUI.CommonTextBlock\" to this node, "
                    "or remove text_style_class if CommonUI text styling is not intended.",
                )


def _validate_spec(
    spec: WidgetSpec,
    enforce_generated_ags_policy: bool,
    project_class_mapping: dict[str, str] | None = None,
) -> None:
    seen: set[str] = set()
    for node in spec.root.walk():
        if node.name in seen:
            raise ValidationError(
                "duplicate_widget_name",
                f"Widget name '{node.name}' appears more than once in the spec. "
                "Unreal auto-renames duplicates, breaking variable GUID mapping "
                "and any C++ references by name.",
            )
        seen.add(node.name)
        if node.is_variable:
            _binding_metadata_for_node(node, spec.ui_mode, project_class_mapping)

    _validate_text_style_classes(spec)
    _validate_root_panel_structure(spec)
    _validate_focused_parent_bindings(spec)
    if enforce_generated_ags_policy:
        _validate_generated_ags_state_contract(spec)


def _validate_root_panel_structure(spec: WidgetSpec) -> None:
    if not GENERATED_UI_ASSET_PATH.match(spec.asset_path):
        return
    if "/UI/Generated/" not in spec.asset_path:
        return
    if _is_collection_entry_asset_path(spec.asset_path):
        return

    root = spec.root

    if root.type != "Border":
        raise ValidationError(
            "invalid_root_structure",
            f"root.type must be 'Border' (the background panel). Got '{root.type}'. "
            "Required hierarchy: Border (PanelBackground) > Overlay (ContentContainer, padding=20) > content widgets.",
        )
    if root.name != "PanelBackground":
        raise ValidationError(
            "invalid_root_structure",
            f"root.name must be 'PanelBackground' for generated panels. Got '{root.name}'.",
        )

    if len(root.children) != 1:
        raise ValidationError(
            "invalid_root_structure",
            f"root (Border/PanelBackground) must have exactly 1 child (the ContentContainer Overlay). "
            f"Got {len(root.children)}.",
        )

    container = root.children[0]

    if container.type != "Overlay":
        raise ValidationError(
            "invalid_root_structure",
            f"root.children[0].type must be 'Overlay' (ContentContainer). Got '{container.type}'.",
        )
    if container.name != "ContentContainer":
        raise ValidationError(
            "invalid_root_structure",
            f"root.children[0].name must be 'ContentContainer' for generated panels. Got '{container.name}'.",
        )

    if container.slot.get("h_align") != "fill" or container.slot.get("v_align") != "fill":
        raise ValidationError(
            "invalid_root_structure",
            "ContentContainer (root.children[0]) must have slot.h_align='fill' and slot.v_align='fill'.",
        )

    if container.padding != (20.0, 20.0, 20.0, 20.0):
        raise ValidationError(
            "invalid_root_structure",
            "ContentContainer (root.children[0]) must have padding=[20, 20, 20, 20].",
        )

    for i, child in enumerate(container.children):
        if child.slot.get("h_align") != "fill" or child.slot.get("v_align") != "fill":
            raise ValidationError(
                "invalid_root_structure",
                f"root.children[0].children[{i}] ('{child.name}') must have "
                "slot.h_align='fill' and slot.v_align='fill'.",
            )


def _validate_focused_parent_bindings(spec: WidgetSpec) -> None:
    if spec.asset_path not in FOCUSED_COMPONENT_CONTRACT_ASSET_PATHS:
        return
    node_names = {node.name for node in spec.root.walk()}
    required_info = FOCUSED_PARENT_REQUIRED_BINDINGS.get(spec.parent_class)
    if required_info is not None:
        required, message = required_info
        missing = sorted(required - node_names)
        if missing:
            raise ValidationError(
                "focused_widget_contract",
                f"{message} Missing: {', '.join(missing)}.",
            )

    any_info = FOCUSED_PARENT_ANY_BINDINGS.get(spec.parent_class)
    if any_info is None:
        return
    accepted, message = any_info
    if node_names & accepted:
        return
    raise ValidationError("focused_widget_contract", message)


def _binding_metadata_for_node(
    node: WidgetNode,
    ui_mode: str = "umg",
    project_class_mapping: dict[str, str] | None = None,
) -> BindingMetadata:
    contract: BindingContract | None = None
    resolution_source = "static_contract"
    if node.class_path is not None and node.class_path.startswith("/Game/") and project_class_mapping:
        project_cpp_type = project_class_mapping.get(node.class_path)
        if project_cpp_type:
            contract = _static_contract_for_exact_project_mapped_type(node, ui_mode, project_cpp_type)
            if contract is not None:
                resolution_source = "static_contract_via_project_mapping"
            else:
                contract = _binding_contract_for_project_mapped_type(project_cpp_type)
                resolution_source = "style_context"
    if ui_mode == "common_ui":
        if contract is None:
            contract = COMMON_UI_BINDING_CONTRACTS.get(node.type)
        if contract is None and node.class_path is not None:
            contract = COMMON_UI_BINDING_CONTRACTS_BY_PATH.get(node.class_path)
    if contract is None:
        contract = AGS_CORE_BINDING_CONTRACTS.get(node.type)
    if contract is None and node.class_path is not None:
        contract = AGS_CORE_BINDING_CONTRACTS_BY_PATH.get(node.class_path)
    if contract is None and node.class_path is not None:
        contract = COMMON_UI_BINDING_CONTRACTS_BY_PATH.get(node.class_path)
    if contract is None:
        contract = NATIVE_BINDING_CONTRACTS.get(node.type)
    if contract is None:
        contract = BindingContract("UUserWidget", '"Blueprint/UserWidget.h"', "/Script/UMG.UserWidget")

    bind_meta = BIND_WIDGET_OPTIONAL_META if node.optional_binding else BIND_WIDGET_META
    return BindingMetadata(
        widget_name=node.name,
        spec_type=node.type,
        class_path=node.class_path,
        cpp_type=contract.cpp_type,
        include=contract.include,
        bind_meta=bind_meta,
        expected_unreal_class=contract.expected_unreal_class,
        resolution_source=resolution_source,
    )


def _static_contract_for_exact_project_mapped_type(
    node: WidgetNode,
    ui_mode: str,
    project_cpp_type: str,
) -> BindingContract | None:
    static_contract: BindingContract | None = None
    if ui_mode == "common_ui":
        static_contract = COMMON_UI_BINDING_CONTRACTS.get(node.type)
        if static_contract is None and node.class_path is not None:
            static_contract = COMMON_UI_BINDING_CONTRACTS_BY_PATH.get(node.class_path)
    if static_contract is None:
        static_contract = AGS_CORE_BINDING_CONTRACTS.get(node.type)
    if static_contract is None and node.class_path is not None:
        static_contract = AGS_CORE_BINDING_CONTRACTS_BY_PATH.get(node.class_path)
    if static_contract is not None and static_contract.cpp_type == project_cpp_type:
        return static_contract
    return None


def _binding_contract_for_project_mapped_type(project_cpp_type: str) -> BindingContract:
    if project_cpp_type.startswith("UAGS"):
        return BindingContract(
            project_cpp_type,
            '"AGSUI/AGSWidgetBase.h"',
            f"/Script/AccelByteUITools.{project_cpp_type[1:]}",
        )
    return BindingContract(
        project_cpp_type,
        f'"{project_cpp_type}.h"',
        f"/Script/Project.{project_cpp_type}",
    )


def _validate_generated_ags_state_contract(spec: WidgetSpec) -> None:
    if _is_collection_entry_asset_path(spec.asset_path):
        return
    state_switchers = [node for node in spec.root.walk() if node.name == "StateSwitcher"]
    for node in spec.root.walk():
        if node.type == "WidgetSwitcher" and node.name != "StateSwitcher" and _looks_like_state_switcher(node):
            raise ValidationError(
                "schema_error",
                f"State-like WidgetSwitcher '{node.name}' must be named StateSwitcher.",
            )
    if not state_switchers:
        return
    if len(state_switchers) > 1:
        raise ValidationError("schema_error", "Generated AGS panels may define only one StateSwitcher.")

    state_switcher = state_switchers[0]
    if state_switcher.type != "WidgetSwitcher":
        raise ValidationError("schema_error", "StateSwitcher must be a WidgetSwitcher.")
    if not state_switcher.is_variable:
        raise ValidationError("schema_error", "StateSwitcher must be marked is_variable: true.")
    if len(state_switcher.children) != len(EXPECTED_STATE_SWITCHER_CHILDREN):
        raise ValidationError("schema_error", "StateSwitcher must contain exactly Idle, Loading, Success, Empty, and Error children.")

    for child, (state_name, expected_type) in zip(state_switcher.children, EXPECTED_STATE_SWITCHER_CHILDREN):
        if state_name not in child.name:
            raise ValidationError("schema_error", f"StateSwitcher child '{child.name}' is not in the required {state_name} position.")
        if not child.is_variable:
            raise ValidationError("schema_error", f"StateSwitcher child '{child.name}' must be marked is_variable: true.")
        if expected_type is None:
            if child.type not in SUCCESS_STATE_CONTAINER_TYPES:
                raise ValidationError("schema_error", f"Success state '{child.name}' must be a native container widget.")
            continue
        expected_core_role = EXPECTED_STATE_CORE_ROLES.get(state_name)
        if expected_core_role and child.core_role == expected_core_role:
            continue
        if child.type != expected_type:
            raise ValidationError("schema_error", f"{state_name} state '{child.name}' must use type {expected_type}.")


def _looks_like_state_switcher(node: WidgetNode) -> bool:
    if not node.children:
        return False
    child_roles = {child.core_role for child in node.children if child.core_role}
    if child_roles & STATE_CORE_ROLE_VALUES:
        return True
    child_name_parts = {
        part
        for child in node.children
        for part in STATE_CHILD_NAME_PARTS
        if part in child.name.casefold()
    }
    if len(child_name_parts) >= 2:
        return True
    if len(node.children) == len(EXPECTED_STATE_SWITCHER_CHILDREN):
        return all(
            state_name.casefold() in child.name.casefold()
            for child, (state_name, _expected_type) in zip(node.children, EXPECTED_STATE_SWITCHER_CHILDREN)
        )
    return False


def _parse_node(
    data: dict[str, Any],
    path: str,
    enforce_generated_ags_policy: bool = False,
    ui_mode: str = "umg",
    style_mode: str = "auto",
) -> WidgetNode:
    widget_type = _required_string(data, "type", path)
    name = _required_string(data, "name", path)
    class_path = _optional_string(data, "class_path", path)
    button_style_class = _optional_string(data, "button_style_class", path)
    text_style_class = _optional_string(data, "text_style_class", path)
    style_asset = _optional_string(data, "style_asset", path)
    entry_widget_class = _optional_string(data, "entry_widget_class", path)
    core_role = _optional_string(data, "core_role", path) or _optional_string(data, "_core_role", path)
    if class_path is None:
        if ui_mode == "common_ui":
            class_path = COMMON_UI_ALIAS_OVERRIDES.get(widget_type) or AGS_COMPONENT_ALIASES.get(widget_type)
        elif widget_type in AGS_COMPONENT_ALIASES:
            class_path = AGS_COMPONENT_ALIASES[widget_type]
    # Auto-inject CommonTextBlock class_path when text_style_class is used on a TextBlock
    # (text_style_class is a CommonUI concept and requires UCommonTextBlock, not UTextBlock)
    if widget_type == "TextBlock" and text_style_class is not None and class_path is None:
        class_path = COMMON_TEXT_BLOCK_CLASS_PATH

    has_class_path = bool(class_path)

    if class_path is not None and not VALID_CLASS_PATH.match(class_path):
        raise ValidationError("schema_error", f"{path}.class_path must use /Root/Path/Asset.Asset_C or /Script/Module.ClassName form.")
    if button_style_class is not None and not VALID_CLASS_PATH.match(button_style_class):
        raise ValidationError("schema_error", f"{path}.button_style_class must use /Root/Path/Asset.Asset_C or /Script/Module.ClassName form.")
    if text_style_class is not None and not VALID_CLASS_PATH.match(text_style_class):
        raise ValidationError("schema_error", f"{path}.text_style_class must use /Root/Path/Asset.Asset_C or /Script/Module.ClassName form.")
    if entry_widget_class is not None and not VALID_CLASS_PATH.match(entry_widget_class):
        raise ValidationError("schema_error", f"{path}.entry_widget_class must use /Root/Path/Asset.Asset_C form.")
    if enforce_generated_ags_policy:
        _validate_generated_ags_widget_type(widget_type, path)
        _validate_generated_ags_plugin_reference(class_path, f"{path}.class_path")
        _validate_generated_ags_entry_widget_class(entry_widget_class, f"{path}.entry_widget_class")
    if widget_type not in SUPPORTED_WIDGETS and not has_class_path and not core_role:
        raise ValidationError("unsupported_widget", f"{path}.type '{widget_type}' is not supported.")
    if not VALID_NAME.match(name):
        raise ValidationError("schema_error", f"{path}.name '{name}' is not a valid Unreal object name.")
    if widget_type in {"ListView", "TileView", "TreeView"} and not entry_widget_class:
        raise ValidationError("schema_error", f"{path}.entry_widget_class is required for {widget_type}.")
    selection_mode = _optional_enum(data, "selection_mode", path, {"none", "single", "multi"})
    orientation = _optional_enum(data, "orientation", path, {"horizontal", "vertical"})
    entry_width = _optional_positive_number(data, "entry_width", path)
    entry_height = _optional_positive_number(data, "entry_height", path)
    if widget_type != "TileView" and (entry_width is not None or entry_height is not None):
        raise ValidationError("schema_error", f"{path}.entry_width and entry_height are only supported for TileView.")
    horizontal_entry_spacing = _optional_non_negative_number(data, "horizontal_entry_spacing", path)
    vertical_entry_spacing = _optional_non_negative_number(data, "vertical_entry_spacing", path)
    if widget_type not in {"ListView", "TileView"} and (horizontal_entry_spacing is not None or vertical_entry_spacing is not None):
        raise ValidationError("schema_error", f"{path}.horizontal_entry_spacing and vertical_entry_spacing are only supported for ListView and TileView.")
    if enforce_generated_ags_policy and widget_type in {"ListView", "TileView"} and (
        horizontal_entry_spacing is None or vertical_entry_spacing is None
    ):
        raise ValidationError("schema_error", f"{path}.horizontal_entry_spacing and vertical_entry_spacing are required for generated AGS ListView and TileView widgets.")
    if enforce_generated_ags_policy and widget_type == "EditableTextBox":
        _validate_generated_ags_editable_text_style(data, path)
    if enforce_generated_ags_policy:
        _validate_generated_ags_theme_tokens(data, widget_type, name, class_path, path, style_mode)
    padding = _optional_margin(data, "padding", path)
    preview_entries = _optional_array(data, "preview_entries", path)

    raw_children = data.get("children", [])
    if raw_children is None:
        raw_children = []
    if not isinstance(raw_children, list):
        raise ValidationError("schema_error", f"{path}.children must be an array.")

    children = tuple(
        _parse_node(child, f"{path}.children[{index}]", enforce_generated_ags_policy, ui_mode, style_mode)
        for index, child in enumerate(raw_children)
    )
    if widget_type in SUPPORTED_LEAVES and children:
        raise ValidationError("schema_error", f"{path}.children is not allowed for leaf widget '{widget_type}'.")

    return WidgetNode(
        type=widget_type,
        name=name,
        is_variable=bool(data.get("is_variable", False)),
        padding=padding,
        slot=_optional_object(data, "slot", path),
        style=_optional_style(data, "style", path),
        text=_optional_string(data, "text", path),
        hint_text=_optional_string(data, "hint_text", path),
        is_password=_optional_bool(data, "is_password", path),
        brush=_optional_string(data, "brush", path),
        visibility=_optional_string(data, "visibility", path),
        class_path=class_path,
        button_style_class=button_style_class,
        text_style_class=text_style_class,
        style_asset=style_asset,
        entry_widget_class=entry_widget_class,
        selection_mode=selection_mode,
        orientation=orientation,
        entry_width=entry_width,
        entry_height=entry_height,
        horizontal_entry_spacing=horizontal_entry_spacing,
        vertical_entry_spacing=vertical_entry_spacing,
        preview_entries=tuple(preview_entries),
        optional_binding=bool(data.get("optional_binding", False)),
        core_role=core_role,
        children=children,
    )


def _validate_generated_ags_plugin_reference(class_path: str | None, path: str) -> None:
    if class_path is None:
        return
    if class_path.startswith(GENERATED_AGS_FORBIDDEN_ALIAS_PREFIXES):
        raise ValidationError("schema_error", f"{path} for generated AGS project widgets may only reference AGSUI/Core plugin widgets.")


def _validate_generated_ags_entry_widget_class(entry_widget_class: str | None, path: str) -> None:
    if entry_widget_class is None:
        return
    if entry_widget_class.startswith("/AccelByteUITools/AGSUI/"):
        raise ValidationError("schema_error", f"{path} for generated AGS project widgets must reference a project-owned entry widget, not an AGSUI plugin widget.")


def _validate_generated_ags_widget_type(widget_type: str, path: str) -> None:
    if widget_type in GENERATED_AGS_FORBIDDEN_NATIVE_CONTROL_TYPES:
        allowed = ", ".join(sorted(GENERATED_AGS_REQUIRED_CORE_CONTROL_TYPES))
        raise ValidationError(
            "schema_error",
            f"{path}.type '{widget_type}' is not allowed for generated AGS project widgets. Use AGSUI/Core semantic controls instead: {allowed}.",
        )


def _validate_generated_ags_editable_text_style(data: dict[str, Any], path: str) -> None:
    style = data.get("style")
    if not isinstance(style, dict):
        raise ValidationError("schema_error", f"{path}.style is required for generated AGS EditableTextBox widgets.")
    required_style_keys = {
        "background_color",
        "color",
        "hint_color",
        "corner_radius",
        "border_color",
        "border_width",
    }
    missing = sorted(required_style_keys - set(style))
    if missing:
        joined = ", ".join(missing)
        raise ValidationError("schema_error", f"{path}.style is missing generated AGS input style keys: {joined}.")
    if "padding" not in data:
        raise ValidationError("schema_error", f"{path}.padding is required for generated AGS EditableTextBox widgets.")


def _validate_generated_ags_theme_tokens(
    data: dict[str, Any],
    widget_type: str,
    name: str,
    class_path: str | None,
    path: str,
    style_mode: str,
) -> None:
    tokens = load_theme_tokens()
    style = data.get("style")
    if isinstance(style, dict):
        for key, value in style.items():
            if key in CONTROL_STYLE_KEYS and isinstance(value, list):
                try:
                    color_tuple = tuple(float(channel) for channel in value[:4])
                except (TypeError, ValueError):
                    continue
                if color_tuple in STALE_DARK_COLORS:
                    raise ValidationError("schema_error", f"{path}.style.{key} contains a stale dark-theme color.")

    if widget_type == "TextBlock" and isinstance(style, dict) and "color" in style:
        _require_token_value(style["color"], tokens["colors"]["text"]["primary"], f"{path}.style.color")
    elif widget_type == "EditableTextBox":
        _require_token_style(style, tokens["presets"]["input"], f"{path}.style")
        _require_token_value(data.get("padding"), tokens["spacing"]["controlPadding"], f"{path}.padding")
    elif widget_type == "Button":
        preset = tokens["presets"][_button_preset_name(widget_type, name, class_path)]
        _require_token_style(style, preset, f"{path}.style")
        if "padding" in data:
            _require_token_value(data.get("padding"), tokens["spacing"]["controlPadding"], f"{path}.padding")
    elif widget_type == "Border" and isinstance(style, dict):
        preset = tokens["presets"][_border_preset_name(name)]
        if path == "root":
            _require_generated_panel_style(style, preset, f"{path}.style", style_mode)
        else:
            _require_token_style(style, preset, f"{path}.style")

    if widget_type in {"ListView", "TileView"}:
        _require_token_value(data.get("horizontal_entry_spacing"), tokens["spacing"]["entrySpacing"], f"{path}.horizontal_entry_spacing")
        _require_token_value(data.get("vertical_entry_spacing"), tokens["spacing"]["entrySpacing"], f"{path}.vertical_entry_spacing")


def _require_token_style(style: Any, preset: dict[str, Any], path: str) -> None:
    if not isinstance(style, dict):
        raise ValidationError("schema_error", f"{path} is required for generated AGS themed widgets.")
    for key, expected in preset.items():
        if key not in style:
            raise ValidationError("schema_error", f"{path} is missing token style key: {key}.")
        _require_token_value(style[key], expected, f"{path}.{key}")


def _require_generated_panel_style(style: Any, preset: dict[str, Any], path: str, style_mode: str) -> None:
    if not isinstance(style, dict):
        raise ValidationError("schema_error", f"{path} is required for generated AGS themed widgets.")
    for key, expected in preset.items():
        if key not in style:
            raise ValidationError("schema_error", f"{path} is missing token style key: {key}.")
        if key == "background_color":
            if _same_value(style[key], PROJECT_PANEL_BACKGROUND_COLOR) or _same_value(style[key], expected):
                continue
            expected = PROJECT_PANEL_BACKGROUND_COLOR
        _require_token_value(style[key], expected, f"{path}.{key}")


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(
            isinstance(actual_value, (int, float))
            and not isinstance(actual_value, bool)
            and abs(float(actual_value) - float(expected_value)) <= 0.000001
            for actual_value, expected_value in zip(actual, expected)
        )
    return actual == expected


def _require_token_value(actual: Any, expected: Any, path: str) -> None:
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValidationError("schema_error", f"{path} must match theme token value {expected}.")
        for actual_value, expected_value in zip(actual, expected):
            if not isinstance(actual_value, (int, float)) or isinstance(actual_value, bool):
                raise ValidationError("schema_error", f"{path} must contain numeric theme token values.")
            if abs(float(actual_value) - float(expected_value)) > 0.000001:
                raise ValidationError("schema_error", f"{path} must match theme token value {expected}.")
        return
    if isinstance(expected, (int, float)):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) or abs(float(actual) - float(expected)) > 0.000001:
            raise ValidationError("schema_error", f"{path} must match theme token value {expected}.")
        return
    if actual != expected:
        raise ValidationError("schema_error", f"{path} must match theme token value {expected}.")


def _button_preset_name(widget_type: str, name: str, class_path: str | None) -> str:
    combined = f"{widget_type} {name} {class_path or ''}".casefold()
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


def _is_collection_entry_asset_path(asset_path: str) -> bool:
    asset_name = asset_path.rsplit("/", 1)[-1]
    compact = re.sub(r"[^a-z0-9]", "", asset_name.casefold())
    return (
        compact.endswith(("entry", "row", "card", "tileitem", "listitem", "entrywidget", "rowwidget", "cardwidget"))
        or any(keyword in compact for keyword in ("itemcard", "entrywidget", "rowwidget", "cardwidget"))
    )


_ENTRY_ROW_STYLE_AGSUI: dict[str, Any] = {
    "background_color": [0.980392, 0.988235, 0.996078, 1.0],   # near-white; dark text readable
    "corner_radius": 8,
    "border_color": [0.31, 0.36, 0.43, 1.0],
    "border_width": 1,
}
_ENTRY_ROW_STYLE_PROJECT: dict[str, Any] = {
    "background_color": [0.0, 0.0, 0.0, 0.1],                  # transparent black; any text color
    "corner_radius": 8,
    "border_color": [0.31, 0.36, 0.43, 1.0],
    "border_width": 1,
}
_ENTRY_ROW_PADDING: tuple[float, float, float, float] = (12.0, 8.0, 12.0, 8.0)


def _normalize_entry_spec_root(spec: WidgetSpec) -> WidgetSpec:
    """Auto-inject a RowBackground Border wrapper for collection entry specs that lack one.

    style_mode controls the background color:
    - "agsui"            -> near-white (matches AGSUI list row components, dark text)
    - "project" / "auto" -> transparent black (safe with any text color scheme)
    """
    if not _is_collection_entry_asset_path(spec.asset_path):
        return spec
    root = spec.root
    lowered = root.name.casefold()
    if root.type == "Border" and any(k in lowered for k in ("row", "card", "background", "item")):
        return spec
    row_style = _ENTRY_ROW_STYLE_AGSUI if spec.style_mode == "agsui" else _ENTRY_ROW_STYLE_PROJECT
    wrapper = WidgetNode(
        type="Border",
        name="RowBackground",
        style=dict(row_style),
        padding=_ENTRY_ROW_PADDING,
        children=(root,),
    )
    return WidgetSpec(
        asset_path=spec.asset_path,
        parent_class=spec.parent_class,
        root=wrapper,
        ui_mode=spec.ui_mode,
        style_mode=spec.style_mode,
        project_class_mapping=dict(spec.project_class_mapping),
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


def _optional_style(data: dict[str, Any], key: str, path: str) -> dict[str, Any]:
    style = _optional_object(data, key, path)
    for color_key in ("color", "background_color", "hint_color", "border_color", "hover_color", "pressed_color"):
        if color_key in style:
            _validate_color_array(style[color_key], f"{path}.{key}.{color_key}")
    for number_key in ("corner_radius", "border_width"):
        if number_key in style:
            value = style[number_key]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ValidationError("schema_error", f"{path}.{key}.{number_key} must be a non-negative number.")
    return style


def _optional_margin(data: dict[str, Any], key: str, path: str) -> tuple[float, float, float, float] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise ValidationError("schema_error", f"{path}.{key} must be a four-number margin array.")
    channels: list[float] = []
    for channel in value:
        if not isinstance(channel, (int, float)) or isinstance(channel, bool) or channel < 0:
            raise ValidationError("schema_error", f"{path}.{key} must contain non-negative numeric values.")
        channels.append(float(channel))
    return (channels[0], channels[1], channels[2], channels[3])


def _validate_color_array(value: Any, path: str) -> None:
    if not isinstance(value, list) or len(value) < 4:
        raise ValidationError("schema_error", f"{path} must be an RGBA array.")
    for channel in value[:4]:
        if not isinstance(channel, (int, float)) or isinstance(channel, bool):
            raise ValidationError("schema_error", f"{path} must contain numeric RGBA values.")


def _optional_bool(data: dict[str, Any], key: str, path: str) -> bool:
    value = data.get(key, False)
    if not isinstance(value, bool):
        raise ValidationError("schema_error", f"{path}.{key} must be a boolean.")
    return value


def _optional_enum(data: dict[str, Any], key: str, path: str, allowed: set[str]) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("schema_error", f"{path}.{key} must be a string.")
    normalized = value.casefold()
    if normalized not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValidationError("schema_error", f"{path}.{key} must be one of: {options}.")
    return normalized


def _optional_positive_number(data: dict[str, Any], key: str, path: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValidationError("schema_error", f"{path}.{key} must be a positive number.")
    return float(value)


def _optional_non_negative_number(data: dict[str, Any], key: str, path: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValidationError("schema_error", f"{path}.{key} must be a non-negative number.")
    return float(value)


def _optional_array(data: dict[str, Any], key: str, path: str) -> list[Any]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("schema_error", f"{path}.{key} must be an array.")
    return value
