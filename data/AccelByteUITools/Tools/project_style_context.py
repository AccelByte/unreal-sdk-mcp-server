from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = 1
STYLE_CONTEXT_FILENAME = "project_style_context.json"
STYLE_APPROVAL_FILENAME = "project_style_context.approved.json"
GENERATED_COMPONENTS_REGISTRY_FILENAME = "generated_project_components.json"
GENERATED_COMPONENTS_ASSET_PREFIX = "/Game/AGS/UI/Components/"
GENERATED_WIDGETS_REGISTRY_KEY = "__generated_widgets"
VALID_GENERATED_PROJECT_CLASS_REFERENCE = re.compile(
    r"^/Game/(?:[A-Za-z0-9_]+/)*UI/(?:Generated|Components)/(?:[A-Za-z0-9_]+/)*"
    r"([A-Za-z_][A-Za-z0-9_]*)\.\1_C$"
)

UI_MODULE_NAMES = {"UMG", "CommonUI", "Slate", "SlateCore"}
SOURCE_EXTENSIONS = {".h", ".hpp", ".cpp", ".cc", ".cxx", ".cs"}
SPEC_EXTENSIONS = {".json", ".md", ".ini", ".uplugin", ".uproject", ".Build.cs"}
ASSET_EXTENSIONS = {".uasset"}
FINGERPRINT_EXTENSIONS = SOURCE_EXTENSIONS | SPEC_EXTENSIONS | ASSET_EXTENSIONS

DERIVED_CLASS_PATTERNS = {
    "user_widget": re.compile(r"class\s+\w+_API\s+(U\w+)\s*:\s*public\s+UUserWidget|class\s+(U\w+)\s*:\s*public\s+UUserWidget"),
    "common_activatable": re.compile(
        r"class\s+\w+_API\s+(U\w+)\s*:\s*public\s+(?:UCommonActivatableWidget|UAGSCommonActivatableBase)"
        r"|class\s+(U\w+)\s*:\s*public\s+(?:UCommonActivatableWidget|UAGSCommonActivatableBase)"
    ),
    "common_button": re.compile(r"class\s+\w+_API\s+(U\w+)\s*:\s*public\s+UCommonButtonBase|class\s+(U\w+)\s*:\s*public\s+UCommonButtonBase"),
    "common_text": re.compile(r"class\s+\w+_API\s+(U\w+)\s*:\s*public\s+UCommonTextBlock|class\s+(U\w+)\s*:\s*public\s+UCommonTextBlock"),
}

COMMON_UI_FALLBACK_PARENT_CLASSES = {
    "/Script/AccelByteUITools.AGSCommonActivatableBase",
    "/Script/CommonUI.CommonActivatableWidget",
}

ROLE_KEYWORDS = {
    "primary_button": ("primary", "confirm", "submit", "continue", "play", "start"),
    "secondary_button": ("secondary", "cancel", "back", "small"),
    "danger_button": ("danger", "delete", "remove", "quit", "warning"),
    "tab_button": ("tab",),
    "body_text": ("body", "paragraph", "caption", "label", "description"),
    "title_text": ("title", "heading", "header"),
    "warning_text": ("warning", "error", "danger"),
    "panel": ("panel", "container", "surface"),
    "list_row": ("listrow", "list_row", "row", "entry", "card"),
    "modal": ("modal", "popup", "dialog"),
    "input": ("input", "search", "password", "textbox", "text_input"),
    "state_widget": ("loading", "empty", "error", "status", "state"),
}

BUTTON_ROLES = {"primary_button", "secondary_button", "danger_button", "tab_button"}
TEXT_ROLES = {"body_text", "title_text", "warning_text"}
LIST_ROLES = {"list_row"}
INPUT_ROLES = {"input"}
RUNTIME_COLLECTION_KEYWORDS = {
    "leaderboard",
    "friends",
    "party",
    "inventory",
    "notifications",
    "store",
    "achievements",
    "sessions",
    "entitlements",
}
COLLECTION_RECIPE_INTENTS = {
    "leaderboard": {
        "keywords": {"leaderboard", "rank", "score"},
        "required_groups": ({"rank", "position", "place"}, {"score", "points", "value"}, {"player", "name", "displayname", "username"}),
        "description": "leaderboard entry containing rank, player name, and score fields",
    },
    "store": {
        "keywords": {"store", "catalog", "catalogue", "shop", "item", "sku", "price"},
        "required_groups": ({"item", "title", "name"}, {"price", "cost", "currency", "amount"}),
        "description": "store item entry/card containing item name and price/cost fields",
    },
    "achievements": {
        "keywords": {"achievement", "achievements", "trophy", "progress"},
        "required_groups": ({"achievement", "title", "name"}, {"progress", "percent", "status", "unlocked"}),
        "description": "achievement entry/card containing title/name and progress/status fields",
    },
    "friends": {
        "keywords": {"friend", "friends", "social"},
        "required_groups": ({"player", "friend", "name", "displayname", "username"}, {"status", "presence", "online"}),
        "description": "friend entry containing player identity and presence/status fields",
    },
    "sessions": {
        "keywords": {"session", "sessions", "server", "match"},
        "required_groups": ({"session", "server", "match", "name"}, {"players", "slots", "region", "status"}),
        "description": "session entry containing session/server identity and player/status fields",
    },
    "entitlements": {
        "keywords": {"entitlement", "entitlements", "owned", "inventory"},
        "required_groups": ({"entitlement", "item", "name"}, {"status", "owned", "quantity", "expires"}),
        "description": "entitlement entry containing item identity and ownership/status fields",
    },
    "notifications": {
        "keywords": {"notification", "notifications", "inbox", "news"},
        "required_groups": ({"title", "subject", "message"}, {"time", "date", "status", "body"}),
        "description": "notification/news entry containing title/message and time/status/body fields",
    },
}
AGS_STATE_ATOM_TYPES = {"AGSLoadingIndicator", "AGSEmptyState", "AGSErrorState", "AGSStatusMessage"}

