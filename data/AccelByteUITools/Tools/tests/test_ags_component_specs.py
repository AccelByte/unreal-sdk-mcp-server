import json
from pathlib import Path
import unittest

try:
    from Plugins.AccelByteUITools.Tools.widget_spec import ValidationError, load_spec_from_dict
    from Plugins.AccelByteUITools.Tools.theme_tokens import load_theme_tokens
except ModuleNotFoundError:
    from data.AccelByteUITools.Tools.widget_spec import ValidationError, load_spec_from_dict
    from data.AccelByteUITools.Tools.theme_tokens import load_theme_tokens


COMPONENT_DIR = Path(__file__).resolve().parents[1] / "specs" / "components" / "agsui"
RECIPE_DIR = Path(__file__).resolve().parents[1] / "specs" / "recipes"
TEST_SPEC_DIR = Path(__file__).resolve().parents[1] / "specs" / "test"
TOKENS = load_theme_tokens()
EXPECTED_COMPONENT_ASSETS = {
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_BasePanel",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_ModalPanel",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_SectionHeader",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Divider",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_SecondaryButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_DangerButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_IconButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonSecondaryButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonDangerButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonIconButton",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_PasswordInput",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_SearchInput",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Toast",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Badge",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Avatar",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CurrencyPill",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListPanel",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_LeaderboardRow",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_EntitlementRow",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LoginBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AccountLinkBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionExpiredBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendsListBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendRow",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_IncomingFriendRequestRow",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_BlockUserRow",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyMemberRow",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_MatchmakingStatusBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionBrowserBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionRow",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LeaderboardBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementGridBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementCard",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StatsSummaryBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreGridBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_WalletBalanceBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_EntitlementsBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotsBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotRow",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_NotificationListBlock",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_GenericAsyncActionBlock",
}
EXPECTED_PARENT_BY_ASSET = {
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_BasePanel": "/Script/AccelByteUITools.AGSBasePanelBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_ModalPanel": "/Script/AccelByteUITools.AGSActionPanelBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_SectionHeader": "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Divider": "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton": "/Script/AccelByteUITools.AGSButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_SecondaryButton": "/Script/AccelByteUITools.AGSButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_DangerButton": "/Script/AccelByteUITools.AGSButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_IconButton": "/Script/AccelByteUITools.AGSIconButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonButton": "/Script/AccelByteUITools.AGSCommonButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonSecondaryButton": "/Script/AccelByteUITools.AGSCommonButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonDangerButton": "/Script/AccelByteUITools.AGSCommonButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonIconButton": "/Script/AccelByteUITools.AGSCommonIconButtonBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput": "/Script/AccelByteUITools.AGSTextInputBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_PasswordInput": "/Script/AccelByteUITools.AGSTextInputBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_SearchInput": "/Script/AccelByteUITools.AGSTextInputBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage": "/Script/AccelByteUITools.AGSStatusMessageBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator": "/Script/AccelByteUITools.AGSLoadingIndicatorBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState": "/Script/AccelByteUITools.AGSEmptyStateBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState": "/Script/AccelByteUITools.AGSErrorStateBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Toast": "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Badge": "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_Avatar": "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_CurrencyPill": "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/AccelByteUITools/AGSUI/Core/WBP_AGS_KeyValueRow": "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListPanel": "/Script/AccelByteUITools.AGSListRowBase",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow": "/Script/AccelByteUITools.AGSListRowBase",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow": "/Script/AccelByteUITools.AGSListRowBase",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_LeaderboardRow": "/Script/AccelByteUITools.AGSListRowBase",
    "/AccelByteUITools/AGSUI/Lists/WBP_AGS_EntitlementRow": "/Script/AccelByteUITools.AGSListRowBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LoginBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AccountLinkBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionExpiredBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendsListBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendRow": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_IncomingFriendRequestRow": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_BlockUserRow": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_PartyMemberRow": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_MatchmakingStatusBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionBrowserBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_SessionRow": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LeaderboardBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementGridBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementCard": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StatsSummaryBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreGridBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_WalletBalanceBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_EntitlementsBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotsBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_CloudSaveSlotRow": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_NotificationListBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
    "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_GenericAsyncActionBlock": "/Script/AccelByteUITools.AGSFeatureBlockBase",
}
LIST_ENTRY_PARENT_CLASSES = {
    "/Script/AccelByteUITools.AGSLabelValueWidgetBase",
    "/Script/AccelByteUITools.AGSListRowBase",
    "/Script/AccelByteUITools.AGSFeatureBlockBase",
}
ITEM_SURFACE_COMPONENTS = {
    "list_row.json",
    "player_row.json",
    "leaderboard_row.json",
    "entitlement_row.json",
    "feature_friend_row.json",
    "feature_party_member_row.json",
    "feature_block_user_row.json",
    "feature_cloud_save_slot_row.json",
    "feature_session_row.json",
    "feature_incoming_friend_row.json",
    "feature_achievement_card.json",
    "feature_store_item_card.json",
}
ITEM_BACKGROUND_COLOR = TOKENS["colors"]["bg"]["item"]
ITEM_BORDER_COLOR = TOKENS["colors"]["border"]["control"]


