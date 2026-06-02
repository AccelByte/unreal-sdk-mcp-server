import json
from pathlib import Path
import unittest

try:
    from Plugins.AccelByteUITools.Tools.theme_normalizer import normalize_theme
    from Plugins.AccelByteUITools.Tools.theme_tokens import load_theme_tokens
except ModuleNotFoundError:
    from data.AccelByteUITools.Tools.theme_normalizer import normalize_theme
    from data.AccelByteUITools.Tools.theme_tokens import load_theme_tokens


class ThemeNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.tokens = load_theme_tokens()

    def test_applies_generated_ags_defaults(self):
        spec = normalize_theme(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_ThemeSafe",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {"type": "TextBlock", "name": "TitleText", "text": "Title"},
                        {
                            "type": "AGSTextInput",
                            "name": "SearchInput",
                            "style": {"color": [0.2, 0.2, 0.2, 1.0]},
                        },
                        {"type": "AGSBaseButton", "name": "SubmitButton"},
                        {
                            "type": "ListView",
                            "name": "RowsListView",
                            "entry_widget_class": "/Game/AGS/UI/Generated/WBP_Row.WBP_Row_C",
                        },
                    ],
                },
            }
        )

        root = spec["root"]
        title, text_input, button, list_view = root["children"]
        expected_panel = dict(self.tokens["presets"]["panel"])
        expected_panel["background_color"] = [0.0, 0.0, 0.0, 0.1]
        self.assertEqual(root["style"], expected_panel)
        self.assertEqual(root["padding"], self.tokens["spacing"]["panelPadding"])
        self.assertEqual(title["style"]["color"], self.tokens["colors"]["text"]["primary"])
        self.assertEqual(text_input["padding"], self.tokens["spacing"]["controlPadding"])
        self.assertEqual(button["padding"], self.tokens["spacing"]["controlPadding"])
        self.assertEqual(list_view["horizontal_entry_spacing"], self.tokens["spacing"]["entrySpacing"])
        self.assertEqual(list_view["vertical_entry_spacing"], self.tokens["spacing"]["entrySpacing"])

    def test_button_role_presets_are_name_based(self):
        root = normalize_theme(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_Buttons",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "HorizontalBox",
                    "name": "Root",
                    "children": [
                        {"type": "Button", "name": "CancelButton"},
                        {"type": "Button", "name": "DeleteButton"},
                    ],
                },
            }
        )["root"]

        self.assertEqual(root["children"][0]["style"], self.tokens["presets"]["secondaryButton"])
        self.assertEqual(root["children"][1]["style"], self.tokens["presets"]["dangerButton"])

    def test_flow_container_child_slot_padding_defaults_are_added(self):
        root = normalize_theme(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_Spacing",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "VerticalBox",
                    "name": "RootStack",
                    "children": [
                        {"type": "TextBlock", "name": "FirstText"},
                        {"type": "TextBlock", "name": "SecondText", "slot": {"padding": [1, 2, 3, 4]}},
                        {
                            "type": "HorizontalBox",
                            "name": "ButtonRow",
                            "children": [
                                {"type": "AGSBaseButton", "name": "ConfirmButton"},
                                {"type": "AGSBaseButton", "name": "CancelButton"},
                            ],
                        },
                        {
                            "type": "WrapBox",
                            "name": "TagWrap",
                            "children": [{"type": "TextBlock", "name": "TagText"}],
                        },
                    ],
                },
            }
        )["root"]

        self.assertEqual(root["children"][0]["slot"]["padding"], [0, 0, 0, 8])
        self.assertEqual(root["children"][1]["slot"]["padding"], [1, 2, 3, 4])
        self.assertEqual(root["children"][2]["children"][0]["slot"]["padding"], [0, 0, 8, 0])
        self.assertEqual(root["children"][3]["children"][0]["slot"]["padding"], [0, 0, 8, 8])

    def test_low_confidence_auto_preserves_blank_project_panel_background(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Custom",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [1.0, 1.0, 1.0, 1.0]},
            },
        }

        normalized = normalize_theme(spec, style_context={"confidence": "low"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [1.0, 1.0, 1.0, 1.0])

    def test_project_style_panel_background_fallback_applies_with_confidence(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Custom",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [0.0, 0.0, 0.0, 0.1])

    def test_project_panel_background_fallback_preserves_explicit_color(self):
        spec = {
            "asset_path": "/Game/ByteWars/UI/Generated/WBP_Custom",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [0.2, 0.2, 0.2, 0.5]},
            },
        }

        self.assertEqual(normalize_theme(spec, style_context={"confidence": "medium"}), spec)

    def test_project_panel_background_preserves_explicit_white(self):
        spec = {
            "asset_path": "/Game/ByteWars/UI/Generated/WBP_Custom",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [1.0, 1.0, 1.0, 1.0]},
            },
        }

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [1.0, 1.0, 1.0, 1.0])

    def test_explicit_agsui_mode_preserves_legacy_white_preset(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Custom",
            "parent_class": "/Script/UMG.UserWidget",
            "style_mode": "agsui",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [1.0, 1.0, 1.0, 1.0]},
            },
        }

        normalized = normalize_theme(spec, style_context={"confidence": "high"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [1.0, 1.0, 1.0, 1.0])

    def test_generated_ags_collection_entry_keeps_project_style_background(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardEntry",
            "parent_class": "/Script/AccelByteWars.AccelByteWarsWidgetEntry",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [0.0, 0.0, 0.0, 0.1]},
                "children": [
                    {
                        "type": "Overlay",
                        "name": "ContentContainer",
                        "padding": [16, 10, 16, 10],
                    }
                ],
            },
        }

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized, spec)

    def test_generated_ags_collection_entry_gets_project_background_fallback(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/Store/WBP_AGS_StoreItemCard",
            "parent_class": "/Script/AccelByteWars.AccelByteWarsWidgetEntry",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [0.0, 0.0, 0.0, 0.1])
        self.assertNotEqual(normalized["root"]["style"], self.tokens["presets"]["panel"])

    def test_bundled_agsui_card_preserves_ags_item_background_with_project_context(self):
        spec_path = (
            Path(__file__).resolve().parents[1]
            / "specs"
            / "components"
            / "agsui"
            / "feature_store_item_card.json"
        )
        spec = json.loads(spec_path.read_text(encoding="utf-8"))

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized["style_mode"], "agsui")
        self.assertEqual(normalized["root"]["style"]["background_color"], self.tokens["colors"]["bg"]["item"])

    def test_generated_ags_panel_preserves_explicit_project_background(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_Store",
            "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [0.0, 0.0, 0.0, 0.1], "corner_radius": 8},
                "children": [{"type": "Overlay", "name": "ContentContainer"}],
            },
        }

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [0.0, 0.0, 0.0, 0.1])
        self.assertEqual(normalized["root"]["style"]["corner_radius"], self.tokens["presets"]["panel"]["corner_radius"])
        self.assertEqual(normalized["root"]["style"]["border_color"], self.tokens["presets"]["panel"]["border_color"])
        self.assertEqual(normalized["root"]["style"]["border_width"], self.tokens["presets"]["panel"]["border_width"])

    def test_generated_ags_panel_gets_project_background_fallback(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_Store",
            "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [0.0, 0.0, 0.0, 0.1])
        self.assertEqual(normalized["root"]["style"]["corner_radius"], self.tokens["presets"]["panel"]["corner_radius"])
        self.assertEqual(normalized["root"]["style"]["border_color"], self.tokens["presets"]["panel"]["border_color"])
        self.assertEqual(normalized["root"]["style"]["border_width"], self.tokens["presets"]["panel"]["border_width"])

    def test_generated_ags_panel_preserves_explicit_white(self):
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_Store",
            "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [1.0, 1.0, 1.0, 1.0]},
                "children": [{"type": "Overlay", "name": "ContentContainer"}],
            },
        }

        normalized = normalize_theme(spec, style_context={"confidence": "medium"})

        self.assertEqual(normalized["root"]["style"]["background_color"], [1.0, 1.0, 1.0, 1.0])

    def test_non_generated_non_panel_specs_are_left_unchanged(self):
        spec = {
            "asset_path": "/Game/ByteWars/UI/Widgets/WBP_Custom",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "TextBlock", "name": "TitleText"},
        }

        self.assertEqual(normalize_theme(spec), spec)

    def test_low_confidence_uses_preset_panel_background(self):
        """Empty/blank projects with low style confidence should get the AGS preset white background."""
        spec = normalize_theme(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_EmptyProject",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {"type": "Border", "name": "PanelBackground", "children": []},
            },
            style_context={"confidence": "low"},
        )
        self.assertEqual(spec["root"]["style"]["background_color"], [1.0, 1.0, 1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
