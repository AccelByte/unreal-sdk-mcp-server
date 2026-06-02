from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RecipeSelection:
    layout: str
    recipe: str | None
    reason: str
    component: str | None = None


def select_ags_recipe(request: str) -> RecipeSelection:
    text = request.casefold()

    if _contains_any(text, "account link", "account linking"):
        return RecipeSelection("AGS_CenteredPanel", "ags_account_link_panel.json", "account_link")
    if _contains_any(text, "session expired"):
        return RecipeSelection("AGS_CenteredPanel", "ags_session_expired_panel.json", "session_expired")
    if _contains_any(text, "season pass", "battle pass"):
        return RecipeSelection("AGS_SeasonPassPanel", "ags_season_pass_panel.json", "season_pass")
    if _contains_any(text, "tournament", "bracket", "elimination"):
        return RecipeSelection("AGS_BracketPanel", "ags_tournament_bracket_panel.json", "tournament_bracket")
    if _contains_any(text, "guild", "clan"):
        return RecipeSelection("AGS_TabbedManagementPanel", "ags_guild_management_panel.json", "guild_management")
    if _contains_any(text, "news feed", "news", "announcement", "announcements", "patch notes"):
        return RecipeSelection("AGS_FeedPanel", "ags_news_feed_panel.json", "news_feed")
    if _contains_any(text, "match summary", "scoreboard", "team score", "battle report", "post match"):
        return RecipeSelection("AGS_ListPanel", "ags_leaderboard_panel.json", "match_results")
    if _contains_any(text, "player profile", "profile"):
        return RecipeSelection("AGS_ProfilePanel", "ags_user_profile_panel.json", "player_profile")
    if _contains_any(text, "lobby browser", "custom room", "room settings", "server browser"):
        return RecipeSelection("AGS_ListPanel", "ags_session_browser_panel.json", "lobby_browser")
    if _contains_any(text, "party finder", "invite inbox", "invites"):
        return RecipeSelection("AGS_ListPanel", "ags_notifications_panel.json", "invites")
    if _contains_any(text, "squad loadout", "loadout", "cosmetic", "cosmetics"):
        return RecipeSelection("AGS_GridPanel", "ags_store_grid_panel.json", "loadout_grid")
    if _contains_word_any(text, "quest", "quests", "challenge", "challenges", "mission", "missions"):
        return RecipeSelection("AGS_GridPanel", "ags_achievements_grid_panel.json", "challenge_board")
    if _contains_any(text, "social hub", "voice", "channel", "channels"):
        return RecipeSelection("AGS_TabbedPanel", "ags_tabbed_social_panel.json", "social_hub")
    if _contains_any(text, "report player", "moderation", "block player"):
        return RecipeSelection("AGS_ActionModal", "ags_action_modal.json", "moderation")
    if _contains_any(text, "confirm", "confirmation", "delete", "unlink", "leave party", "buy item"):
        return RecipeSelection("AGS_ActionModal", "ags_action_modal.json", "action_modal")
    if _contains_any(text, "auth", "login"):
        return RecipeSelection("AGS_CenteredPanel", "ags_login_panel.json", "auth")
    if _contains_any(text, "matchmaking", "queue", "connecting", "reconnecting"):
        return RecipeSelection("AGS_StatusOverlay", "ags_matchmaking_panel.json", "matchmaking")
    if _contains_any(text, "party"):
        return RecipeSelection("AGS_ListPanel", "ags_party_panel.json", "party")
    if _contains_any(text, "friend", "social"):
        return RecipeSelection("AGS_ListPanel", "ags_friends_panel.json", "social")
    if _contains_any(text, "cloud save", "save slot", "save slots"):
        return RecipeSelection("AGS_ListPanel", "ags_cloud_save_slots_panel.json", "cloud_save")
    if _contains_any(text, "session browser", "sessions", "join session", "server browser"):
        return RecipeSelection("AGS_ListPanel", "ags_session_browser_panel.json", "sessions")
    if _contains_any(text, "leaderboard", "rank", "ranking"):
        return RecipeSelection("AGS_ListPanel", "ags_leaderboard_panel.json", "leaderboard")
    if _contains_any(text, "achievement"):
        return RecipeSelection("AGS_GridPanel", "ags_achievements_grid_panel.json", "achievements")
    if _contains_any(text, "stats", "statistic"):
        return RecipeSelection("AGS_ListPanel", "ags_stats_summary_panel.json", "stats")
    if _contains_any(text, "store", "shop", "commerce"):
        return RecipeSelection("AGS_GridPanel", "ags_store_grid_panel.json", "grid")
    if _contains_any(text, "wallet", "balance"):
        return RecipeSelection("AGS_ListPanel", "ags_wallet_panel.json", "wallet")
    if _contains_any(text, "entitlement", "inventory", "owned item"):
        return RecipeSelection("AGS_ListPanel", "ags_entitlements_panel.json", "entitlements")
    if _contains_any(text, "notification", "inbox"):
        return RecipeSelection("AGS_ListPanel", "ags_notifications_panel.json", "notifications")
    if _contains_any(text, "tab view", "tab panel", "tabbed", "tabs", " tab "):
        return RecipeSelection("AGS_TabbedPanel", "ags_tabbed_social_panel.json", "tab_view")

    return RecipeSelection(
        "AGS_CenteredPanel",
        "ags_generic_async_panel.json",
        "generic_async",
        component="WBP_AGS_GenericAsyncActionBlock",
    )


def _contains_any(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def _contains_word_any(text: str, *terms: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)