CORE_COMPONENT_ROLES: dict[str, dict[str, Any]] = {
    "state_loading": {
        "description": "Loading / in-progress state panel",
        "ags_aliases": ["AGSLoadingIndicator"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator.WBP_AGS_LoadingIndicator_C",
        "keywords": {"loading", "spinner", "progress", "busy", "wait"},
        "generated_asset_name": "WBP_AGS_ProjectLoadingPanel",
        "template": "state_loading",
    },
    "state_empty": {
        "description": "Empty state / no-data panel",
        "ags_aliases": ["AGSEmptyState"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState.WBP_AGS_EmptyState_C",
        "keywords": {"empty", "nodata", "placeholder", "noresult"},
        "generated_asset_name": "WBP_AGS_ProjectEmptyPanel",
        "template": "state_empty",
    },
    "state_error": {
        "description": "Error state panel with optional retry",
        "ags_aliases": ["AGSErrorState"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState.WBP_AGS_ErrorState_C",
        "keywords": {"error", "fail", "failed", "retry", "offline"},
        "generated_asset_name": "WBP_AGS_ProjectErrorPanel",
        "template": "state_error",
    },
    "state_idle": {
        "description": "Idle / status message panel",
        "ags_aliases": ["AGSStatusMessage"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C",
        "keywords": {"status", "idle", "message", "info", "hint"},
        "generated_asset_name": "WBP_AGS_ProjectStatusPanel",
        "template": "state_idle",
    },
    "icon_button": {
        "description": "Icon-only button",
        "ags_aliases": ["AGSIconButton"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_IconButton.WBP_AGS_IconButton_C",
        "keywords": {"icon", "icon_btn", "iconbtn", "iconbutton"},
        "generated_asset_name": "WBP_AGS_ProjectIconButton",
        "template": None,
    },
    "text_input": {
        "description": "Single-line text input field",
        "ags_aliases": ["AGSTextInput"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput.WBP_AGS_TextInput_C",
        "keywords": {"textinput", "text_input", "editbox"},
        "generated_asset_name": "WBP_AGS_ProjectTextInput",
        "template": None,
    },
    "password_input": {
        "description": "Password input field",
        "ags_aliases": ["AGSPasswordInput"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_PasswordInput.WBP_AGS_PasswordInput_C",
        "keywords": {"password", "passinput", "passwordfield"},
        "generated_asset_name": "WBP_AGS_ProjectPasswordInput",
        "template": None,
    },
    "search_input": {
        "description": "Search input field",
        "ags_aliases": ["AGSSearchInput"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_SearchInput.WBP_AGS_SearchInput_C",
        "keywords": {"search", "searchbox", "searchinput"},
        "generated_asset_name": "WBP_AGS_ProjectSearchInput",
        "template": None,
    },
    "badge": {
        "description": "Badge / tag atom",
        "ags_aliases": ["AGSBadge"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_Badge.WBP_AGS_Badge_C",
        "keywords": {"badge", "tag", "label_badge"},
        "generated_asset_name": "WBP_AGS_ProjectBadge",
        "template": None,
    },
    "avatar": {
        "description": "User avatar widget",
        "ags_aliases": ["AGSAvatar"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_Avatar.WBP_AGS_Avatar_C",
        "keywords": {"avatar", "profile_pic", "user_icon"},
        "generated_asset_name": "WBP_AGS_ProjectAvatar",
        "template": None,
    },
    "divider": {
        "description": "Visual separator / divider",
        "ags_aliases": ["AGSDivider"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_Divider.WBP_AGS_Divider_C",
        "keywords": {"divider", "separator"},
        "generated_asset_name": "WBP_AGS_ProjectDivider",
        "template": None,
    },
    "currency_pill": {
        "description": "Currency / coin display pill",
        "ags_aliases": ["AGSCurrencyPill"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CurrencyPill.WBP_AGS_CurrencyPill_C",
        "keywords": {"currency", "coin", "gem", "credit"},
        "generated_asset_name": "WBP_AGS_ProjectCurrencyPill",
        "template": None,
    },
    "section_header": {
        "description": "Section heading / group title",
        "ags_aliases": ["AGSSectionHeader"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_SectionHeader.WBP_AGS_SectionHeader_C",
        "keywords": {"section", "section_header", "group_title"},
        "generated_asset_name": "WBP_AGS_ProjectSectionHeader",
        "template": None,
    },
    "key_value_row": {
        "description": "Key-value stat row",
        "ags_aliases": ["AGSKeyValueRow"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow.WBP_AGS_KeyValueRow_C",
        "keywords": {"keyvalue", "key_value", "stat_row"},
        "generated_asset_name": "WBP_AGS_ProjectKeyValueRow",
        "template": None,
    },
    "toast": {
        "description": "Toast / transient notification widget",
        "ags_aliases": ["AGSToast"],
        "agsui_fallback": "/AccelByteUITools/AGSUI/Core/WBP_AGS_Toast.WBP_AGS_Toast_C",
        "keywords": {"toast", "notification_toast", "snack"},
        "generated_asset_name": "WBP_AGS_ProjectToast",
        "template": None,
    },
}

AGS_ALIAS_TO_CORE_ROLE: dict[str, str] = {
    alias: role
    for role, info in CORE_COMPONENT_ROLES.items()
    for alias in info["ags_aliases"]
}

STRUCTURAL_CONTAINER_TYPES = {
    "Border", "Overlay", "VerticalBox", "HorizontalBox",
    "WidgetSwitcher", "SizeBox", "SafeZone", "ScaleBox",
    "UniformGridPanel", "WrapBox", "CanvasPanel",
    "AGSStatusMessage", "AGSLoadingIndicator", "AGSEmptyState",
    "AGSErrorState", "AGSBasePanel", "AGSModalPanel",
    "TextBlock", "Image", "Spacer", "Button", "EditableTextBox",
    "AGSBaseButton", "AGSButton", "AGSSecondaryButton", "AGSDangerButton", "AGSIconButton",
    "AGSTextInput", "AGSPasswordInput", "AGSSearchInput",
    "AGSBadge", "AGSAvatar", "AGSDivider", "AGSCurrencyPill",
    "AGSSectionHeader", "AGSKeyValueRow", "AGSToast",
}
ENFORCED_ROLE_ORDER = (
    "primary_button",
    "secondary_button",
    "danger_button",
    "tab_button",
    "body_text",
    "title_text",
    "warning_text",
    "input",
    "list_row",
    "panel",
    "modal",
    "state_widget",
)
PLUGIN_FALLBACK_PREFIX = "/AccelByteUITools/"
LIKELY_UI_PATH_PARTS = {
    "ui",
    "uis",
    "umg",
    "hud",
    "widget",
    "widgets",
    "commonui",
    "common_ui",
    "menu",
    "menus",
    "frontend",
    "interface",
    "styles",
}
NON_UI_PATH_PARTS = {
    "audio",
    "sound",
    "sounds",
    "soundwaves",
    "music",
    "materials",
    "material",
    "meshes",
    "mesh",
    "textures",
    "texture",
    "input",
    "inputs",
    "gamedata",
    "data",
    "datatables",
    "gamemodes",
    "game_modes",
    "crates",
    "ships",
}


class StyleContextError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


@dataclass(frozen=True)
class StyleContextPaths:
    context_path: Path
    approval_path: Path


def style_context_paths(project: str | Path) -> StyleContextPaths:
    root = project_root_from_project(project)
    config_dir = root / "Config" / "AccelByteUITools"
    return StyleContextPaths(
        context_path=config_dir / STYLE_CONTEXT_FILENAME,
        approval_path=config_dir / STYLE_APPROVAL_FILENAME,
    )


def project_root_from_project(project: str | Path) -> Path:
    project_path = Path(project).resolve()
    if project_path.suffix.lower() == ".uproject":
        return project_path.parent
    return project_path


def legacy_style_context_paths(project: str | Path) -> StyleContextPaths:
    root = project_root_from_project(project)
    saved_dir = root / "Saved" / "AccelByteUITools"
    return StyleContextPaths(
        context_path=saved_dir / STYLE_CONTEXT_FILENAME,
        approval_path=saved_dir / STYLE_APPROVAL_FILENAME,
    )


def discover_project_style(project: str | Path) -> dict[str, Any]:
    project_root = project_root_from_project(project)
    files = _iter_relevant_files(project_root)
    source_files = [path for path in files if path.suffix in SOURCE_EXTENSIONS]
    asset_files = [path for path in files if path.suffix in ASSET_EXTENSIONS]
    asset_files.extend(_iter_plugin_fallback_asset_files(project_root))
    spec_files = [path for path in files if path.suffix in SPEC_EXTENSIONS]

    modules = _discover_modules(project_root, spec_files)
    classes = _discover_source_classes(project_root, source_files)
    widget_assets = _discover_widget_assets(project_root, asset_files)
    style_assets = _discover_style_assets(project_root, asset_files + spec_files)
    registry = load_generated_components_registry(project_root)
    widget_assets.extend(_registry_widget_assets(registry))
    semantic_roles = _build_semantic_roles(widget_assets, style_assets, classes)
    enforced_roles = _build_enforced_roles(widget_assets, style_assets, classes, registry, project_root)
    ui_backend = _detect_ui_backend(modules, classes, widget_assets, style_assets)
    warnings = _build_warnings(ui_backend, semantic_roles, style_assets, enforced_roles)
    confidence = _confidence(ui_backend, semantic_roles, warnings)
    core_component_roles = _core_component_candidates(widget_assets, registry)

    context = {
        "schema_version": SCHEMA_VERSION,
        "project_root": str(project_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_fingerprint": _fingerprint(project_root, files),
        "ui_backend": ui_backend,
        "confidence": confidence,
        "enabled_ui_modules": sorted(modules),
        "source_classes": classes,
        "semantic_roles": semantic_roles,
        "enforced_roles": enforced_roles,
        "core_component_roles": core_component_roles,
        "allowed_class_references": _allowed_class_references(classes, widget_assets, registry),
        "project_class_mapping": _build_project_class_mapping(classes, widget_assets, registry, project_root),
        "allowed_style_references": _allowed_style_references(style_assets),
        "discouraged_raw_widget_types": _discouraged_raw_widget_types(ui_backend, semantic_roles, enforced_roles),
        "candidate_widget_assets": widget_assets[:80],
        "candidate_style_assets": style_assets[:80],
        "discovery_warnings": warnings,
        "unresolved_ambiguities": _ambiguities(semantic_roles, enforced_roles),
        "validation_rules": _validation_rules(ui_backend, semantic_roles, enforced_roles),
    }
    return context


def write_style_context(context: dict[str, Any], project: str | Path) -> Path:
    paths = style_context_paths(project)
    paths.context_path.parent.mkdir(parents=True, exist_ok=True)
    paths.context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")
    return paths.context_path


def approve_style_context(context: dict[str, Any], project: str | Path) -> Path:
    paths = style_context_paths(project)
    paths.approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval = {
        "schema_version": SCHEMA_VERSION,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "project_root": context["project_root"],
        "source_fingerprint": context["source_fingerprint"],
        "ui_backend": context["ui_backend"],
        "confidence": context["confidence"],
    }
    paths.approval_path.write_text(json.dumps(approval, indent=2), encoding="utf-8")
    return paths.approval_path


def load_style_context(project: str | Path) -> dict[str, Any] | None:
    for path in (style_context_paths(project).context_path, legacy_style_context_paths(project).context_path):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_style_approval(project: str | Path) -> dict[str, Any] | None:
    for path in (style_context_paths(project).approval_path, legacy_style_context_paths(project).approval_path):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def approval_status(context: dict[str, Any], project: str | Path) -> dict[str, Any]:
    approval = load_style_approval(project)
    reasons: list[str] = []
    if approval is None:
        reasons.append("no approved style context exists")
        if context.get("confidence") == "low":
            reasons.append("style discovery confidence is low")
        if context.get("unresolved_ambiguities"):
            reasons.append("style discovery found unresolved ambiguities")
    elif approval.get("source_fingerprint") != context.get("source_fingerprint"):
        reasons.append("approved style context fingerprint is stale")
    return {"approved": not reasons, "reasons": reasons, "approval": approval}


def ensure_approved_style_context(project: str | Path) -> dict[str, Any]:
    context = discover_project_style(project)
    write_style_context(context, project)
    status = approval_status(context, project)
    if not status["approved"]:
        raise StyleContextError(
            "style_context_approval_required",
            "Project style context must be reviewed and approved before generation.",
            {"approval_reasons": status["reasons"], "findings": style_findings(context)},
        )
    return context


def style_findings(context: dict[str, Any]) -> dict[str, Any]:
    roles = context.get("semantic_roles", {})
    enforced_roles = context.get("enforced_roles", {})
    return {
        "ui_backend": context.get("ui_backend"),
        "confidence": context.get("confidence"),
        "enabled_ui_modules": context.get("enabled_ui_modules", []),
        "top_widget_roles": {role: values[:3] for role, values in roles.get("widgets", {}).items() if values},
        "top_style_roles": {role: values[:3] for role, values in roles.get("styles", {}).items() if values},
        "enforced_roles": {
            role: {
                "default": values.get("default"),
                "project_candidates": values.get("project_candidates", [])[:3],
                "fallback_candidates": values.get("fallback_candidates", [])[:3],
            }
            for role, values in enforced_roles.items()
            if values.get("project_candidates") or values.get("fallback_candidates")
        },
        "validation_rules": context.get("validation_rules", []),
        "warnings": context.get("discovery_warnings", []),
        "unresolved_ambiguities": context.get("unresolved_ambiguities", []),
    }


def extra_parent_classes_from_context(context: dict[str, Any]) -> frozenset[str]:
    """Return discovered project widget parent classes accepted by widget specs."""
    result: set[str] = set()
    source_classes = context.get("source_classes", {})
    for role in ("user_widget", "common_activatable", "list_entry_compatible", "common_button", "common_text"):
        for entry in source_classes.get(role, []):
            result.update(_script_class_path_variants_for_source(entry))
    return frozenset(result)


def _should_enforce_project_style(context: dict[str, Any], style_mode: str) -> bool:
    if style_mode == "agsui":
        return False
    if style_mode == "project":
        return True
    return context.get("confidence", "high") in {"medium", "high"}


def _normalize_spec_nodes(spec: dict[str, Any], context: dict[str, Any]) -> list[str]:
    """Mutate spec nodes in-place before validation. Returns informational notes.

    Three auto-fixes are applied:
    1a. State panel nodes: auto-apply core_component_roles.<role>.resolved as class_path.
        Note: is_variable is NOT set to false — WidgetSwitcher children must remain
        is_variable:true (schema requirement). verify_failed for project-tier panels is a
        known limitation handled at the guidance level.
    1b. TextBlock nodes with text_style_class in mixed/CommonUI projects: inject
        class_path="/Script/CommonUI.CommonTextBlock" so the bridge Cast<UCommonTextBlock>
        succeeds in ApplyCommonTextStyle().
    1c. AGS state panel nodes inside WidgetSwitcher: auto-apply h_align=fill / v_align=fill
        slot so state panels fill the switcher rather than defaulting to top-left.
    """
    notes: list[str] = []
    ui_backend = context.get("ui_backend", "unknown")
    core_component_roles = context.get("core_component_roles", {})
    enforced_roles = context.get("enforced_roles", {})
    use_project_style = _should_enforce_project_style(context, str(spec.get("style_mode", "auto")))

    apply_common_text = ui_backend in ("mixed", "common_ui")
    has_text_styles = bool(
        _project_candidates_for_role(enforced_roles, "title_text", kind="style")
        or _project_candidates_for_role(enforced_roles, "body_text", kind="style")
    )
    common_text_class = "/Script/CommonUI.CommonTextBlock"

    for path, node in _walk_nodes(spec.get("root"), "root"):
        widget_type = str(node.get("type", ""))
        class_path = node.get("class_path")
        text_style_class = node.get("text_style_class")
        entry_widget_class = node.get("entry_widget_class")

        # Fix 1a: auto-apply core_component_roles resolved path for state panel nodes.
        # Agents may provide an explicit role marker for project-specific state widgets;
        # otherwise AGS state aliases are mapped to their matching core role.
        if core_component_roles:
            core_role = node.get("core_role") or node.get("_core_role")
            if not core_role and widget_type in AGS_STATE_ATOM_TYPES:
                core_role = AGS_ALIAS_TO_CORE_ROLE.get(widget_type)
            if core_role:
                role_info = core_component_roles.get(core_role, {})
                resolved = role_info.get("resolved")
                should_apply_core_resolution = use_project_style or role_info.get("resolution_tier") == "agsui_fallback"
                if should_apply_core_resolution and resolved and class_path != resolved:
                    node["class_path"] = resolved
                    notes.append(f"{path}: auto-applied {core_role} resolved → {resolved}")

        # Fix 1b: inject CommonTextBlock class_path for styled text nodes in CommonUI projects
        if (
            apply_common_text
            and has_text_styles
            and widget_type == "TextBlock"
            and isinstance(text_style_class, str)
            and not isinstance(class_path, str)
        ):
            node["class_path"] = common_text_class
            notes.append(
                f"{path}: injected class_path={common_text_class} "
                f"(mixed/CommonUI project — text_style_class requires UCommonTextBlock)"
            )

        if widget_type in {"ListView", "TileView", "TreeView"} and not isinstance(entry_widget_class, str):
            compatible = _compatible_project_candidates_for_role(enforced_roles, "list_row")
            recipe_intent = _collection_recipe_intent(spec, path, node)
            eligible = _recipe_compatible_candidates(compatible, recipe_intent) if recipe_intent else compatible
            if len(eligible) == 1:
                resolved_entry = eligible[0].get("class_path") or eligible[0].get("asset_path")
                if resolved_entry:
                    node["entry_widget_class"] = resolved_entry
                    suffix = f" for {recipe_intent}" if recipe_intent else ""
                    notes.append(f"{path}: auto-applied list_row entry_widget_class{suffix} -> {resolved_entry}")

    # Fix 1c: auto-apply fill slot to AGS state panel children of WidgetSwitcher.
    # Without an explicit slot, Unreal defaults WidgetSwitcher children to top-left.
    # AGSUI fallback state panels fill their slot and center content internally,
    # so h_align=fill / v_align=fill is the correct slot for all state atom types.
    for path, node in _walk_nodes(spec.get("root"), "root"):
        if str(node.get("type", "")) != "WidgetSwitcher":
            continue
        for i, child in enumerate(node.get("children", []) or []):
            if not isinstance(child, dict):
                continue
            child_type = str(child.get("type", ""))
            child_core_role = child.get("core_role") or child.get("_core_role")
            is_state_panel = child_type in AGS_STATE_ATOM_TYPES or bool(child_core_role)
            if not is_state_panel:
                continue
            slot = child.get("slot")
            if not isinstance(slot, dict):
                slot = {}
                child["slot"] = slot
            changed = False
            if slot.get("h_align") != "fill":
                slot["h_align"] = "fill"
                changed = True
            if slot.get("v_align") != "fill":
                slot["v_align"] = "fill"
                changed = True
            if changed:
                child_path = f"{path}.children[{i}]"
                notes.append(
                    f"{child_path}: auto-applied WidgetSwitcher slot → "
                    f"h_align=fill, v_align=fill ({child_type or child_core_role})"
                )

    return notes


def _normalize_spec_parent(spec: dict[str, Any], context: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not _is_generated_project_spec(spec):
        return notes
    if _is_collection_entry_spec(spec) and spec.get("ui_mode") == "common_ui":
        spec["ui_mode"] = "umg"
        notes.append("ui_mode: auto-applied umg for generated collection entry widget")
        return notes
    if spec.get("ui_mode") != "common_ui":
        return notes
    project_parents = _project_common_activatable_parent_classes(context)
    parent_class = str(spec.get("parent_class", ""))
    if parent_class in COMMON_UI_FALLBACK_PARENT_CLASSES and len(project_parents) == 1:
        spec["parent_class"] = project_parents[0]["class_path"]
        notes.append(f"parent_class: auto-applied project CommonUI parent -> {project_parents[0]['class_path']}")
    return notes


def validate_spec_against_style_context(spec: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    # Normalize spec nodes in-place before validation (fixes class_path for state panels
    # and injects CommonTextBlock class_path for styled text nodes).
    _normalize_spec_parent(spec, context)
    _normalize_spec_nodes(spec, context)

    ui_backend = context.get("ui_backend", "unknown")
    allowed_classes = set(context.get("allowed_class_references", []))
    # Trust resolved paths from core_component_roles — they were discovered from project assets.
    for role_info in context.get("core_component_roles", {}).values():
        resolved = role_info.get("resolved")
        if resolved:
            allowed_classes.add(resolved)
    allowed_styles = set(context.get("allowed_style_references", []))
    discouraged_raw_types = set(context.get("discouraged_raw_widget_types", []))
    enforced_roles = context.get("enforced_roles", {})
    core_component_roles = context.get("core_component_roles", {})
    is_generated_project_widget = _is_generated_project_spec(spec)
    use_project_style = _should_enforce_project_style(context, str(spec.get("style_mode", "auto")))

    spec_ui_mode = spec.get("ui_mode", "umg")
    if ui_backend == "umg" and spec_ui_mode == "common_ui":
        errors.append(_style_error("ui_backend_mismatch", "spec.ui_mode", "common_ui", "umg"))
    project_common_parents = _project_common_activatable_parent_classes(context)
    if (
        is_generated_project_widget
        and use_project_style
        and spec_ui_mode == "common_ui"
        and project_common_parents
        and str(spec.get("parent_class", "")) not in {entry["class_path"] for entry in project_common_parents}
    ):
        errors.append(
            _style_error(
                "project_parent_class_required",
                "parent_class",
                spec.get("parent_class"),
                "final project CommonUI script parent discovered from source; do not swap to AGSCommonActivatableBase/CommonActivatableWidget. Create or update the final C++ header, rerun style discovery/approval or accelbyte_ui_verify_backing_class, then do a full Build.bat rebuild for a new UCLASS before generation",
                role="common_activatable",
                recommended=project_common_parents[:5],
            )
        )
    if is_generated_project_widget and _is_collection_entry_spec(spec):
        parent_class = str(spec.get("parent_class", ""))
        compatible_classes = context.get("source_classes", {}).get("list_entry_compatible", [])
        if use_project_style and not _parent_class_matches_source_class(parent_class, compatible_classes):
            errors.append(
                _style_error(
                    "collection_entry_parent_required",
                    "parent_class",
                    parent_class,
                    "final project C++ entry class implementing IUserObjectListEntry; do not swap to UUserWidget or a generic AccelByteWarsWidgetEntry fallback. Create or update the final entry header, rerun style discovery/approval or accelbyte_ui_verify_backing_class, then do a full Build.bat rebuild for a new UCLASS before generation",
                    role="list_row",
                    recommended=[
                        {
                            "class_path": _script_class_path_for_source(entry),
                            "name": entry.get("name"),
                            "source": entry.get("source"),
                        }
                        for entry in compatible_classes[:5]
                    ],
                )
            )

    for path, node in _walk_nodes(spec.get("root"), "root"):
        widget_type = str(node.get("type", ""))
        class_path = node.get("class_path")
        button_style_class = node.get("button_style_class")
        text_style_class = node.get("text_style_class")
        style_asset = node.get("style_asset") or node.get("text_style") or node.get("button_style")

        if widget_type in discouraged_raw_types and not class_path and not text_style_class and not button_style_class:
            errors.append(
                _style_error(
                    "discouraged_raw_widget",
                    f"{path}.type",
                    widget_type,
                    "project-approved styled widget or class_path",
                )
            )
        if (
            isinstance(class_path, str)
            and class_path.startswith("/Game/")
            and allowed_classes
            and class_path not in allowed_classes
            and not _is_generated_project_class_reference(class_path)
        ):
            errors.append(_style_error("unknown_class_reference", f"{path}.class_path", class_path, "approved project class reference"))
        if (
            isinstance(node.get("entry_widget_class"), str)
            and node["entry_widget_class"].startswith("/Game/")
            and allowed_classes
            and node["entry_widget_class"] not in allowed_classes
            and not _is_generated_project_class_reference(node["entry_widget_class"])
        ):
            errors.append(
                _style_error(
                    "unknown_class_reference",
                    f"{path}.entry_widget_class",
                    node["entry_widget_class"],
                    "approved project class reference",
                )
            )
        for field_name, field_value in (
            ("button_style_class", button_style_class),
            ("text_style_class", text_style_class),
            ("style_asset", style_asset),
        ):
            if isinstance(field_value, str) and field_value.startswith("/Game/") and allowed_styles and field_value not in allowed_styles:
                errors.append(_style_error("unknown_style_reference", f"{path}.{field_name}", field_value, "approved project style reference"))

        if not is_generated_project_widget:
            continue
        if not use_project_style:
            continue

        if _is_button_node(widget_type, class_path):
            role = _button_role_for_node(node)
            project_candidates = _project_candidates_for_role(enforced_roles, role)
            project_button_widgets = _project_candidates_for_role(enforced_roles, role, kind="widget")
            project_button_styles = _project_candidates_for_role(enforced_roles, role, kind="style")
            if role == "tab_button" and not project_candidates and not _uses_project_reference(class_path):
                errors.append(
                    _style_error(
                        "project_tab_button_required",
                        f"{path}.class_path",
                        class_path,
                        "project tab button widget or project tab button_style_class; create/generate this component before the main tabbed widget",
                        role=role,
                    )
                )
            if project_candidates:
                if isinstance(class_path, str) and _is_plugin_fallback_path(class_path):
                    errors.append(
                        _style_error(
                            "project_button_required",
                            f"{path}.class_path",
                            class_path,
                            "approved project button widget or project button_style_class",
                            role=role,
                            recommended=project_candidates[:5],
                        )
                    )
                if not _uses_project_reference(class_path) and not isinstance(button_style_class, str):
                    errors.append(
                        _style_error(
                            "missing_project_button_style",
                            f"{path}.button_style_class",
                            None,
                            "approved project button_style_class",
                            role=role,
                            recommended=(project_button_styles or project_candidates)[:5],
                        )
                    )
                if (
                    isinstance(button_style_class, str)
                    and project_button_styles
                    and not _is_candidate_reference(button_style_class, project_button_styles)
                    and button_style_class not in allowed_styles
                ):
                    errors.append(
                        _style_error(
                            "unknown_project_button_style",
                            f"{path}.button_style_class",
                            button_style_class,
                            "approved project button_style_class",
                            role=role,
                            recommended=project_button_styles[:5],
                        )
                    )
                all_project_button_widgets = _project_button_widget_candidates(enforced_roles)
                if (
                    _uses_project_reference(class_path)
                    and project_button_widgets
                    and not _is_candidate_reference(class_path, project_button_widgets)
                    and not _is_candidate_reference(class_path, all_project_button_widgets)
                ):
                    errors.append(
                        _style_error(
                            "unknown_project_button_widget",
                            f"{path}.class_path",
                            class_path,
                            "approved project button widget",
                            role=role,
                            recommended=project_button_widgets[:5],
                        )
                    )
        if _is_text_node(widget_type, class_path):
            role = _text_role_for_node(node)
            project_candidates = _project_candidates_for_role(enforced_roles, role, kind="style") or _project_candidates_for_role(
                enforced_roles, "body_text", kind="style"
            )
            if project_candidates and not isinstance(text_style_class, str):
                errors.append(
                    _style_error(
                        "missing_project_text_style",
                        f"{path}.text_style_class",
                        None,
                        "approved project text_style_class",
                        role=role,
                        recommended=project_candidates[:5],
                    )
                )
            if (
                isinstance(text_style_class, str)
                and project_candidates
                and not _is_candidate_reference(text_style_class, project_candidates)
                and text_style_class not in allowed_styles
            ):
                errors.append(
                    _style_error(
                        "unknown_project_text_style",
                        f"{path}.text_style_class",
                        text_style_class,
                        "approved project text_style_class",
                        role=role,
                        recommended=project_candidates[:5],
                    )
                )

        if _is_panel_node(widget_type, class_path):
            role = "panel"
            project_candidates = _project_candidates_for_role(enforced_roles, role, kind="widget")
            if isinstance(class_path, str) and _is_plugin_fallback_path(class_path) and "/FeatureBlocks/" in class_path:
                errors.append(
                    _style_error(
                        "project_panel_required",
                        f"{path}.class_path",
                        class_path,
                        "flat project-styled panel composition or approved project panel widget; do not embed AGS FeatureBlock panels in generated project widgets",
                        role=role,
                        recommended=project_candidates[:5],
                    )
                )
            if project_candidates and isinstance(class_path, str) and _is_plugin_fallback_path(class_path):
                errors.append(
                    _style_error(
                        "project_panel_required",
                        f"{path}.class_path",
                        class_path,
                        "approved project panel widget",
                        role=role,
                        recommended=project_candidates[:5],
                    )
                )

        entry_widget_class = node.get("entry_widget_class")
        has_runtime_collection_intent = _has_runtime_collection_intent(spec, path, node)
        collection_recipe_intent = _collection_recipe_intent(spec, path, node)
        list_row_project_candidates = _project_candidates_for_role(enforced_roles, "list_row")
        compatible_list_rows = _compatible_project_candidates_for_role(enforced_roles, "list_row")
        recipe_compatible_list_rows = _recipe_compatible_candidates(compatible_list_rows, collection_recipe_intent)
        unresolved_list_rows = _incompatible_or_unknown_project_candidates_for_role(enforced_roles, "list_row")
        recommended_list_rows = recipe_compatible_list_rows or compatible_list_rows or unresolved_list_rows or list_row_project_candidates

        if has_runtime_collection_intent and widget_type == "ScrollBox":
            errors.append(
                _style_error(
                    "runtime_collection_requires_virtualized_list",
                    f"{path}.type",
                    widget_type,
                    "ListView, TileView, or TreeView with an approved compatible project entry widget",
                    role="list_row",
                    recommended=recommended_list_rows[:5],
                )
            )
        if widget_type in {"ListView", "TileView", "TreeView"}:
            if isinstance(entry_widget_class, str) and _is_plugin_fallback_path(entry_widget_class):
                errors.append(
                    _style_error(
                        "project_list_entry_required",
                        f"{path}.entry_widget_class",
                        entry_widget_class,
                        "approved compatible project-owned entry/card widget; create/generate this component before the main collection widget",
                        role="list_row",
                        recommended=recommended_list_rows[:5],
                    )
                )
            if not compatible_list_rows:
                errors.append(
                    _style_error(
                        "no_compatible_project_list_entry",
                        f"{path}.entry_widget_class",
                        entry_widget_class,
                        "project list entry/card widget verified compatible with IUserObjectListEntry",
                        role="list_row",
                        recommended=unresolved_list_rows[:5],
                    )
                )
            elif collection_recipe_intent and not recipe_compatible_list_rows:
                expected = COLLECTION_RECIPE_INTENTS[collection_recipe_intent]["description"]
                errors.append(
                    _style_error(
                        "recipe_list_entry_required",
                        f"{path}.entry_widget_class",
                        entry_widget_class,
                        f"project-styled {expected}; generate or select an entry widget from the selected AGS recipe before composing this collection",
                        role="list_row",
                        recommended=compatible_list_rows[:5],
                    )
                )
            elif isinstance(entry_widget_class, str) and compatible_list_rows and not _is_candidate_reference(entry_widget_class, compatible_list_rows):
                errors.append(
                    _style_error(
                        "project_list_entry_required",
                        f"{path}.entry_widget_class",
                        entry_widget_class,
                        "approved compatible project list entry widget",
                        role="list_row",
                        recommended=compatible_list_rows[:5],
                    )
                )
            if (
                collection_recipe_intent
                and recipe_compatible_list_rows
                and isinstance(entry_widget_class, str)
                and not _is_candidate_reference(entry_widget_class, recipe_compatible_list_rows)
            ):
                expected = COLLECTION_RECIPE_INTENTS[collection_recipe_intent]["description"]
                errors.append(
                    _style_error(
                        "recipe_list_entry_required",
                        f"{path}.entry_widget_class",
                        entry_widget_class,
                        f"project-styled {expected}; do not use a generic or unrelated project entry for this recipe",
                        role="list_row",
                        recommended=recipe_compatible_list_rows[:5],
                    )
                )
        elif has_runtime_collection_intent and list_row_project_candidates and widget_type not in STRUCTURAL_CONTAINER_TYPES:
            # Exempt nodes that resolve to a known project widget via class_path — they are
            # structural references to named widgets, not generic unresolved placeholders.
            if not (class_path and class_path in allowed_classes):
                errors.append(
                    _style_error(
                        "runtime_collection_requires_virtualized_list",
                        f"{path}.type",
                        widget_type,
                        "ListView, TileView, or TreeView with an approved compatible project entry widget",
                        role="list_row",
                        recommended=recommended_list_rows[:5],
                    )
                )

        core_role = node.get("core_role") or node.get("_core_role")
        if not core_role and widget_type in AGS_STATE_ATOM_TYPES:
            core_role = AGS_ALIAS_TO_CORE_ROLE.get(widget_type)
        if isinstance(core_role, str) and core_role in {"state_loading", "state_empty", "state_error", "state_idle"}:
            role_info = core_component_roles.get(core_role, {})
            if role_info.get("resolution_tier") == "agsui_fallback":
                errors.append(
                    _style_error(
                        "project_core_widget_required",
                        f"{path}.core_role",
                        core_role,
                        "project/generated state panel component; call generate_project_core_widgets for state roles before the main stateful widget",
                        role=core_role,
                    )
                )

    return errors


def _iter_relevant_files(project_root: Path) -> list[Path]:
    ignored_parts = {"Binaries", "DerivedDataCache", "Intermediate", "Saved", ".git", ".vs", "__pycache__", ".pytest_cache", "AccelByteUITools"}
    if not project_root.exists():
        return []
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [name for name in dirnames if name not in ignored_parts]
        current = Path(dirpath)
        for filename in filenames:
            path = current / filename
            # AGS-generated Blueprint assets change on every generate call; exclude them
            # so they don't invalidate the style context approval fingerprint.
            rel = path.relative_to(project_root)
            if path.suffix in ASSET_EXTENSIONS and "AGS" in rel.parts and "Generated" in rel.parts and "UI" in rel.parts:
                continue
            if path.suffix in FINGERPRINT_EXTENSIONS or path.name.endswith(".Build.cs"):
                files.append(path)
    return sorted(files)


def _iter_plugin_fallback_asset_files(project_root: Path) -> list[Path]:
    plugin_content = project_root / "Plugins" / "AccelByteUITools" / "Content"
    if not plugin_content.exists():
        return []
    return sorted(path for path in plugin_content.rglob("*") if path.is_file() and path.suffix in ASSET_EXTENSIONS)


def _discover_modules(project_root: Path, files: list[Path]) -> set[str]:
    modules: set[str] = set()
    module_pattern = re.compile(r'"(UMG|CommonUI|Slate|SlateCore)"')
    plugin_pattern = re.compile(r'"Name"\s*:\s*"(UMG|CommonUI|Slate|SlateCore)"')
    for path in files:
        if path.suffix not in {".uproject", ".uplugin", ".cs", ".ini"} and not path.name.endswith(".Build.cs"):
            continue
        text = _read_text(path)
        modules.update(module_pattern.findall(text))
        modules.update(plugin_pattern.findall(text))
    if (project_root / "Content").exists():
        modules.add("UMG")
    return modules


def _discover_source_classes(project_root: Path, files: list[Path]) -> dict[str, list[dict[str, str]]]:
    classes: dict[str, list[dict[str, str]]] = {key: [] for key in DERIVED_CLASS_PATTERNS}
    class_name_pattern = re.compile(r"class\s+(?:\w+_API\s+)?(U\w+)\s*:")
    inheritance_pattern = re.compile(r"class\s+(?:\w+_API\s+)?(U\w+)\s*:\s*public\s+(\w+)")
    inheritance_entries: list[dict[str, str]] = []
    for path in files:
        text = _read_text(path)
        module = _module_name_for_source(project_root, path)
        for match in inheritance_pattern.finditer(text):
            inheritance_entries.append(
                {
                    "name": match.group(1),
                    "base": match.group(2),
                    "source": _rel(project_root, path),
                    "module": module,
                }
            )
        for role, pattern in DERIVED_CLASS_PATTERNS.items():
            for match in pattern.finditer(text):
                name = next(group for group in match.groups() if group)
                classes[role].append({"name": name, "source": _rel(project_root, path), "module": module})
        if "IUserObjectListEntry" in text or "UUserObjectListEntry" in text:
            for match in class_name_pattern.finditer(text):
                classes.setdefault("list_entry_compatible", []).append({"name": match.group(1), "source": _rel(project_root, path), "module": module})
    # Pre-seed known AGS plugin base classes as list_entry_compatible so that project
    # classes extending them are promoted by _add_transitive_source_classes without
    # requiring a manual IUserObjectListEntry include in each project header.
    _AGS_LIST_ENTRY_BASE_CLASSES = ["UAGSListRowBase", "UAGSLabelValueWidgetBase", "UAGSFeatureBlockBase"]
    existing_names = {entry["name"] for entry in classes.get("list_entry_compatible", [])}
    for cls in _AGS_LIST_ENTRY_BASE_CLASSES:
        if cls not in existing_names:
            classes.setdefault("list_entry_compatible", []).append({"name": cls, "source": "plugin", "module": "AccelByteUITools"})
    _add_transitive_source_classes(classes, inheritance_entries, "common_activatable")
    _add_transitive_source_classes(classes, inheritance_entries, "list_entry_compatible")
    return {role: values[:50] for role, values in classes.items() if values}


def _add_transitive_source_classes(
    classes: dict[str, list[dict[str, str]]],
    inheritance_entries: list[dict[str, str]],
    role: str,
) -> None:
    compatible_names = {entry["name"] for entry in classes.get(role, [])}
    compatible_names.update(name.removeprefix("U") for name in list(compatible_names))
    known_entries = {(entry["name"], entry["module"]) for entry in classes.get(role, [])}
    changed = True
    while changed:
        changed = False
        for entry in inheritance_entries:
            name = entry["name"]
            base = entry["base"]
            if name in compatible_names:
                continue
            if base in compatible_names or base.removeprefix("U") in compatible_names:
                key = (name, entry["module"])
                if key not in known_entries:
                    classes.setdefault(role, []).append(
                        {"name": name, "source": entry["source"], "module": entry["module"]}
                    )
                    known_entries.add(key)
                compatible_names.add(name)
                compatible_names.add(name.removeprefix("U"))
                changed = True


def _module_name_for_source(project_root: Path, path: Path) -> str:
    try:
        rel_parts = path.relative_to(project_root).parts
    except ValueError:
        rel_parts = path.parts
    if len(rel_parts) >= 2 and rel_parts[0] == "Source":
        return rel_parts[1]
    return "Project"


def _discover_widget_assets(project_root: Path, files: list[Path]) -> list[dict[str, str]]:
    assets = []
    for path in files:
        if not _is_likely_ui_asset(project_root, path):
            continue
        name = path.stem
        if _is_style_asset_name(name):
            continue
        roles = _widget_roles_for_name(name)
        if roles:
            asset_path = _asset_reference(project_root, path)
            assets.append(
                {
                    "asset_path": asset_path,
                    "class_path": _asset_class_reference(asset_path),
                    "name": name,
                    "roles": roles,
                    "candidate_type": _candidate_type(asset_path),
                }
            )
    return sorted(assets, key=lambda item: (item["roles"][0], item["asset_path"]))


def _discover_style_assets(project_root: Path, files: list[Path]) -> list[dict[str, str]]:
    assets = []
    for path in files:
        if path.suffix == ".uasset" and not _is_style_asset_name(path.stem) and not _is_likely_ui_asset(project_root, path):
            continue
        name = path.stem
        roles = _style_roles_for_name(name)
        if path.name == "theme_tokens.json":
            roles.append("theme_tokens")
        if roles:
            asset_path = _asset_reference(project_root, path)
            assets.append(
                {
                    "asset_path": asset_path,
                    "class_path": _asset_class_reference(asset_path) if path.suffix == ".uasset" else asset_path,
                    "name": name,
                    "roles": sorted(set(roles)),
                    "candidate_type": _candidate_type(asset_path),
                }
            )
    return sorted(assets, key=lambda item: (item["roles"][0], item["asset_path"]))


def _build_semantic_roles(
    widget_assets: list[dict[str, Any]],
    style_assets: list[dict[str, Any]],
    classes: dict[str, list[dict[str, str]]],
) -> dict[str, dict[str, list[str]]]:
    widget_roles: dict[str, list[str]] = {role: [] for role in ENFORCED_ROLE_ORDER}
    style_roles: dict[str, list[str]] = {role: [] for role in ENFORCED_ROLE_ORDER}
    class_roles: dict[str, list[str]] = {}

    for item in widget_assets:
        for role in item["roles"]:
            widget_roles.setdefault(role, []).append(item.get("class_path") or item["asset_path"])
    for item in style_assets:
        for role in item["roles"]:
            if role == "theme_tokens":
                continue
            style_roles.setdefault(role, []).append(item.get("class_path") or item["asset_path"])
    for source_role, values in classes.items():
        class_roles[source_role] = [item["name"] for item in values]

    return {
        "widgets": {role: values[:10] for role, values in widget_roles.items() if values},
        "styles": {role: values[:10] for role, values in style_roles.items() if values},
        "classes": class_roles,
    }


def _build_enforced_roles(
    widget_assets: list[dict[str, Any]],
    style_assets: list[dict[str, Any]],
    classes: dict[str, list[dict[str, str]]] | None = None,
    registry: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    compatible_list_class_names = {item["name"] for item in (classes or {}).get("list_entry_compatible", [])}
    for role in ENFORCED_ROLE_ORDER:
        project_candidates: list[dict[str, str]] = []
        fallback_candidates: list[dict[str, str]] = []
        for item in widget_assets + style_assets:
            if role not in item.get("roles", []):
                continue
            candidate = {
                "asset_path": item["asset_path"],
                "class_path": item.get("class_path") or item["asset_path"],
                "name": item["name"],
                "source": item.get("source") or ("project" if item.get("candidate_type") == "project" else "fallback"),
                "kind": "style" if item in style_assets else ("entry_widget" if role == "list_row" else "widget"),
            }
            if "list_entry_compatible" in item:
                candidate["list_entry_compatible"] = item["list_entry_compatible"]
            if "recipe_intents" in item:
                candidate["recipe_intents"] = item["recipe_intents"]
            if role == "list_row":
                candidate["list_entry_compatible"] = _list_entry_compatibility(candidate, compatible_list_class_names)
                candidate["recipe_intents"] = candidate.get("recipe_intents") or _entry_recipe_intents_for_name(item["name"])
            if item.get("candidate_type") == "project":
                project_candidates.append(candidate)
            else:
                fallback_candidates.append(candidate)
        if role == "list_row":
            for candidate in _registry_list_entry_candidates(registry or {}, project_root, compatible_list_class_names):
                project_candidates.append(candidate)
        if project_candidates or fallback_candidates:
            project_candidates = _sort_role_candidates(role, project_candidates)
            fallback_candidates = _sort_role_candidates(role, fallback_candidates)
            default = (project_candidates or fallback_candidates)[0]
            role_data: dict[str, Any] = {
                "project_candidates": project_candidates[:20],
                "fallback_candidates": fallback_candidates[:20],
                "required": bool(project_candidates),
                "default": default.get("class_path") or default.get("asset_path"),
            }
            if role == "list_row":
                compatible_project_candidates = [
                    candidate for candidate in project_candidates if candidate.get("list_entry_compatible") is True
                ]
                incompatible_or_unknown = [
                    candidate for candidate in project_candidates if candidate.get("list_entry_compatible") is not True
                ]
                role_data["compatible_project_candidates"] = compatible_project_candidates[:20]
                role_data["incompatible_or_unknown_project_candidates"] = incompatible_or_unknown[:20]
            roles[role] = role_data
    return roles


def _list_entry_compatibility(candidate: dict[str, str], compatible_class_names: set[str]) -> bool | None:
    if candidate.get("source") == "fallback":
        return None
    if candidate.get("source") == "generated":
        value = candidate.get("list_entry_compatible")
        return value if isinstance(value, bool) else None
    if not compatible_class_names:
        return None
    candidate_names = {_compact_name(candidate.get("name", ""))}
    class_path = candidate.get("class_path") or ""
    tail = class_path.rsplit("/", 1)[-1].split(".", 1)[0]
    candidate_names.add(_compact_name(tail))
    for class_name in compatible_class_names:
        compact = _compact_name(class_name)
        stripped = compact.removeprefix("u")
        if compact in candidate_names or stripped in candidate_names:
            return True
        if any(candidate.endswith(stripped) or candidate.endswith(compact) for candidate in candidate_names):
            return True
    return None


def _registry_list_entry_candidates(
    registry: dict[str, Any],
    project_root: Path | None,
    compatible_class_names: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for role, entry in _iter_registry_role_entries(registry):
        if role not in {
            "list_row",
            "list_entry",
            "tile_entry",
            "card_entry",
            "leaderboard_entry",
            "leaderboard_row",
            "store_item_card",
            "achievement_card",
            "friend_entry",
            "session_entry",
            "entitlement_entry",
            "notification_entry",
        }:
            continue
        class_path = entry.get("class_path")
        asset_path = entry.get("asset_path")
        if not isinstance(class_path, str) or not isinstance(asset_path, str):
            continue
        spec = _load_registry_spec(project_root, entry.get("spec_path"))
        parent_class = str(spec.get("parent_class", "")) if isinstance(spec, dict) else ""
        compatible = _parent_class_matches_names(parent_class, compatible_class_names)
        if isinstance(spec, dict):
            recipe_intents = set(_entry_recipe_intents_for_spec(spec))
            recipe_intents.update(_entry_recipe_intents_for_name(asset_path.rsplit("/", 1)[-1]))
            for registry_role in entry.get("roles") or []:
                recipe_intents.update(_entry_recipe_intents_for_role(str(registry_role)))
            recipe_intents.update(_entry_recipe_intents_for_role(role))
        else:
            recipe_intents = set(_entry_recipe_intents_for_name(asset_path.rsplit("/", 1)[-1]))
            recipe_intents.update(_entry_recipe_intents_for_role(role))
        candidates.append(
            {
                "asset_path": asset_path,
                "class_path": class_path,
                "name": asset_path.rsplit("/", 1)[-1],
                "source": "generated",
                "kind": "entry_widget",
                "list_entry_compatible": compatible,
                "recipe_intents": sorted(recipe_intents),
                "parent_class": parent_class,
                "spec_path": entry.get("spec_path"),
            }
        )
    return candidates


def _load_registry_spec(project_root: Path | None, spec_path: Any) -> dict[str, Any] | None:
    if project_root is None or not isinstance(spec_path, str) or not spec_path:
        return None
    path = Path(spec_path)
    if not path.is_absolute():
        path = project_root / path
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sort_role_candidates(role: str, candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    def sort_key(candidate: dict[str, str]) -> tuple[int, str]:
        kind = candidate.get("kind", "")
        if role in TEXT_ROLES:
            priority = 0 if kind == "style" else 1
        elif role in BUTTON_ROLES:
            priority = 0 if kind == "widget" else 1
        else:
            priority = 0 if kind == "widget" else 1
        return (priority, candidate.get("class_path") or candidate.get("asset_path") or "")

    return sorted(candidates, key=sort_key)


def _detect_ui_backend(
    modules: set[str],
    classes: dict[str, list[dict[str, str]]],
    widget_assets: list[dict[str, str]],
    style_assets: list[dict[str, str]],
) -> str:
    has_common = "CommonUI" in modules or any(role in classes for role in ("common_activatable", "common_button", "common_text"))
    has_umg = "UMG" in modules or bool(widget_assets)
    has_common_assets = any("common" in item["name"].casefold() for item in widget_assets + style_assets)
    if has_common and has_umg and not has_common_assets:
        return "common_ui"
    if has_common and has_umg:
        return "mixed"
    if has_common:
        return "common_ui"
    if has_umg:
        return "umg"
    return "unknown"


def _confidence(ui_backend: str, semantic_roles: dict[str, dict[str, list[str]]], warnings: list[str]) -> str:
    role_count = sum(1 for group in semantic_roles.values() for values in group.values() if values)
    if ui_backend == "unknown" or role_count < 2:
        return "low"
    if warnings or role_count < 5:
        return "medium"
    return "high"


def _build_warnings(
    ui_backend: str,
    semantic_roles: dict[str, dict[str, list[str]]],
    style_assets: list[dict[str, str]],
    enforced_roles: dict[str, dict[str, Any]],
) -> list[str]:
    warnings = []
    if ui_backend == "unknown":
        warnings.append("No UMG/Common UI backend was confidently detected.")
    if not any(item.get("candidate_type") == "project" for item in style_assets):
        warnings.append("No project style assets or theme token files were found; default theme fallback may be needed.")
    if not semantic_roles.get("widgets") and not semantic_roles.get("styles"):
        warnings.append("No reusable UI roles were inferred from project assets.")
    if any(values.get("project_candidates") and values.get("fallback_candidates") for values in enforced_roles.values()):
        warnings.append("Project UI candidates and AGSUI/Core fallback candidates were both found; approved project candidates are mandatory for generated project widgets.")
    return warnings


def _ambiguities(semantic_roles: dict[str, dict[str, list[str]]], enforced_roles: dict[str, dict[str, Any]]) -> list[str]:
    ambiguous = []
    for group_name in ("widgets", "styles"):
        for role, values in semantic_roles.get(group_name, {}).items():
            if len(values) > 5:
                ambiguous.append(f"{group_name}.{role} has {len(values)} candidates; confirmation should choose the intended default.")
    for role, values in enforced_roles.items():
        project_candidates = values.get("project_candidates", [])
        if len(project_candidates) > 1:
            ambiguous.append(f"enforced_roles.{role} has {len(project_candidates)} project candidates; the first candidate is the deterministic default.")
    return ambiguous


def _discouraged_raw_widget_types(
    ui_backend: str,
    semantic_roles: dict[str, dict[str, list[str]]],
    enforced_roles: dict[str, dict[str, Any]],
) -> list[str]:
    discouraged = []
    roles = semantic_roles.get("widgets", {}) | semantic_roles.get("styles", {})
    if ui_backend in {"common_ui", "mixed"} or any(role in BUTTON_ROLES for role in roles) or any(role in BUTTON_ROLES for role in enforced_roles):
        discouraged.append("Button")
    has_text_widget_candidates = any(
        candidate.get("kind") == "widget"
        for role in TEXT_ROLES
        for candidate in enforced_roles.get(role, {}).get("project_candidates", [])
    )
    if ui_backend == "common_ui" or has_text_widget_candidates:
        discouraged.append("TextBlock")
    if "input" in roles:
        discouraged.append("EditableTextBox")
    return sorted(set(discouraged))


def _validation_rules(
    ui_backend: str,
    semantic_roles: dict[str, dict[str, list[str]]],
    enforced_roles: dict[str, dict[str, Any]],
) -> list[str]:
    rules = [f"Generated specs must match detected UI backend: {ui_backend}."]
    if semantic_roles.get("widgets") or semantic_roles.get("styles"):
        rules.append("Approved project widgets and style assets are mandatory defaults for generated project widgets.")
    if any(role in BUTTON_ROLES for role, values in enforced_roles.items() if values.get("project_candidates")):
        rules.append("Buttons must use discovered project button classes or button_style_class before AGSUI/Core fallback.")
    if any(role in TEXT_ROLES for role, values in enforced_roles.items() if values.get("project_candidates")):
        rules.append("Text nodes must use discovered project text_style_class values when project text styles exist.")
    if enforced_roles.get("list_row", {}).get("project_candidates"):
        rules.append("ListView/TileView/TreeView entry_widget_class must use discovered project list entry widgets.")
    rules.append("Unknown project class/style references are rejected when allowlists are available.")
    return rules


def _allowed_class_references(
    classes: dict[str, list[dict[str, str]]],
    widget_assets: list[dict[str, str]],
    registry: dict[str, Any] | None = None,
) -> list[str]:
    references = set()
    for item in widget_assets:
        asset_path = item["asset_path"]
        references.add(asset_path)
        references.add(item.get("class_path") or _asset_class_reference(asset_path))
    for values in classes.values():
        for item in values:
            references.update(_script_class_path_variants_for_source(item))
    # Include paths from the generated-components registry so specs can reference
    # previously generated project-style state panels and other core components.
    for role_entry in _iter_registry_entries(registry or {}):
        for key in ("asset_path", "class_path"):
            value = role_entry.get(key)
            if isinstance(value, str) and value:
                references.add(value)
    return sorted(references)


def _build_project_class_mapping(
    classes: dict[str, list[dict[str, str]]],
    widget_assets: list[dict[str, str]],
    registry: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> dict[str, str]:
    """Map project widget class_path values to their resolved C++ class names.

    Consumed by widget_spec.py binding resolution when a spec node references a
    project widget by class_path instead of a known AGS contract type.
    Prefer asset/source name matches, then role-specific source-class fallbacks.
    """
    mapping: dict[str, str] = {}

    source_class_names = [
        item["name"]
        for role in ("common_button", "common_text", "common_activatable", "user_widget", "list_entry_compatible")
        for item in classes.get(role, [])
        if item.get("name")
    ]

    for asset in widget_assets:
        class_path = asset.get("class_path")
        if not class_path:
            continue
        matched = _match_asset_to_source_class(asset.get("name", ""), source_class_names)
        if matched:
            mapping[class_path] = matched

    common_button_entries = classes.get("common_button", [])
    if common_button_entries:
        button_class = common_button_entries[0]["name"]
        for asset in widget_assets:
            if any(r in BUTTON_ROLES for r in asset.get("roles", [])):
                class_path = asset.get("class_path")
                if class_path and class_path not in mapping:
                    mapping[class_path] = button_class
    list_entry_entries = classes.get("list_entry_compatible", [])
    for asset in widget_assets:
        if "list_row" not in asset.get("roles", []):
            continue
        class_path = asset.get("class_path")
        if not class_path or class_path in mapping:
            continue
        matched = _match_asset_to_source_class(asset.get("name", ""), [item["name"] for item in list_entry_entries])
        if matched:
            mapping[class_path] = matched
    for candidate in _registry_list_entry_candidates(registry or {}, project_root, {item["name"] for item in list_entry_entries}):
        class_path = candidate.get("class_path")
        parent_class = str(candidate.get("parent_class") or "")
        if isinstance(class_path, str) and parent_class.startswith("/Script/"):
            tail = parent_class.rsplit(".", 1)[-1]
            mapping[class_path] = tail if tail.startswith("U") else f"U{tail}"
    for entry in _iter_registry_entries(registry or {}):
        class_path = entry.get("class_path")
        if not isinstance(class_path, str) or class_path in mapping:
            continue
        spec = _load_registry_spec(project_root, entry.get("spec_path"))
        parent_class = str(spec.get("parent_class", "")) if isinstance(spec, dict) else ""
        if parent_class.startswith("/Script/"):
            tail = parent_class.rsplit(".", 1)[-1]
            mapping[class_path] = tail if tail.startswith("U") else f"U{tail}"
    return mapping


def _match_asset_to_source_class(asset_name: str, class_names: list[str]) -> str | None:
    asset_key = _compact_name(asset_name)
    asset_variants = {
        asset_key,
        re.sub(r"^(wbp|wb|w|bp)", "", asset_key),
        re.sub(r"(widget|entry)$", "", asset_key),
    }
    for class_name in class_names:
        class_key = _compact_name(class_name)
        class_variants = {
            class_key,
            class_key[1:] if class_key.startswith("u") else class_key,
            re.sub(r"(widget|entry|base)$", "", class_key[1:] if class_key.startswith("u") else class_key),
        }
        if any(a and c and (a == c or a.endswith(c) or c.endswith(a)) for a in asset_variants for c in class_variants):
            return class_name
    return None


def _allowed_style_references(style_assets: list[dict[str, str]]) -> list[str]:
    references = set()
    for item in style_assets:
        references.add(item["asset_path"])
        references.add(item.get("class_path") or _asset_class_reference(item["asset_path"]))
    return sorted(references)


def _widget_roles_for_name(name: str) -> list[str]:
    lowered = name.casefold()
    compact = _compact_name(name)
    if re.match(r"^(m|mi|mat|t|tex|s)_", lowered):
        return []
    roles = []
    if any(keyword in compact for keyword in ("input", "search", "password", "textbox", "textinput")):
        return ["input"]
    if "button" in lowered or lowered.endswith("btn") or "_btn" in lowered:
        roles.extend(_button_roles_for_name(name))
    if "text" in lowered or "label" in lowered:
        roles.extend(_text_roles_for_name(name))
    if any(keyword in compact for keyword in ("listrow", "listentry", "entry", "row", "card")):
        roles.append("list_row")
    if any(keyword in compact for keyword in ("modal", "popup", "dialog")):
        roles.append("modal")
    if any(keyword in compact for keyword in ("panel", "container", "surface")):
        roles.append("panel")
    if any(keyword in compact for keyword in ("loading", "empty", "error", "status", "state")):
        roles.append("state_widget")
    return sorted(set(roles))


def _style_roles_for_name(name: str) -> list[str]:
    lowered = name.casefold()
    compact = _compact_name(name)
    if "buttonstyle" in compact or "commonbuttonstyle" in compact or ("button" in lowered and "style" in lowered):
        return _button_roles_for_name(name)
    if "textstyle" in compact or "commontextstyle" in compact or "richtext" in compact or ("text" in lowered and "style" in lowered):
        return _text_roles_for_name(name)
    if "theme" in lowered and ("token" in lowered or "style" in lowered):
        return ["theme_tokens"]
    return []


def _button_roles_for_name(name: str) -> list[str]:
    lowered = name.casefold()
    compact = _compact_name(name)
    roles: list[str] = []
    if any(keyword in lowered for keyword in ROLE_KEYWORDS["danger_button"]):
        roles.append("danger_button")
    if any(keyword in lowered for keyword in ROLE_KEYWORDS["secondary_button"]):
        roles.append("secondary_button")
    if "tab" in lowered:
        roles.append("tab_button")
    if any(keyword in lowered for keyword in ROLE_KEYWORDS["primary_button"]):
        roles.append("primary_button")
    if not roles and ("button" in lowered or "btn" in compact):
        roles.append("primary_button")
    return sorted(set(roles), key=lambda role: ENFORCED_ROLE_ORDER.index(role))


def _text_roles_for_name(name: str) -> list[str]:
    lowered = name.casefold()
    roles: list[str] = []
    if any(keyword in lowered for keyword in ROLE_KEYWORDS["warning_text"]):
        roles.append("warning_text")
    if any(keyword in lowered for keyword in ROLE_KEYWORDS["title_text"]):
        roles.append("title_text")
    if any(keyword in lowered for keyword in ROLE_KEYWORDS["body_text"]):
        roles.append("body_text")
    if not roles and ("text" in lowered or "label" in lowered):
        roles.append("body_text")
    return sorted(set(roles), key=lambda role: ENFORCED_ROLE_ORDER.index(role))


def _is_likely_ui_asset(project_root: Path, path: Path) -> bool:
    try:
        parts = [part.casefold() for part in path.relative_to(project_root).parts]
    except ValueError:
        parts = [part.casefold() for part in path.parts]
    if "plugins" in parts and "accelbyteuitools" in parts:
        return True
    if any(part in NON_UI_PATH_PARTS for part in parts):
        return False
    return any(part in LIKELY_UI_PATH_PARTS for part in parts)


def _is_style_asset_name(name: str) -> bool:
    lowered = name.casefold()
    return "style" in lowered or "theme" in lowered or "token" in lowered


def _candidate_type(asset_path: str) -> str:
    return "fallback" if _is_plugin_fallback_path(asset_path) else "project"


def _compact_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _asset_class_reference(asset_path: str) -> str:
    if not asset_path.startswith("/") or "." in asset_path or asset_path.startswith("/Script/"):
        return asset_path
    return f"{asset_path}.{asset_path.rsplit('/', 1)[-1]}_C"


def _is_generated_project_spec(spec: dict[str, Any]) -> bool:
    asset_path = str(spec.get("asset_path", ""))
    return asset_path.startswith("/Game/") and "/UI/Generated/" in asset_path


def _is_collection_entry_spec(spec: dict[str, Any]) -> bool:
    asset_name = str(spec.get("asset_path", "")).rsplit("/", 1)[-1]
    compact = _compact_name(asset_name)
    return (
        compact.endswith(("entry", "row", "card", "tileitem", "listitem"))
        or any(keyword in compact for keyword in ("itemcard", "entrywidget", "rowwidget", "cardwidget"))
    )


def _parent_class_matches_source_class(parent_class: str, source_classes: list[dict[str, Any]]) -> bool:
    return any(parent_class in _script_class_path_variants_for_source(entry) for entry in source_classes)


def _parent_class_matches_names(parent_class: str, class_names: set[str]) -> bool | None:
    if not parent_class:
        return None
    tail = parent_class.rsplit(".", 1)[-1]
    compact_tail = _compact_name(tail).removeprefix("u")
    for class_name in class_names:
        compact = _compact_name(class_name).removeprefix("u")
        if compact_tail == compact:
            return True
    return False if class_names else None


def _script_class_path_for_source(entry: dict[str, Any]) -> str:
    module = entry.get("module") or "Project"
    name = entry.get("name") or ""
    if name.startswith("U") and len(name) > 1 and name[1].isupper():
        name = name[1:]
    return f"/Script/{module}.{name}" if name else ""


def _script_class_path_variants_for_source(entry: dict[str, Any]) -> set[str]:
    primary = _script_class_path_for_source(entry)
    module = entry.get("module") or "Project"
    name = entry.get("name") or ""
    variants = {primary} if primary else set()
    if name:
        variants.add(f"/Script/{module}.{name}")
    return variants


def _project_common_activatable_parent_classes(context: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in context.get("source_classes", {}).get("common_activatable", []):
        class_path = _script_class_path_for_source(entry)
        if class_path:
            result.append(
                {
                    "class_path": class_path,
                    "name": entry.get("name"),
                    "source": entry.get("source"),
                }
            )
    return result


def _is_plugin_fallback_path(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(PLUGIN_FALLBACK_PREFIX)


def _uses_project_reference(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith("/Game/")


def _is_generated_project_class_reference(value: str) -> bool:
    if not value.startswith("/Game/"):
        return False
    if not VALID_GENERATED_PROJECT_CLASS_REFERENCE.match(value):
        return False
    return "/UI/Generated/" in value or "/UI/Components/" in value or value.startswith(GENERATED_COMPONENTS_ASSET_PREFIX)


def _is_generated_project_asset_path(value: str) -> bool:
    return isinstance(value, str) and value.startswith("/Game/") and (
        "/UI/Generated/" in value or "/UI/Components/" in value
    )


def _registry_path(project_root: Path) -> Path:
    return project_root / "Config" / "AccelByteUITools" / GENERATED_COMPONENTS_REGISTRY_FILENAME


def _legacy_registry_path(project_root: Path) -> Path:
    return project_root / "Saved" / "AccelByteUITools" / GENERATED_COMPONENTS_REGISTRY_FILENAME


def load_generated_components_registry(project: str | Path) -> dict[str, Any]:
    project_root = project_root_from_project(project)
    for path in (_registry_path(project_root), _legacy_registry_path(project_root)):
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def register_generated_component(project: str | Path, role: str, asset_path: str, spec_path: str) -> None:
    register_generated_widget(project, asset_path, spec_path, roles=[role], legacy_role=role)


def register_generated_widget(
    project: str | Path,
    asset_path: str,
    spec_path: str,
    *,
    roles: list[str] | None = None,
    legacy_role: str | None = None,
) -> None:
    project_root = project_root_from_project(project)
    if not _is_generated_project_asset_path(asset_path):
        return
    registry = load_generated_components_registry(project_root)
    spec = _load_registry_spec(project_root, spec_path)
    inferred_roles = roles or _infer_generated_widget_registry_roles(asset_path, spec)
    if not inferred_roles:
        return
    entry = {
        "asset_path": asset_path,
        "class_path": f"{asset_path}.{asset_path.rsplit('/', 1)[-1]}_C",
        "spec_path": spec_path,
        "roles": sorted(set(inferred_roles)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    widgets = [item for item in registry.get(GENERATED_WIDGETS_REGISTRY_KEY, []) if isinstance(item, dict)]
    widgets = [
        item
        for item in widgets
        if item.get("class_path") != entry["class_path"] and item.get("asset_path") != entry["asset_path"]
    ]
    widgets.append(entry)
    registry[GENERATED_WIDGETS_REGISTRY_KEY] = widgets
    if legacy_role:
        registry[legacy_role] = entry
    path = _registry_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _iter_registry_entries(registry: dict[str, Any]):
    seen: set[str] = set()
    for entry in registry.get(GENERATED_WIDGETS_REGISTRY_KEY, []):
        if not isinstance(entry, dict):
            continue
        ref = str(entry.get("class_path") or entry.get("asset_path") or "")
        if ref:
            seen.add(ref)
        yield entry
    for key, entry in registry.items():
        if key == GENERATED_WIDGETS_REGISTRY_KEY or not isinstance(entry, dict):
            continue
        ref = str(entry.get("class_path") or entry.get("asset_path") or "")
        if ref and ref in seen:
            continue
        if ref:
            seen.add(ref)
        yield entry


def _iter_registry_role_entries(registry: dict[str, Any]):
    for entry in registry.get(GENERATED_WIDGETS_REGISTRY_KEY, []):
        if not isinstance(entry, dict):
            continue
        for role in entry.get("roles") or []:
            yield str(role), entry
    for key, entry in registry.items():
        if key == GENERATED_WIDGETS_REGISTRY_KEY or not isinstance(entry, dict):
            continue
        yield key, entry


def _registry_widget_assets(registry: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _iter_registry_entries(registry):
        asset_path = entry.get("asset_path")
        class_path = entry.get("class_path")
        if not isinstance(asset_path, str) or not isinstance(class_path, str):
            continue
        if class_path in seen:
            continue
        roles = _widget_roles_from_registry_roles(entry.get("roles") or [])
        if not roles:
            roles = _widget_roles_for_name(asset_path.rsplit("/", 1)[-1])
        if not roles:
            continue
        assets.append(
            {
                "asset_path": asset_path,
                "class_path": class_path,
                "name": asset_path.rsplit("/", 1)[-1],
                "roles": roles,
                "candidate_type": "project",
                "source": "generated",
            }
        )
        seen.add(class_path)
    return assets


def _widget_roles_from_registry_roles(registry_roles: list[Any]) -> list[str]:
    roles: set[str] = set()
    for role_value in registry_roles:
        role = str(role_value)
        if role in CORE_COMPONENT_ROLES:
            roles.add("state_widget")
        elif role in {
            "list_row",
            "list_entry",
            "tile_entry",
            "card_entry",
            "leaderboard_entry",
            "leaderboard_row",
            "store_item_card",
            "achievement_card",
            "friend_entry",
            "session_entry",
            "entitlement_entry",
            "notification_entry",
        }:
            roles.add("list_row")
        elif role in ENFORCED_ROLE_ORDER:
            roles.add(role)
    return sorted(roles, key=lambda role: ENFORCED_ROLE_ORDER.index(role))


def _infer_generated_widget_registry_roles(asset_path: str, spec: dict[str, Any] | None) -> list[str]:
    values = [asset_path]
    if isinstance(spec, dict):
        values.append(str(spec.get("asset_path", "")))
        for _, node in _walk_nodes(spec.get("root"), "root"):
            values.append(str(node.get("name", "")))
            values.append(str(node.get("type", "")))
    combined = " ".join(values)
    if isinstance(spec, dict) and _is_collection_entry_spec(spec):
        intents = set(_entry_recipe_intents_for_spec(spec))
        intents.update(_entry_recipe_intents_for_name(asset_path))
        roles = [_entry_role_for_intent(intent) for intent in sorted(intents)]
        return [role for role in roles if role] or ["list_entry"]
    roles = set(_widget_roles_for_name(asset_path.rsplit("/", 1)[-1]))
    roles.discard("list_row")
    compact = _compact_name(combined)
    if any(token in compact for token in ("modal", "popup", "dialog")):
        roles.add("modal")
    if any(token in compact for token in ("panel", "screen", "page", "view")):
        roles.add("panel")
    if any(token in compact for token in ("loading", "empty", "error", "status", "state")):
        roles.add("state_widget")
    if any(token in compact for token in ("input", "search", "password", "textbox", "textinput")):
        roles.add("input")
    return sorted((role for role in roles if role in ENFORCED_ROLE_ORDER), key=lambda role: ENFORCED_ROLE_ORDER.index(role))


def _entry_role_for_intent(intent: str) -> str | None:
    return {
        "leaderboard": "leaderboard_entry",
        "store": "store_item_card",
        "achievements": "achievement_card",
        "friends": "friend_entry",
        "sessions": "session_entry",
        "entitlements": "entitlement_entry",
        "notifications": "notification_entry",
    }.get(intent)


def _core_component_candidates(
    widget_assets: list[dict[str, Any]],
    registry: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for role, info in CORE_COMPONENT_ROLES.items():
        keywords = info["keywords"]
        project_candidate = None
        for item in widget_assets:
            if item.get("candidate_type") != "project":
                continue
            compact = _compact_name(item.get("name", ""))
            if any(kw.replace("_", "") in compact for kw in keywords):
                project_candidate = {
                    "asset_path": item["asset_path"],
                    "class_path": item.get("class_path") or _asset_class_reference(item["asset_path"]),
                    "name": item["name"],
                    "source": "project",
                }
                break
        generated_candidate = None
        if role in registry:
            entry = registry[role]
            generated_candidate = {
                "asset_path": entry["asset_path"],
                "class_path": entry["class_path"],
                "source": "generated",
            }
        result[role] = {
            "description": info["description"],
            "ags_aliases": info["ags_aliases"],
            "agsui_fallback": info["agsui_fallback"],
            "project_candidate": project_candidate,
            "generated_candidate": generated_candidate,
            "resolved": (project_candidate or generated_candidate or {}).get("class_path") or info["agsui_fallback"],
            "resolution_tier": (
                "project" if project_candidate else
                "generated" if generated_candidate else
                "agsui_fallback"
            ),
        }
    return result


def _project_candidates_for_role(enforced_roles: dict[str, Any], role: str, *, kind: str | None = None) -> list[dict[str, Any]]:
    values = enforced_roles.get(role, {})
    candidates = list(values.get("project_candidates", []))
    if kind is None:
        return candidates
    filtered = [candidate for candidate in candidates if candidate.get("kind") == kind]
    if filtered:
        return filtered
    if candidates and all("kind" not in candidate for candidate in candidates):
        return candidates
    return []


def _project_button_widget_candidates(enforced_roles: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role in BUTTON_ROLES:
        for candidate in _project_candidates_for_role(enforced_roles, role, kind="widget"):
            ref = candidate.get("class_path") or candidate.get("asset_path")
            if not isinstance(ref, str) or ref in seen:
                continue
            candidates.append(candidate)
            seen.add(ref)
    return candidates


def _compatible_project_candidates_for_role(enforced_roles: dict[str, Any], role: str) -> list[dict[str, Any]]:
    values = enforced_roles.get(role, {})
    return list(values.get("compatible_project_candidates", []))


def _incompatible_or_unknown_project_candidates_for_role(enforced_roles: dict[str, Any], role: str) -> list[dict[str, Any]]:
    values = enforced_roles.get(role, {})
    return list(values.get("incompatible_or_unknown_project_candidates", []))


def _is_candidate_reference(value: str | None, candidates: list[dict[str, Any]]) -> bool:
    if not isinstance(value, str):
        return False
    references = {candidate.get("class_path") for candidate in candidates}
    references.update(candidate.get("asset_path") for candidate in candidates)
    return value in references


def _recipe_compatible_candidates(candidates: list[dict[str, Any]], intent: str | None) -> list[dict[str, Any]]:
    if not intent:
        return candidates
    matching: list[dict[str, Any]] = []
    for candidate in candidates:
        recipe_intents = _candidate_recipe_intents(candidate)
        if intent in recipe_intents:
            matching.append(candidate)
    return matching


def _candidate_recipe_intents(candidate: dict[str, Any]) -> set[str]:
    recipe_intents = set(candidate.get("recipe_intents") or [])
    if recipe_intents:
        return recipe_intents

    recipe_intents.update(_entry_recipe_intents_for_name(str(candidate.get("name", ""))))
    recipe_intents.update(_entry_recipe_intents_for_name(str(candidate.get("class_path", ""))))
    recipe_intents.update(_entry_recipe_intents_for_name(str(candidate.get("asset_path", ""))))
    return recipe_intents


def _collection_recipe_intent(spec: dict[str, Any], path: str, node: dict[str, Any]) -> str | None:
    values = [
        str(spec.get("asset_path", "")),
        str(spec.get("name", "")),
        str(spec.get("title", "")),
        path,
        str(node.get("name", "")),
        str(node.get("type", "")),
        str(node.get("entry_widget_class", "")),
    ]
    for _, child in _walk_nodes(spec.get("root"), "root"):
        values.append(str(child.get("name", "")))
        values.append(str(child.get("text", "")))
        values.append(str(child.get("type", "")))
    compact = _compact_name(" ".join(values))
    matches = [
        intent
        for intent, info in COLLECTION_RECIPE_INTENTS.items()
        if any(keyword in compact for keyword in info["keywords"])
    ]
    if "store" in matches and "achievements" in matches:
        return "achievements" if "achievement" in compact else "store"
    return matches[0] if matches else None


def _has_runtime_collection_intent(spec: dict[str, Any], path: str, node: dict[str, Any]) -> bool:
    values = [
        str(spec.get("asset_path", "")),
        path,
        str(node.get("name", "")),
        str(node.get("type", "")),
    ]
    combined = " ".join(values).casefold()
    return any(keyword in combined for keyword in RUNTIME_COLLECTION_KEYWORDS)


def _entry_recipe_intents_for_role(role: str) -> list[str]:
    role_map = {
        "leaderboard_entry": "leaderboard",
        "leaderboard_row": "leaderboard",
        "store_item_card": "store",
        "achievement_card": "achievements",
        "friend_entry": "friends",
        "session_entry": "sessions",
        "entitlement_entry": "entitlements",
        "notification_entry": "notifications",
        "tile_entry": None,
        "card_entry": None,
        "list_entry": None,
        "list_row": None,
    }
    mapped = role_map.get(role)
    return [mapped] if mapped else []


def _entry_recipe_intents_for_name(name: str) -> list[str]:
    compact = _compact_name(name)
    intents: list[str] = []
    for intent, info in COLLECTION_RECIPE_INTENTS.items():
        if any(keyword in compact for keyword in info["keywords"]):
            intents.append(intent)
    return sorted(set(intents))


def _entry_recipe_intents_for_spec(spec: dict[str, Any]) -> list[str]:
    tokens: set[str] = set()
    node_names: list[str] = []
    for _, node in _walk_nodes(spec.get("root"), "root"):
        node_names.append(str(node.get("name", "")))
        node_names.append(str(node.get("text", "")))
    compact_nodes = _compact_name(" ".join(node_names))
    for intent, info in COLLECTION_RECIPE_INTENTS.items():
        if intent in tokens:
            continue
        if all(any(keyword in compact_nodes for keyword in group) for group in info["required_groups"]):
            tokens.add(intent)
    return sorted(tokens)


def _is_button_node(widget_type: str, class_path: Any) -> bool:
    combined = f"{widget_type} {class_path or ''}".casefold()
    return "button" in combined or widget_type in {"AGSBaseButton", "AGSButton", "AGSSecondaryButton", "AGSDangerButton", "AGSIconButton"}


def _is_text_node(widget_type: str, class_path: Any) -> bool:
    combined = f"{widget_type} {class_path or ''}".casefold()
    return widget_type == "TextBlock" or "commontextblock" in combined or "textblock" in combined


def _is_panel_node(widget_type: str, class_path: Any) -> bool:
    combined = f"{widget_type} {class_path or ''}".casefold()
    return "panel" in combined or "card" in combined or widget_type in {"Border", "Overlay", "CanvasPanel"}


def _button_role_for_node(node: dict[str, Any]) -> str:
    combined = f"{node.get('type', '')} {node.get('name', '')} {node.get('class_path', '')}".casefold()
    if "tab" in combined:
        return "tab_button"
    if any(keyword in combined for keyword in ("danger", "delete", "remove", "quit", "warning")):
        return "danger_button"
    if any(keyword in combined for keyword in ("secondary", "cancel", "back")):
        return "secondary_button"
    return "primary_button"


def _text_role_for_node(node: dict[str, Any]) -> str:
    combined = f"{node.get('type', '')} {node.get('name', '')} {node.get('class_path', '')}".casefold()
    if any(keyword in combined for keyword in ("warning", "error", "danger")):
        return "warning_text"
    if any(keyword in combined for keyword in ("title", "heading", "header")):
        return "title_text"
    return "body_text"
    return roles


def _asset_reference(project_root: Path, path: Path) -> str:
    relative = path.relative_to(project_root).with_suffix("")
    parts = relative.parts
    if parts and parts[0] == "Content":
        return "/Game/" + "/".join(parts[1:])
    if len(parts) > 2 and parts[0] == "Plugins":
        return "/" + parts[1] + "/" + "/".join(parts[3:] if parts[2] == "Content" else parts[2:])
    return _rel(project_root, path)


def _fingerprint(project_root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        digest.update(_rel(project_root, path).encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(int(stat.st_mtime)).encode("ascii"))
    return digest.hexdigest()


def _walk_nodes(node: Any, path: str):
    if not isinstance(node, dict):
        return
    yield path, node
    children = node.get("children", [])
    if isinstance(children, list):
        for index, child in enumerate(children):
            yield from _walk_nodes(child, f"{path}.children[{index}]")


def _style_error(
    code: str,
    path: str,
    actual: Any,
    expected: Any,
    *,
    role: str | None = None,
    recommended: list[dict[str, Any]] | None = None,
    advisory: bool = False,
) -> dict[str, Any]:
    error = {"code": code, "path": path, "actual": actual, "expected": expected}
    if role is not None:
        error["role"] = role
    if recommended is not None:
        error["recommended_project_candidates"] = recommended
    if advisory:
        error["advisory"] = True
    return error


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _rel(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()