def _load_bundled_spec(path: Path):
    return load_spec_from_dict(
        json.loads(path.read_text(encoding="utf-8")),
        enforce_generated_ags_policy=False,
    )


def _parse_bundled_spec(raw: dict):
    return load_spec_from_dict(raw, enforce_generated_ags_policy=False)


class AGSComponentSpecTests(unittest.TestCase):
    def test_component_specs_cover_full_catalog(self):
        component_asset_paths = {
            _load_bundled_spec(path).asset_path
            for path in COMPONENT_DIR.glob("*.json")
        }

        self.assertEqual(component_asset_paths, EXPECTED_COMPONENT_ASSETS)

    def test_component_specs_validate_under_plugin_content(self):
        component_specs = sorted(COMPONENT_DIR.glob("*.json"))

        self.assertTrue(component_specs)
        for spec_path in component_specs:
            with self.subTest(spec=spec_path.name):
                raw = json.loads(spec_path.read_text(encoding="utf-8"))
                spec = _load_bundled_spec(spec_path)

                self.assertEqual(raw.get("style_mode"), "agsui")
                self.assertEqual(spec.style_mode, "agsui")
                self.assertTrue(spec.asset_path.startswith("/AccelByteUITools/AGSUI/"))
                self.assertTrue(spec.parent_class.startswith("/Script/AccelByteUITools."))

    def test_component_specs_use_focused_parent_classes(self):
        for path in sorted(COMPONENT_DIR.glob("*.json")):
            spec = _load_bundled_spec(path)
            with self.subTest(spec=path.name):
                self.assertEqual(spec.parent_class, EXPECTED_PARENT_BY_ASSET[spec.asset_path])

    def test_recipe_class_paths_have_matching_component_specs(self):
        component_asset_paths = {
            _load_bundled_spec(path).asset_path
            for path in COMPONENT_DIR.glob("*.json")
        }

        for recipe_path in sorted(RECIPE_DIR.glob("*.json")):
            recipe = _load_bundled_spec(recipe_path)
            for node in recipe.root.walk():
                referenced_paths = [path for path in (node.class_path, node.entry_widget_class) if path is not None]
                for referenced_path in referenced_paths:
                    asset_path = referenced_path.removesuffix("_C")
                    asset_path = asset_path.rsplit(".", 1)[0]
                    with self.subTest(recipe=recipe_path.name, class_path=referenced_path):
                        self.assertIn(asset_path, component_asset_paths)

    def test_native_collection_recipes_use_entry_widget_classes(self):
        component_parents = {}
        for path in COMPONENT_DIR.glob("*.json"):
            spec = _load_bundled_spec(path)
            component_parents[spec.asset_path] = spec.parent_class

        collection_nodes = []
        for recipe_path in sorted(RECIPE_DIR.glob("*.json")):
            recipe = _load_bundled_spec(recipe_path)
            collection_nodes.extend(
                (recipe_path.name, node)
                for node in recipe.root.walk()
                if node.type in {"ListView", "TileView", "TreeView"}
            )

        self.assertTrue(collection_nodes)
        entry_classes = {node.entry_widget_class for _, node in collection_nodes}
        self.assertEqual(
            entry_classes,
            {
                "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow.WBP_AGS_PlayerRow_C",
                "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C",
                "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard.WBP_AGS_StoreItemCard_C",
            },
        )
        for recipe_name, node in collection_nodes:
            with self.subTest(recipe=recipe_name, node=node.name):
                self.assertIsNotNone(node.entry_widget_class)
                self.assertTrue(node.entry_widget_class.startswith("/AccelByteUITools/AGSUI/"))
                asset_path = node.entry_widget_class.removesuffix("_C").rsplit(".", 1)[0]
                self.assertIn(
                    component_parents[asset_path],
                    LIST_ENTRY_PARENT_CLASSES,
                    f"{node.entry_widget_class} must use a list-entry-capable AGS base class",
                )

    def test_card_grid_feature_blocks_use_tile_view(self):
        for filename in ("feature_achievement_grid_block.json", "feature_store_grid_block.json"):
            with self.subTest(spec=filename):
                spec = _load_bundled_spec(COMPONENT_DIR / filename)
                tile_view = next(node for node in spec.root.walk() if node.type == "TileView")

                self.assertIsNotNone(tile_view.entry_widget_class, "TileView must have entry_widget_class")
                self.assertEqual(tile_view.orientation, "vertical", "Grid TileView must use vertical orientation (left-to-right rows)")
                self.assertEqual(tile_view.entry_width, 256)
                self.assertEqual(tile_view.entry_height, 256)
                self.assertEqual(tile_view.horizontal_entry_spacing, TOKENS["spacing"]["entrySpacing"])
                self.assertEqual(tile_view.vertical_entry_spacing, TOKENS["spacing"]["entrySpacing"])

    def test_list_and_tile_items_use_consistent_surface_style(self):
        for filename in sorted(ITEM_SURFACE_COMPONENTS):
            with self.subTest(spec=filename):
                raw = json.loads((COMPONENT_DIR / filename).read_text(encoding="utf-8"))
                style = raw["root"]["style"]

                self.assertEqual(style["background_color"], ITEM_BACKGROUND_COLOR)
                self.assertEqual(style["border_color"], ITEM_BORDER_COLOR)
                self.assertEqual(style["border_width"], 1)

    def test_collection_specs_use_native_lists_with_spacing(self):
        for spec_dir in (COMPONENT_DIR, RECIPE_DIR, TEST_SPEC_DIR):
            for path in sorted(spec_dir.glob("*.json")):
                spec = _load_bundled_spec(path)
                with self.subTest(spec=path.name):
                    self.assertFalse(
                        any(node.type == "ScrollBox" for node in spec.root.walk()),
                        f"{path.name} must use native ListView/TileView instead of ScrollBox for collections",
                    )
                    for node in spec.root.walk():
                        if node.type in {"ListView", "TileView"}:
                            self.assertEqual(node.horizontal_entry_spacing, TOKENS["spacing"]["entrySpacing"])
                            self.assertEqual(node.vertical_entry_spacing, TOKENS["spacing"]["entrySpacing"])

    def test_core_button_and_input_visual_contract(self):
        for filename in ("core_base_button.json", "core_secondary_button.json", "core_danger_button.json"):
            with self.subTest(spec=filename):
                raw = json.loads((COMPONENT_DIR / filename).read_text(encoding="utf-8"))

                self.assertEqual(raw["root"]["type"], "Button")
                self.assertEqual(raw["root"]["name"], "InteractiveButton")
                self.assertEqual(raw["root"]["padding"], TOKENS["spacing"]["controlPadding"])

        for filename in ("core_text_input.json", "core_password_input.json", "core_search_input.json"):
            with self.subTest(spec=filename):
                raw = json.loads((COMPONENT_DIR / filename).read_text(encoding="utf-8"))
                spec = _parse_bundled_spec(raw)

                self.assertNotIn("InputBackground", [node.name for node in spec.root.walk()])
                self.assertEqual(raw["root"]["type"], "EditableTextBox")
                self.assertEqual(raw["root"]["name"], "ValueInput")
                self.assertTrue(raw["root"]["is_variable"])
                self.assertEqual(raw["root"]["padding"], TOKENS["spacing"]["controlPadding"])
                self.assertEqual(raw["root"]["style"], TOKENS["presets"]["input"])

    def test_core_button_contract_rejects_renamed_button_text(self):
        raw = json.loads((COMPONENT_DIR / "core_base_button.json").read_text(encoding="utf-8"))
        raw["root"]["children"][0]["name"] = "ButtonLabel"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(raw)

        self.assertEqual(raised.exception.code, "focused_widget_contract")
        self.assertIn("ButtonText", raised.exception.message)

    def test_core_text_input_contract_rejects_renamed_value_input(self):
        raw = json.loads((COMPONENT_DIR / "core_text_input.json").read_text(encoding="utf-8"))
        raw["root"]["name"] = "InputValue"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(raw)

        self.assertEqual(raised.exception.code, "focused_widget_contract")
        self.assertIn("ValueInput", raised.exception.message)

    def test_no_stale_dark_theme_literals_or_partial_input_styles(self):
        stale_dark_colors = {
            (0.08, 0.08, 0.1, 1.0),
            (0.08, 0.08, 0.10, 1.0),
            (0.13, 0.13, 0.16, 1.0),
            (0.11, 0.11, 0.14, 1.0),
        }
        required_input_style_keys = {
            "background_color",
            "color",
            "hint_color",
            "corner_radius",
            "border_color",
            "border_width",
        }

        for spec_dir in (COMPONENT_DIR, RECIPE_DIR):
            for path in sorted(spec_dir.glob("*.json")):
                raw = json.loads(path.read_text(encoding="utf-8"))
                spec = _parse_bundled_spec(raw)
                for node in spec.root.walk():
                    with self.subTest(spec=path.name, node=node.name):
                        for value in node.style.values():
                            if isinstance(value, list):
                                self.assertNotIn(tuple(value), stale_dark_colors)
                        if node.type == "EditableTextBox":
                            self.assertTrue(required_input_style_keys.issubset(set(node.style)))


if __name__ == "__main__":
    unittest.main()
