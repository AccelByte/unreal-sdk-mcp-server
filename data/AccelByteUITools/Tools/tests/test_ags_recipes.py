import json
from pathlib import Path
import unittest

try:
    from Plugins.AccelByteUITools.Tools.widget_spec import load_spec_from_dict
except ModuleNotFoundError:
    from data.AccelByteUITools.Tools.widget_spec import load_spec_from_dict


RECIPE_DIR = Path(__file__).resolve().parents[1] / "specs" / "recipes"


def _parse_bundled_recipe(data: dict):
    return load_spec_from_dict(data, enforce_generated_ags_policy=False)


def _child_has_valid_overlay_slot(child: dict) -> bool:
    slot = child.get("slot")
    if not isinstance(slot, dict):
        return False
    return slot.get("h_align") == "fill" and slot.get("v_align") == "fill"
EXPECTED_RECIPES = {
    "ags_account_link_panel.json",
    "ags_action_modal.json",
    "ags_achievements_grid_panel.json",
    "ags_login_panel.json",
    "ags_matchmaking_panel.json",
    "ags_leaderboard_panel.json",
    "ags_friends_panel.json",
    "ags_party_panel.json",
    "ags_session_browser_panel.json",
    "ags_session_expired_panel.json",
    "ags_split_detail_panel.json",
    "ags_stats_summary_panel.json",
    "ags_store_grid_panel.json",
    "ags_tabbed_social_panel.json",
    "ags_entitlements_panel.json",
    "ags_wallet_panel.json",
    "ags_cloud_save_slots_panel.json",
    "ags_notifications_panel.json",
    "ags_generic_async_panel.json",
    "ags_guild_management_panel.json",
    "ags_news_feed_panel.json",
    "ags_season_pass_panel.json",
    "ags_tournament_bracket_panel.json",
    "ags_user_profile_panel.json",
}
DIRECT_LAYOUT_RECIPES = {
    "ags_user_profile_panel.json",
}
REQUIRED_STATES = {
    "idle",
    "loading",
    "success",
    "empty",
    "error",
}
STATE_SWITCHER_SUFFIXES = [
    "_IdleState",
    "_LoadingState",
    "_SuccessState",
    "_EmptyState",
    "_ErrorState",
]


