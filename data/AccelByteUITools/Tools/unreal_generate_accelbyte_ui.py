from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

import unreal

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--force", action="store_true")
    args, _unknown = parser.parse_known_args(argv)

    try:
        spec_path = Path(args.spec)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        report = generate_accelbyte_ui(spec, force=args.force)
        write_report(spec_path, report)
        if report["errors"]:
            unreal.log_error(json.dumps(report, indent=2))
            return 1
        unreal.log(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        report = {
            "ok": False,
            "asset_path": None,
            "parent_class": None,
            "expected_widget_count": 0,
            "verified_widget_count": 0,
            "verified_widget_names": [],
            "warnings": [],
            "errors": [
                {
                    "code": "unreal_generation_failed",
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ],
        }
        write_report(Path(args.spec), report)
        unreal.log_error(json.dumps(report, indent=2))
        return 1


def generate_accelbyte_ui(spec: dict, force: bool) -> dict:
    asset_path = spec["asset_path"]
    parent_class_path = spec["parent_class"]
    parent_class = unreal.load_class(None, parent_class_path)
    warnings = []
    errors = []
    expected_widget_count = count_widgets(spec["root"])
    verified_widget_count = 0
    verified_widget_names = []

    if parent_class is None:
        return _report(
            False,
            asset_path,
            parent_class_path,
            expected_widget_count,
            verified_widget_count,
            verified_widget_names,
            warnings,
            [{"code": "parent_class_missing", "message": parent_class_path}],
        )

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path) and not force:
        return _report(
            False,
            asset_path,
            parent_class_path,
            expected_widget_count,
            verified_widget_count,
            verified_widget_names,
            warnings,
            [
                {
                    "code": "asset_path_denied",
                    "message": "Asset already exists. Use --force to overwrite generated assets.",
                }
            ],
        )

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    package_path, asset_name = asset_path.rsplit("/", 1)
    factory = unreal.WidgetBlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)

    generated_blueprint = asset_tools.create_asset(asset_name, package_path, unreal.WidgetBlueprint, factory)
    if generated_blueprint is None:
        return _report(
            False,
            asset_path,
            parent_class_path,
            expected_widget_count,
            verified_widget_count,
            verified_widget_names,
            warnings,
            [{"code": "unreal_generation_failed", "message": "create_asset returned None"}],
        )

    widget_tree = get_widget_tree(generated_blueprint)
    if widget_tree is None:
        warnings.append(
            {
                "code": "widget_tree_unavailable",
                "message": "Widget Blueprint asset was created, but UE Python did not expose WidgetTree editing for this asset.",
            }
        )
        populated, populate_error = populate_accelbyte_ui_from_json(asset_path, spec)
        if not populated:
            errors.append(
                {
                    "code": "widget_hierarchy_unverified",
                    "message": "Widget Blueprint hierarchy could not be created by the editor helper.",
                    "detail": populate_error,
                }
            )
    else:
        root_widget = build_widget_tree(widget_tree, spec["root"])
        widget_tree.set_editor_property("root_widget", root_widget)

    kismet_editor_utilities = getattr(unreal, "KismetEditorUtilities", None)
    if kismet_editor_utilities is None:
        warnings.append(
            {
                "code": "compile_unavailable",
                "message": "unreal.KismetEditorUtilities is not exposed in this Unreal Python environment; asset was saved without explicit compile.",
            }
        )
    else:
        try:
            kismet_editor_utilities.compile_blueprint(generated_blueprint)
        except Exception as exc:
            errors.append({"code": "compile_failed", "message": str(exc)})

    if "variant" in spec and not errors:
        ags_variant_enum = getattr(unreal, "EAGSButtonVariant", None)
        if ags_variant_enum is not None:
            variant_map = {
                "primary":   getattr(ags_variant_enum, "PRIMARY", None),
                "secondary": getattr(ags_variant_enum, "SECONDARY", None),
                "danger":    getattr(ags_variant_enum, "DANGER", None),
                "icon":      getattr(ags_variant_enum, "ICON", None),
            }
            variant_val = variant_map.get(spec["variant"].lower())
            if variant_val is not None:
                generated_class = getattr(generated_blueprint, "generated_class", None)
                if generated_class:
                    cdo = generated_class.get_default_object()
                    if cdo and hasattr(cdo, "set_editor_property"):
                        try:
                            cdo.set_editor_property("variant", variant_val)
                        except Exception as exc:
                            warnings.append({"code": "variant_set_failed", "message": str(exc)})

    if not unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False):
        errors.append({"code": "save_failed", "message": asset_path})

    verified_widget_names, verify_error = verify_accelbyte_ui_hierarchy(asset_path, widget_tree)
    verified_widget_count = len(verified_widget_names)
    expected_widget_names = get_spec_widget_names(spec["root"])
    missing_widget_names = [name for name in expected_widget_names if name not in verified_widget_names]
    if verify_error:
        errors.append({"code": "widget_hierarchy_unverified", "message": verify_error})
    elif missing_widget_names:
        errors.append(
            {
                "code": "widget_hierarchy_mismatch",
                "message": "Generated Widget Blueprint is missing widgets from the spec.",
                "missing_widget_names": missing_widget_names,
                "expected_widget_names": expected_widget_names,
                "verified_widget_names": verified_widget_names,
            }
        )
    elif verified_widget_count == 0:
        errors.append(
            {
                "code": "widget_hierarchy_empty",
                "message": "Generated Widget Blueprint has an empty widget hierarchy.",
            }
        )

    return _report(
        not errors,
        asset_path,
        parent_class_path,
        expected_widget_count,
        verified_widget_count,
        verified_widget_names,
        warnings,
        errors,
    )


