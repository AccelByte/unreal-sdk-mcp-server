import unittest

try:
    from Plugins.AccelByteUITools.Tools.ags_recipe_selector import (
        RecipeSelection,
        select_ags_recipe,
    )
except ModuleNotFoundError:
    from data.AccelByteUITools.Tools.ags_recipe_selector import (
        RecipeSelection,
        select_ags_recipe,
    )


class AGSRecipeSelectorTests(unittest.TestCase):
    def test_selects_auth_recipe_for_login_requests(self):
        selection = select_ags_recipe("Build an AGS login screen")

        self.assertEqual(
            selection,
            RecipeSelection(
                layout="AGS_CenteredPanel",
                recipe="ags_login_panel.json",
                reason="auth",
            ),
        )

    def test_selects_matchmaking_status_recipe(self):
        selection = select_ags_recipe("Show matchmaking queue status and allow cancel")

        self.assertEqual(selection.layout, "AGS_StatusOverlay")
        self.assertEqual(selection.recipe, "ags_matchmaking_panel.json")

    def test_selects_list_recipe_for_social_and_sessions(self):
        cases = {
            "friends list with requests": "ags_friends_panel.json",
            "session browser with join buttons": "ags_session_browser_panel.json",
            "cloud save slots": "ags_cloud_save_slots_panel.json",
        }

        for text, recipe in cases.items():
            with self.subTest(text=text):
                selection = select_ags_recipe(text)
                self.assertEqual(selection.layout, "AGS_ListPanel")
                self.assertEqual(selection.recipe, recipe)

    def test_selects_grid_recipe_for_store(self):
        selection = select_ags_recipe("in-game store grid with wallet balance")

        self.assertEqual(selection.layout, "AGS_GridPanel")
        self.assertEqual(selection.recipe, "ags_store_grid_panel.json")

    def test_selects_expanded_feature_recipes(self):
        cases = {
            "party members and invite code": ("AGS_ListPanel", "ags_party_panel.json"),
            "achievement grid with unlock progress": ("AGS_GridPanel", "ags_achievements_grid_panel.json"),
            "player stats summary": ("AGS_ListPanel", "ags_stats_summary_panel.json"),
            "wallet balance": ("AGS_ListPanel", "ags_wallet_panel.json"),
            "owned entitlements inventory": ("AGS_ListPanel", "ags_entitlements_panel.json"),
            "notification inbox": ("AGS_ListPanel", "ags_notifications_panel.json"),
            "account link conflict": ("AGS_CenteredPanel", "ags_account_link_panel.json"),
            "session expired login prompt": ("AGS_CenteredPanel", "ags_session_expired_panel.json"),
            "delete cloud save confirmation": ("AGS_ActionModal", "ags_action_modal.json"),
        }

        for text, expected in cases.items():
            with self.subTest(text=text):
                selection = select_ags_recipe(text)
                self.assertEqual((selection.layout, selection.recipe), expected)

    def test_selects_leaderboard_recipe(self):
        selection = select_ags_recipe("weekly leaderboard with own rank")

        self.assertEqual(selection.layout, "AGS_ListPanel")
        self.assertEqual(selection.recipe, "ags_leaderboard_panel.json")

    def test_unknown_async_operation_uses_generic_centered_fallback(self):
        selection = select_ags_recipe("run an AGS GDPR export request")

        self.assertEqual(selection.layout, "AGS_CenteredPanel")
        self.assertEqual(selection.recipe, "ags_generic_async_panel.json")
        self.assertEqual(selection.component, "WBP_AGS_GenericAsyncActionBlock")

    def test_selects_multiplayer_game_ui_patterns(self):
        cases = {
            "create a season pass progress screen": ("AGS_SeasonPassPanel", "ags_season_pass_panel.json"),
            "make a battle pass rewards widget": ("AGS_SeasonPassPanel", "ags_season_pass_panel.json"),
            "create a guild management panel": ("AGS_TabbedManagementPanel", "ags_guild_management_panel.json"),
            "make a clan roster screen": ("AGS_TabbedManagementPanel", "ags_guild_management_panel.json"),
            "make a news feed widget": ("AGS_FeedPanel", "ags_news_feed_panel.json"),
            "create a tournament bracket display": ("AGS_BracketPanel", "ags_tournament_bracket_panel.json"),
            "build a lobby browser": ("AGS_ListPanel", "ags_session_browser_panel.json"),
            "show a squad loadout grid": ("AGS_GridPanel", "ags_store_grid_panel.json"),
            "create a party finder": ("AGS_ListPanel", "ags_notifications_panel.json"),
            "voice channel social hub": ("AGS_TabbedPanel", "ags_tabbed_social_panel.json"),
            "report player moderation modal": ("AGS_ActionModal", "ags_action_modal.json"),
        }

        for text, expected in cases.items():
            with self.subTest(text=text):
                selection = select_ags_recipe(text)
                self.assertEqual((selection.layout, selection.recipe), expected)


if __name__ == "__main__":
    unittest.main()