class AGSRecipeTests(unittest.TestCase):
    def test_expected_recipes_exist(self):
        recipes = {path.name for path in RECIPE_DIR.glob("*.json")}

        self.assertEqual(recipes, EXPECTED_RECIPES)

    def test_recipes_validate_and_reference_plugin_components(self):
        for recipe_path in sorted(RECIPE_DIR.glob("*.json")):
            with self.subTest(recipe=recipe_path.name):
                data = json.loads(recipe_path.read_text(encoding="utf-8"))
                spec = _parse_bundled_recipe(data)
                class_paths = [
                    node.class_path for node in spec.root.walk() if node.class_path is not None
                ]

                if recipe_path.name in DIRECT_LAYOUT_RECIPES:
                    self.assertEqual(class_paths, [])
                    continue

                self.assertTrue(class_paths)
                self.assertTrue(
                    all(path.startswith("/AccelByteUITools/AGSUI/") for path in class_paths)
                )

    def test_recipes_use_ags_panel_parent(self):
        for recipe_path in sorted(RECIPE_DIR.glob("*.json")):
            with self.subTest(recipe=recipe_path.name):
                data = json.loads(recipe_path.read_text(encoding="utf-8"))

                self.assertEqual(data["parent_class"], "/Script/AccelByteUITools.AGSPanelBase")

    def test_recipes_include_required_state_components(self):
        for recipe_path in sorted(RECIPE_DIR.glob("*.json")):
            with self.subTest(recipe=recipe_path.name):
                if recipe_path.name in DIRECT_LAYOUT_RECIPES:
                    continue

                data = json.loads(recipe_path.read_text(encoding="utf-8"))
                names = {node.name.lower() for node in _parse_bundled_recipe(data).root.walk()}

                for state in REQUIRED_STATES:
                    self.assertTrue(
                        any(state in name for name in names),
                        f"{recipe_path.name} is missing a {state} state widget",
                    )

    def test_stateful_recipes_use_exactly_one_ordered_state_switcher(self):
        for recipe_path in sorted(RECIPE_DIR.glob("*.json")):
            with self.subTest(recipe=recipe_path.name):
                if recipe_path.name in DIRECT_LAYOUT_RECIPES:
                    continue

                data = json.loads(recipe_path.read_text(encoding="utf-8"))
                # StateSwitcher is now inside ContentContainer (root.children[0].children[0])
                container_children = data["root"].get("children", [{}])[0].get("children", [])
                state_switchers = [
                    child
                    for child in container_children
                    if child.get("name") == "StateSwitcher"
                ]

                self.assertEqual(len(state_switchers), 1)
                self.assertEqual(state_switchers[0]["type"], "WidgetSwitcher")
                self.assertTrue(state_switchers[0].get("is_variable"))
                self.assertTrue(_child_has_valid_overlay_slot(state_switchers[0]))

                names = [child["name"] for child in state_switchers[0].get("children", [])]
                self.assertEqual(len(names), len(STATE_SWITCHER_SUFFIXES))
                for name, suffix in zip(names, STATE_SWITCHER_SUFFIXES):
                    self.assertTrue(
                        name.endswith(suffix),
                        f"{recipe_path.name} has StateSwitcher child '{name}' where '{suffix}' was expected",
                    )

    def test_stateful_recipes_use_border_root_with_content_container(self):
        for recipe_path in sorted(RECIPE_DIR.glob("*.json")):
            with self.subTest(recipe=recipe_path.name):
                if recipe_path.name in DIRECT_LAYOUT_RECIPES:
                    continue

                data = json.loads(recipe_path.read_text(encoding="utf-8"))
                root = data["root"]
                self.assertEqual(root["type"], "Border")
                self.assertEqual(root["name"], "PanelBackground")

                children = root.get("children", [])
                self.assertEqual(len(children), 1, f"{recipe_path.name} root must have exactly 1 child (ContentContainer)")
                container = children[0]
                self.assertEqual(container["type"], "Overlay")
                self.assertEqual(container["name"], "ContentContainer")
                self.assertEqual(container.get("padding"), [20, 20, 20, 20])
                self.assertTrue(
                    _child_has_valid_overlay_slot(container),
                    f"ContentContainer in {recipe_path.name} is missing fill slot",
                )
                for child in container.get("children", []):
                    self.assertTrue(
                        _child_has_valid_overlay_slot(child),
                        f"{child['name']} in {recipe_path.name} is missing a valid overlay slot",
                    )

    def test_direct_layout_recipes_use_border_root_with_content_container(self):
        for recipe_name in DIRECT_LAYOUT_RECIPES:
            data = json.loads((RECIPE_DIR / recipe_name).read_text(encoding="utf-8"))
            root = data["root"]
            self.assertEqual(root["type"], "Border")
            self.assertEqual(root["name"], "PanelBackground")
            children = root.get("children", [])
            self.assertEqual(len(children), 1)
            container = children[0]
            self.assertEqual(container["type"], "Overlay")
            self.assertEqual(container["name"], "ContentContainer")

    def test_multiplayer_recipes_use_expected_game_ui_structures(self):
        season_pass = _parse_bundled_recipe(
            json.loads((RECIPE_DIR / "ags_season_pass_panel.json").read_text(encoding="utf-8"))
        )
        guild = _parse_bundled_recipe(
            json.loads((RECIPE_DIR / "ags_guild_management_panel.json").read_text(encoding="utf-8"))
        )
        news = _parse_bundled_recipe(
            json.loads((RECIPE_DIR / "ags_news_feed_panel.json").read_text(encoding="utf-8"))
        )
        bracket = _parse_bundled_recipe(
            json.loads((RECIPE_DIR / "ags_tournament_bracket_panel.json").read_text(encoding="utf-8"))
        )

        for node_name in ("FreeRewardTileView", "PremiumRewardTileView"):
            tile_view = next(node for node in season_pass.root.walk() if node.name == node_name and node.type == "TileView")
            self.assertEqual(tile_view.entry_width, 256)
            self.assertEqual(tile_view.entry_height, 256)
        self.assertTrue(any(node.name == "RosterListView" and node.type == "ListView" for node in guild.root.walk()))
        self.assertTrue(any(node.name == "Guild_TabBar" and node.type == "HorizontalBox" for node in guild.root.walk()))
        self.assertTrue(any(node.name == "NewsListView" and node.type == "ListView" for node in news.root.walk()))
        self.assertTrue(any(node.name == "NewsFeed_FeaturedStory" for node in news.root.walk()))
        self.assertTrue(any(node.name == "BracketRoundColumns" and node.type == "HorizontalBox" for node in bracket.root.walk()))
        self.assertFalse(any(node.name == "TournamentListView" for node in bracket.root.walk()))


if __name__ == "__main__":
    unittest.main()