def build_widget_tree(widget_tree, node: dict):
    widget = widget_tree.construct_widget(resolve_widget_class(node), node["name"])
    apply_widget_properties(widget, node)
    for child in node.get("children", []):
        child_widget = build_widget_tree(widget_tree, child)
        attach_child(widget, child_widget)
    return widget


def attach_child(parent, child) -> None:
    if hasattr(parent, "add_child"):
        parent.add_child(child)
        return
    if hasattr(parent, "set_content"):
        parent.set_content(child)
        return
    raise RuntimeError(f"Widget '{parent.get_name()}' cannot contain child '{child.get_name()}'.")


def get_widget_tree(generated_blueprint):
    if hasattr(generated_blueprint, "widget_tree"):
        return generated_blueprint.widget_tree
    try:
        return generated_blueprint.get_editor_property("widget_tree")
    except Exception:
        return None


def get_widget_tree_names(widget_tree) -> list[str]:
    root_widget = None
    try:
        root_widget = widget_tree.get_editor_property("root_widget")
    except Exception:
        root_widget = getattr(widget_tree, "root_widget", None)

    if root_widget is None:
        return []

    names = []
    visit_widget(root_widget, names)
    return names


def visit_widget(widget, names: list[str]) -> None:
    names.append(widget.get_name())
    if hasattr(widget, "get_children_count") and hasattr(widget, "get_child_at"):
        for index in range(widget.get_children_count()):
            visit_widget(widget.get_child_at(index), names)
        return
    if hasattr(widget, "get_content"):
        child = widget.get_content()
        if child is not None:
            visit_widget(child, names)


def populate_accelbyte_ui_from_json(asset_path: str, spec: dict) -> tuple[bool, str | None]:
    helper = getattr(unreal, "AccelByteUIToolsLibrary", None)
    if helper is None:
        return False, "unreal.AccelByteUIToolsLibrary is not exposed."
    try:
        result = helper.populate_accelbyte_ui_from_json(asset_path, json.dumps(spec))
    except Exception as exc:
        return False, str(exc)
    if isinstance(result, tuple):
        return bool(result[0]), result[1] if len(result) > 1 else None
    return bool(result), None


def verify_accelbyte_ui_hierarchy(asset_path: str, widget_tree) -> tuple[list[str], str | None]:
    helper = getattr(unreal, "AccelByteUIToolsLibrary", None)
    if helper is not None:
        try:
            result = helper.read_accelbyte_ui_hierarchy(asset_path)
        except Exception as exc:
            return [], str(exc)
        if isinstance(result, tuple):
            count = int(result[0])
            names = list(result[1]) if len(result) > 1 and result[1] is not None else []
            error = result[2] if len(result) > 2 else None
            return names[:count] if names else names, error or None

    if widget_tree is None:
        return [], "WidgetTree is unavailable."
    return get_widget_tree_names(widget_tree), None


def resolve_widget_class(widget_type_or_node):
    class_path = None
    widget_type = widget_type_or_node
    if isinstance(widget_type_or_node, dict):
        class_path = widget_type_or_node.get("class_path")
        widget_type = widget_type_or_node.get("type")
    if class_path:
        loaded = unreal.load_class(None, class_path)
        if loaded is None:
            raise RuntimeError(f"Widget class could not be loaded: {class_path}")
        return loaded

    classes = {
        "CanvasPanel": unreal.CanvasPanel,
        "Overlay": unreal.Overlay,
        "VerticalBox": unreal.VerticalBox,
        "HorizontalBox": unreal.HorizontalBox,
        "SizeBox": unreal.SizeBox,
        "Border": unreal.Border,
        "SafeZone": unreal.SafeZone,
        "ScaleBox": unreal.ScaleBox,
        "ScrollBox": unreal.ScrollBox,
        "ListView": unreal.ListView,
        "TileView": unreal.TileView,
        "TreeView": unreal.TreeView,
        "WidgetSwitcher": unreal.WidgetSwitcher,
        "UniformGridPanel": unreal.UniformGridPanel,
        "WrapBox": unreal.WrapBox,
        "TextBlock": unreal.TextBlock,
        "Button": unreal.Button,
        "EditableTextBox": unreal.EditableTextBox,
        "Image": unreal.Image,
        "Spacer": unreal.Spacer,
    }
    if widget_type == "AccelByteWarsButtonBase":
        loaded = unreal.load_class(None, "/Script/AccelByteWars.AccelByteWarsButtonBase")
        if loaded is None:
            raise RuntimeError("AccelByteWarsButtonBase could not be loaded.")
        return loaded
    klass = classes.get(widget_type)
    if klass is not None:
        return klass
    alias_path = AGS_COMPONENT_ALIASES.get(widget_type)
    if alias_path:
        loaded = unreal.load_class(None, alias_path)
        if loaded is None:
            raise RuntimeError(f"AGS component class could not be loaded: {alias_path}")
        return loaded
    raise ValueError(f"Unsupported widget type: {widget_type}")


def apply_widget_properties(widget, node: dict) -> None:
    if "text" in node and hasattr(widget, "set_text"):
        widget.set_text(unreal.Text(node["text"]))
    style = node.get("style", {})
    if "color" in style and hasattr(widget, "set_color_and_opacity"):
        widget.set_color_and_opacity(unreal.SlateColor(unreal.LinearColor(*style["color"])))
    if "visibility" in node and hasattr(widget, "set_visibility"):
        visibility_map = {
            "visible": getattr(unreal.ESlateVisibility, "VISIBLE", None),
            "collapsed": getattr(unreal.ESlateVisibility, "COLLAPSED", None),
            "hidden": getattr(unreal.ESlateVisibility, "HIDDEN", None),
            "hit_test_invisible": getattr(unreal.ESlateVisibility, "HIT_TEST_INVISIBLE", None),
            "self_hit_test_invisible": getattr(unreal.ESlateVisibility, "SELF_HIT_TEST_INVISIBLE", None),
        } if hasattr(unreal, "ESlateVisibility") else {}
        vis = visibility_map.get(node["visibility"].lower())
        if vis is not None:
            widget.set_visibility(vis)
    if "entry_widget_class" in node:
        entry_class = unreal.load_class(None, node["entry_widget_class"])
        if entry_class is None:
            raise RuntimeError(f"Entry widget class could not be loaded: {node['entry_widget_class']}")
        if hasattr(widget, "set_entry_widget_class"):
            widget.set_entry_widget_class(entry_class)
        elif hasattr(widget, "set_editor_property"):
            widget.set_editor_property("entry_widget_class", entry_class)
    if node.get("type") in {"ListView", "TileView", "TreeView"} and hasattr(widget, "set_editor_property"):
        clipping = None
        if hasattr(unreal, "WidgetClipping"):
            clipping = getattr(unreal.WidgetClipping, "CLIP_TO_BOUNDS", None)
        if clipping is not None:
            widget.set_editor_property("clipping", clipping)
    if "selection_mode" in node and hasattr(widget, "set_selection_mode") and hasattr(unreal, "SelectionMode"):
        selection_map = {
            "none": getattr(unreal.SelectionMode, "NONE", None),
            "single": getattr(unreal.SelectionMode, "SINGLE", None),
            "multi": getattr(unreal.SelectionMode, "MULTI", None),
        }
        selection = selection_map.get(node["selection_mode"].lower())
        if selection is not None:
            widget.set_selection_mode(selection)
    if "orientation" in node and hasattr(widget, "set_orientation") and hasattr(unreal, "Orientation"):
        orientation_map = {
            "horizontal": getattr(unreal.Orientation, "ORIENT_HORIZONTAL", None),
            "vertical": getattr(unreal.Orientation, "ORIENT_VERTICAL", None),
        }
        orientation = orientation_map.get(node["orientation"].lower())
        if orientation is not None:
            widget.set_orientation(orientation)


def count_widgets(node: dict) -> int:
    return 1 + sum(count_widgets(child) for child in node.get("children", []))


def get_spec_widget_names(node: dict) -> list[str]:
    names = [node["name"]]
    for child in node.get("children", []):
        names.extend(get_spec_widget_names(child))
    return names


def _report(
    ok: bool,
    asset_path: str | None,
    parent_class: str | None,
    expected_widget_count: int,
    verified_widget_count: int,
    verified_widget_names: list[str],
    warnings: list,
    errors: list,
) -> dict:
    return {
        "ok": ok,
        "asset_path": asset_path,
        "parent_class": parent_class,
        "expected_widget_count": expected_widget_count,
        "verified_widget_count": verified_widget_count,
        "verified_widget_names": verified_widget_names,
        "warnings": warnings,
        "errors": errors,
    }


def write_report(spec_path: Path, report: dict) -> None:
    output_dir = find_project_root(spec_path) / "Saved" / "AccelByteUITools"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{spec_path.stem}.report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def find_project_root(path: Path) -> Path:
    resolved = path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if any(parent.glob("*.uproject")):
            return parent
    return Path.cwd()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
