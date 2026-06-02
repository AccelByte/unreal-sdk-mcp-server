import unittest

try:
    from Plugins.AccelByteUITools.Tools.theme_normalizer import normalize_theme
    from Plugins.AccelByteUITools.Tools.widget_spec import (
        ValidationError,
        canonicalize_spec,
        load_spec_from_dict,
    )
except ModuleNotFoundError:
    from data.AccelByteUITools.Tools.theme_normalizer import normalize_theme
    from data.AccelByteUITools.Tools.widget_spec import (
        ValidationError,
        canonicalize_spec,
        load_spec_from_dict,
    )


class WidgetSpecTests(unittest.TestCase):
    def _valid_generated_ags_stateful_panel(self):
        return {
            "asset_path": "/Game/AGS/UI/Generated/WBP_StatefulPanel",
            "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
            "root": {
                "type": "Border",
                "name": "PanelBackground",
                "style": {"background_color": [0.0, 0.0, 0.0, 0.1], "corner_radius": 8, "border_color": [0.84, 0.87, 0.92, 1.0], "border_width": 1},
                "children": [
                    {
                        "type": "Overlay",
                        "name": "ContentContainer",
                        "padding": [20, 20, 20, 20],
                        "slot": {"h_align": "fill", "v_align": "fill"},
                        "children": [
                            {
                                "type": "WidgetSwitcher",
                                "name": "StateSwitcher",
                                "is_variable": True,
                                "slot": {"h_align": "fill", "v_align": "fill"},
                                "children": [
                                    {"type": "AGSStatusMessage", "name": "IdlePanel", "is_variable": True},
                                    {"type": "AGSLoadingIndicator", "name": "LoadingPanel", "is_variable": True},
                                    {"type": "VerticalBox", "name": "SuccessPanel", "is_variable": True},
                                    {"type": "AGSEmptyState", "name": "EmptyPanel", "is_variable": True},
                                    {"type": "AGSErrorState", "name": "ErrorPanel", "is_variable": True},
                                ],
                            }
                        ],
                    }
                ],
            },
        }

    def test_accepts_typed_common_ui_style_class_fields(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_StyledCommonUiPanel",
                "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
                "ui_mode": "common_ui",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "TextBlock",
                                    "name": "TitleText",
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                    "text_style_class": "/Game/UI/Styles/B_TitleTextStyle.B_TitleTextStyle_C",
                                },
                                {
                                    "type": "AGSButton",
                                    "name": "SubmitButton",
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                    "button_style_class": "/Game/UI/Styles/B_PrimaryButtonStyle.B_PrimaryButtonStyle_C",
                                },
                            ],
                        }
                    ],
                },
            }
        )

        title = next(node for node in spec.root.walk() if node.name == "TitleText")
        button = next(node for node in spec.root.walk() if node.name == "SubmitButton")
        self.assertEqual(title.text_style_class, "/Game/UI/Styles/B_TitleTextStyle.B_TitleTextStyle_C")
        self.assertEqual(button.button_style_class, "/Game/UI/Styles/B_PrimaryButtonStyle.B_PrimaryButtonStyle_C")

    def test_loads_valid_spec_and_counts_widgets(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_SampleMenu",
                "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
                "root": {
                    "type": "CanvasPanel",
                    "name": "RootCanvas",
                    "children": [
                        {"type": "TextBlock", "name": "TitleText", "text": "Play"},
                        {
                            "type": "VerticalBox",
                            "name": "ButtonStack",
                            "children": [
                                {"type": "Button", "name": "PlayButton", "is_variable": True}
                            ],
                        },
                        {
                            "type": "EditableTextBox",
                            "name": "PasswordInput",
                            "hint_text": "Password",
                            "is_password": True,
                        },
                    ],
                },
            }
        )

        self.assertEqual(spec.asset_path, "/AccelByteUITools/AGSUI/Core/WBP_AGS_SampleMenu")
        self.assertEqual(spec.parent_class, "/Script/AccelByteWars.SampleMenuWidget")
        self.assertEqual(spec.widget_count(), 5)
        self.assertEqual(spec.variable_widget_names(), ["PlayButton"])

    def test_rejects_asset_path_outside_generated_ui(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/ByteWars/UI/WBP_HandMade",
                    "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
                    "root": {"type": "CanvasPanel", "name": "RootCanvas"},
                }
            )

        self.assertEqual(raised.exception.code, "asset_path_denied")

    def test_rejects_unsupported_widget_type(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/ByteWars/UI/Generated/WBP_Bad",
                    "parent_class": "/Script/AccelByteWars.BadWidget",
                    "root": {"type": "VirtualList", "name": "UnsupportedRoot"},
                }
            )

        self.assertEqual(raised.exception.code, "unsupported_widget")

    def test_accepts_native_collection_widgets_with_entry_metadata(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_NewsFeed",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "ListView",
                    "name": "NewsListView",
                    "is_variable": True,
                    "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C",
                    "selection_mode": "single",
                    "horizontal_entry_spacing": 4,
                    "vertical_entry_spacing": 4,
                    "preview_entries": [{"title": "Patch Notes"}],
                },
            }
        )

        self.assertEqual(spec.root.type, "ListView")
        self.assertEqual(
            spec.root.entry_widget_class,
            "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C",
        )
        self.assertEqual(spec.root.selection_mode, "single")
        self.assertEqual(spec.root.horizontal_entry_spacing, 4)
        self.assertEqual(spec.root.vertical_entry_spacing, 4)
        self.assertEqual(spec.root.preview_entries, ({"title": "Patch Notes"},))

    def test_accepts_tile_view_orientation(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_SeasonPass",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "TileView",
                    "name": "RewardTileView",
                    "entry_widget_class": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard.WBP_AGS_StoreItemCard_C",
                    "selection_mode": "none",
                    "orientation": "horizontal",
                    "entry_width": 256,
                    "entry_height": 256,
                },
            }
        )

        self.assertEqual(spec.root.orientation, "horizontal")
        self.assertEqual(spec.root.entry_width, 256)
        self.assertEqual(spec.root.entry_height, 256)

    def test_tile_view_entry_size_is_tile_view_only(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_BadList",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {
                        "type": "ListView",
                        "name": "RosterListView",
                        "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C",
                        "entry_width": 256,
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_collection_widgets_require_valid_entry_widget_class(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_BadList",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {"type": "ListView", "name": "RosterListView"},
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_BadList",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {
                        "type": "ListView",
                        "name": "RosterListView",
                        "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow",
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_accepts_class_path_widget_type(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CustomWidgetHost",
                "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
                "root": {
                    "type": "CanvasPanel",
                    "name": "RootCanvas",
                    "children": [
                        {
                            "type": "UserWidget",
                            "class_path": "/Game/ByteWars/UI/W_MenuButton.W_MenuButton_C",
                            "name": "GeneratedTestButton",
                        }
                    ],
                },
            }
        )

        self.assertEqual(spec.widget_count(), 2)
        self.assertEqual(
            spec.root.children[0].class_path,
            "/Game/ByteWars/UI/W_MenuButton.W_MenuButton_C",
        )

    def test_accepts_ags_plugin_component_alias_with_class_path(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoginPanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "AGSBaseButton",
                    "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
                    "name": "Btn_Login",
                    "is_variable": True,
                },
            }
        )

        self.assertEqual(spec.root.type, "AGSBaseButton")
        self.assertEqual(
            spec.root.class_path,
            "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
        )

    def test_rejects_malformed_class_path(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_BadClassPath",
                    "parent_class": "/Script/UMG.UserWidget",
                    "root": {
                        "type": "AGSBaseButton",
                        "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton",
                        "name": "Btn_Login",
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_accepts_accelbyte_ui_tools_plugin_content_asset_path(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_PathCheck",
                "parent_class": "/Script/AccelByteUITools.AGSButtonBase",
                "root": {"type": "Button", "name": "PrimaryButton", "is_variable": True},
            }
        )

        self.assertEqual(spec.asset_path, "/AccelByteUITools/AGSUI/Core/WBP_AGS_PathCheck")

    def test_accepts_responsive_container_types(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_ResponsivePanel",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "SafeZone",
                    "name": "RootSafeZone",
                    "children": [
                        {
                            "type": "ScaleBox",
                            "name": "ResponsiveScale",
                            "children": [
                                {
                                    "type": "WrapBox",
                                    "name": "CardWrap",
                                    "children": [
                                        {
                                            "type": "TextBlock",
                                            "name": "CardLabel",
                                            "text": "Card",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            }
        )

        self.assertEqual(spec.widget_count(), 4)

    def test_accepts_overlay_root_for_fullscreen_panels(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_OverlayPanel",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "Overlay",
                    "name": "RootOverlay",
                    "children": [
                        {
                            "type": "Border",
                            "name": "PanelBackground",
                            "slot": {"h_align": "fill", "v_align": "fill"},
                        }
                    ],
                },
            }
        )

        self.assertEqual(spec.root.type, "Overlay")

    def test_accepts_editable_text_hint_color_style(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_InputPanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "EditableTextBox",
                    "name": "ValueInput",
                    "hint_text": "Search",
                    "style": {
                        "color": [0.0, 0.0, 0.0, 1.0],
                        "hint_color": [0.45, 0.45, 0.48, 1.0],
                    },
                },
            }
        )

        self.assertEqual(spec.root.style["hint_color"], [0.45, 0.45, 0.48, 1.0])

    def test_accepts_rounded_light_style_fields(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_StyledButton",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Button",
                    "name": "PrimaryButton",
                    "style": {
                        "color": [0.043, 0.424, 1.0, 1.0],
                        "hover_color": [0.031, 0.341, 0.86, 1.0],
                        "pressed_color": [0.022, 0.251, 0.66, 1.0],
                        "border_color": [0.043, 0.424, 1.0, 1.0],
                        "border_width": 1,
                        "corner_radius": 6,
                    },
                    "padding": [8, 8, 8, 8],
                },
            }
        )

        self.assertEqual(spec.root.style["corner_radius"], 6)
        self.assertEqual(spec.root.style["border_width"], 1)

    def test_accepts_node_level_padding_for_controls(self):
        for widget_type in ("Button", "EditableTextBox"):
            with self.subTest(widget_type=widget_type):
                spec = load_spec_from_dict(
                    {
                        "asset_path": f"/AccelByteUITools/AGSUI/Core/WBP_AGS_{widget_type}Padding",
                        "parent_class": "/Script/UMG.UserWidget",
                        "root": {
                            "type": widget_type,
                            "name": "PaddedControl",
                            "padding": [8, 8, 8, 8],
                        },
                    }
                )

                self.assertEqual(spec.root.name, "PaddedControl")
                self.assertEqual(spec.root.padding, (8.0, 8.0, 8.0, 8.0))

    def test_rejects_invalid_node_level_padding(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_BadPadding",
                    "parent_class": "/Script/UMG.UserWidget",
                    "root": {
                        "type": "Button",
                        "name": "PaddedControl",
                        "padding": [8, -1, 8],
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_rejects_invalid_rounded_style_fields(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_BadStyle",
                    "parent_class": "/Script/UMG.UserWidget",
                    "root": {
                        "type": "Border",
                        "name": "Panel",
                        "style": {
                            "border_color": [1.0, 1.0, "blue", 1.0],
                            "corner_radius": -1,
                        },
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_generated_ags_collections_require_entry_spacing(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_MissingListSpacing",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {
                        "type": "ListView",
                        "name": "RosterListView",
                        "entry_widget_class": "/Game/AGS/UI/Generated/WBP_AGS_PlayerRowEntry.WBP_AGS_PlayerRowEntry_C",
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_generated_ags_specs_reject_non_core_plugin_class_paths(self):
        for class_path_key, class_path in (
            ("class_path", "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LoginBlock.WBP_AGS_LoginBlock_C"),
            ("entry_widget_class", "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow.WBP_AGS_PlayerRow_C"),
        ):
            with self.subTest(class_path_key=class_path_key):
                node = {
                    "type": "ListView" if class_path_key == "entry_widget_class" else "AGSLoginBlock",
                    "name": "GeneratedWidget",
                    class_path_key: class_path,
                }
                if class_path_key == "entry_widget_class":
                    node["horizontal_entry_spacing"] = 4
                    node["vertical_entry_spacing"] = 4
                with self.assertRaises(ValidationError) as raised:
                    load_spec_from_dict(
                        {
                            "asset_path": "/Game/AGS/UI/Generated/WBP_BadPluginReference",
                            "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                            "root": node,
                        }
                    )

                self.assertEqual(raised.exception.code, "schema_error")

    def test_generated_ags_specs_reject_bare_native_controls(self):
        for widget_type in ("Button", "EditableTextBox"):
            with self.subTest(widget_type=widget_type):
                with self.assertRaises(ValidationError) as raised:
                    load_spec_from_dict(
                        {
                            "asset_path": "/Game/AGS/UI/Generated/WBP_BareNativeControl",
                            "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                            "root": {"type": widget_type, "name": "NativeControl"},
                        }
                    )

                self.assertEqual(raised.exception.code, "schema_error")

    def test_generated_ags_specs_reject_featureblock_and_list_alias_auto_resolution(self):
        for alias in ("AGSFriendRow", "AGSLeaderboardRow"):
            with self.subTest(alias=alias):
                with self.assertRaises(ValidationError) as raised:
                    load_spec_from_dict(
                        {
                            "asset_path": "/Game/AGS/UI/Generated/WBP_BadAlias",
                            "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                            "root": {"type": alias, "name": "AliasWidget"},
                        }
                    )

                self.assertEqual(raised.exception.code, "schema_error")

    def test_generated_ags_specs_allow_core_plugin_class_paths(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_CoreReference",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "style": {"background_color": [0.0, 0.0, 0.0, 0.1], "corner_radius": 8, "border_color": [0.84, 0.87, 0.92, 1.0], "border_width": 1},
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "AGSBaseButton",
                                    "name": "SubmitButton",
                                    "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
                                    "is_variable": True,
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            }
        )

        self.assertEqual(spec.variable_widget_names(), ["SubmitButton"])

    def test_generated_asset_path_allows_subfolders_after_generated(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardPanel",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "style": {"background_color": [0.0, 0.0, 0.0, 0.1], "corner_radius": 8, "border_color": [0.84, 0.87, 0.92, 1.0], "border_width": 1},
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                        }
                    ],
                },
            }
        )

        self.assertEqual(spec.asset_path, "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardPanel")

    def test_generated_collection_entry_allows_compact_row_layout(self):
        spec = load_spec_from_dict(
            {
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
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "HorizontalBox",
                                    "name": "RowContent",
                                    "slot": {"h_align": "fill", "v_align": "center"},
                                    "children": [
                                        {"type": "TextBlock", "name": "Tb_Rank", "is_variable": True},
                                        {"type": "TextBlock", "name": "Tb_PlayerName", "is_variable": True},
                                        {"type": "TextBlock", "name": "Tb_Score", "is_variable": True},
                                    ],
                                }
                            ],
                        }
                    ],
                },
            }
        )

        self.assertEqual(
            spec.variable_widget_names(),
            ["Tb_Rank", "Tb_PlayerName", "Tb_Score"],
        )

    def test_bundled_recipes_can_opt_out_of_generated_ags_policy(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/Game/AGS/UI/Generated/WBP_LoginRecipe",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "Border",
                    "name": "PanelBackground",
                    "style": {"background_color": [0.0, 0.0, 0.0, 0.1], "corner_radius": 8, "border_color": [0.84, 0.87, 0.92, 1.0], "border_width": 1},
                    "children": [
                        {
                            "type": "Overlay",
                            "name": "ContentContainer",
                            "padding": [20, 20, 20, 20],
                            "slot": {"h_align": "fill", "v_align": "fill"},
                            "children": [
                                {
                                    "type": "AGSLoginBlock",
                                    "name": "LoginBlock",
                                    "class_path": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LoginBlock.WBP_AGS_LoginBlock_C",
                                    "is_variable": True,
                                    "slot": {"h_align": "fill", "v_align": "fill"},
                                }
                            ],
                        }
                    ],
                },
            },
            enforce_generated_ags_policy=False,
        )

        self.assertEqual(spec.variable_widget_names(), ["LoginBlock"])

    def test_generated_ags_rejects_bare_editable_text_even_with_incomplete_style(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_IncompleteInput",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {
                        "type": "EditableTextBox",
                        "name": "ValueInput",
                        "style": {
                            "color": [0.0, 0.0, 0.0, 1.0],
                            "hint_color": [0.45, 0.49, 0.56, 1.0],
                        },
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_generated_ags_accepts_core_text_input_alias(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CompleteInput",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "AGSTextInput",
                    "name": "ValueInput",
                    "padding": [8, 8, 8, 8],
                },
            }
        )

        self.assertEqual(spec.root.padding, (8.0, 8.0, 8.0, 8.0))
        self.assertEqual(
            spec.root.class_path,
            "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput.WBP_AGS_TextInput_C",
        )

    def test_generated_ags_rejects_stale_dark_theme_literals(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_DarkLiteral",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {
                        "type": "Border",
                        "name": "PanelBackground",
                        "style": {
                            "background_color": [0.08, 0.08, 0.1, 1.0],
                            "corner_radius": 8,
                            "border_color": [0.84, 0.87, 0.92, 1.0],
                            "border_width": 1,
                        },
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_generated_ags_rejects_non_token_control_style(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_OffTokenButton",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {
                        "type": "Button",
                        "name": "SubmitButton",
                        "padding": [8, 8, 8, 8],
                        "style": {
                            "color": [0.2, 0.2, 0.2, 1.0],
                            "hover_color": [0.031, 0.341, 0.86, 1.0],
                            "pressed_color": [0.022, 0.251, 0.66, 1.0],
                            "corner_radius": 6,
                            "border_color": [0.043, 0.424, 1.0, 1.0],
                            "border_width": 1,
                        },
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_collection_entry_spacing_is_collection_only(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_BadSpacing",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "root": {
                        "type": "Border",
                        "name": "Panel",
                        "horizontal_entry_spacing": 4,
                    },
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_rejects_invalid_names(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/ByteWars/UI/Generated/WBP_Bad",
                    "parent_class": "/Script/AccelByteWars.BadWidget",
                    "root": {"type": "CanvasPanel", "name": "Bad Name"},
                }
            )

        self.assertEqual(raised.exception.code, "schema_error")

    def test_accepts_common_ui_parent_class(self):
        # Mode B — Common UI: generated blueprints use AGSCommonActivatableBase as parent
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoginActivatable",
                "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
                "ui_mode": "common_ui",
                "root": {"type": "Overlay", "name": "RootOverlay"},
            }
        )

        self.assertEqual(
            spec.parent_class,
            "/Script/AccelByteUITools.AGSCommonActivatableBase",
        )

    def test_accepts_vanilla_umg_user_widget_parent_class(self):
        # Mode C — Follow Project: fallback when the project has no custom C++ base class
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_ProjectPanel",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {"type": "CanvasPanel", "name": "RootCanvas"},
            }
        )

        self.assertEqual(spec.parent_class, "/Script/UMG.UserWidget")

    def test_ags_alias_types_auto_resolve_class_path(self):
        for alias, expected_path in [
            ("AGSErrorState",       "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState.WBP_AGS_ErrorState_C"),
            ("AGSEmptyState",       "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState.WBP_AGS_EmptyState_C"),
            ("AGSLoadingIndicator", "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator.WBP_AGS_LoadingIndicator_C"),
            ("AGSStatusMessage",    "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C"),
            ("AGSLeaderboardRow",   "/AccelByteUITools/AGSUI/Lists/WBP_AGS_LeaderboardRow.WBP_AGS_LeaderboardRow_C"),
            ("AGSFriendRow",        "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_FriendRow.WBP_AGS_FriendRow_C"),
        ]:
            with self.subTest(alias=alias):
                spec = load_spec_from_dict(
                    {
                        "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_AliasTest",
                        "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                        "root": {
                            "type": "CanvasPanel",
                            "name": "RootCanvas",
                            "children": [{"type": alias, "name": "AliasWidget", "is_variable": True}],
                        },
                    }
                )
                alias_node = next(n for n in spec.root.walk() if n.type == alias)
                self.assertEqual(alias_node.class_path, expected_path)

    def test_ags_alias_without_explicit_class_path_passes_validation(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorStateTest",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "CanvasPanel",
                    "name": "RootCanvas",
                    "children": [{"type": "AGSErrorState", "name": "ErrorWidget", "is_variable": True}],
                },
            }
        )
        self.assertEqual(spec.widget_count(), 2)

    def test_explicit_class_path_takes_priority_over_alias(self):
        custom_path = "/Game/MyProject/WBP_CustomError.WBP_CustomError_C"
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CustomTest",
                "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                "root": {
                    "type": "CanvasPanel",
                    "name": "RootCanvas",
                    "children": [
                        {
                            "type": "AGSErrorState",
                            "name": "ErrorWidget",
                            "is_variable": True,
                            "class_path": custom_path,
                        }
                    ],
                },
            }
        )
        alias_node = next(n for n in spec.root.walk() if n.type == "AGSErrorState")
        self.assertEqual(alias_node.class_path, custom_path)


    def test_rejects_duplicate_widget_names_among_variables(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/ByteWars/UI/Generated/WBP_DupVars",
                    "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
                    "root": {
                        "type": "VerticalBox",
                        "name": "RootBox",
                        "children": [
                            {"type": "TextBlock", "name": "Lbl_Title", "is_variable": True},
                            {"type": "TextBlock", "name": "Lbl_Title", "is_variable": True},
                        ],
                    },
                }
            )

        self.assertEqual(raised.exception.code, "duplicate_widget_name")

    def test_rejects_duplicate_widget_names_mixed_variable_flags(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/ByteWars/UI/Generated/WBP_DupMixed",
                    "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
                    "root": {
                        "type": "VerticalBox",
                        "name": "RootBox",
                        "children": [
                            {"type": "Image", "name": "Img_Icon", "is_variable": True},
                            {"type": "Image", "name": "Img_Icon"},
                        ],
                    },
                }
            )

        self.assertEqual(raised.exception.code, "duplicate_widget_name")

    def test_rejects_duplicate_widget_name_between_root_and_child(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/ByteWars/UI/Generated/WBP_DupRoot",
                    "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
                    "root": {
                        "type": "CanvasPanel",
                        "name": "Container",
                        "children": [
                            {"type": "TextBlock", "name": "Container"},
                        ],
                    },
                }
            )

        self.assertEqual(raised.exception.code, "duplicate_widget_name")

    def test_accepts_unique_widget_names_across_tree(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_UniqueNames",
                "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
                "root": {
                    "type": "VerticalBox",
                    "name": "RootBox",
                    "children": [
                        {"type": "TextBlock", "name": "Lbl_Title", "is_variable": True},
                        {"type": "TextBlock", "name": "Lbl_Subtitle", "is_variable": True},
                        {"type": "Image", "name": "Img_Avatar"},
                    ],
                },
            }
        )

        self.assertEqual(spec.widget_count(), 4)
        self.assertEqual(spec.variable_widget_names(), ["Lbl_Title", "Lbl_Subtitle"])

    def test_generated_ags_state_switcher_accepts_canonical_state_types(self):
        spec = load_spec_from_dict(self._valid_generated_ags_stateful_panel())

        self.assertEqual(
            spec.variable_widget_names(),
            ["StateSwitcher", "IdlePanel", "LoadingPanel", "SuccessPanel", "EmptyPanel", "ErrorPanel"],
        )
        bindings = {binding.widget_name: binding for binding in spec.bindings()}
        self.assertEqual(bindings["StateSwitcher"].cpp_type, "UWidgetSwitcher")
        self.assertEqual(bindings["IdlePanel"].cpp_type, "UAGSStatusMessageBase")
        self.assertEqual(bindings["LoadingPanel"].cpp_type, "UAGSLoadingIndicatorBase")
        self.assertEqual(bindings["EmptyPanel"].cpp_type, "UAGSEmptyStateBase")
        self.assertEqual(bindings["ErrorPanel"].cpp_type, "UAGSErrorStateBase")
        for binding in bindings.values():
            self.assertIn("BindWidget", binding.bind_meta)
            self.assertNotIn("BindWidgetOptional", binding.bind_meta)
            self.assertNotEqual(binding.cpp_type, "UAGSStateWidgetBase")

    def test_generated_ags_panel_background_fallback_canonicalizes(self):
        data = self._valid_generated_ags_stateful_panel()
        data["asset_path"] = "/Game/AGS/UI/Generated/WBP_AGS_Store"
        data["root"]["style"] = {"background_color": [0.0, 0.0, 0.0, 0.1], "corner_radius": 8}

        normalized = normalize_theme(data)
        canonical = canonicalize_spec(normalized)

        self.assertEqual(canonical["root"]["style"]["background_color"], [0.0, 0.0, 0.0, 0.1])
        self.assertEqual(canonical["root"]["style"]["border_color"], [0.84, 0.87, 0.92, 1.0])
        self.assertEqual(canonical["root"]["style"]["border_width"], 1)

    def test_generated_panel_rejects_renamed_panel_background(self):
        data = self._valid_generated_ags_stateful_panel()
        data["root"]["name"] = "WidgetBackground"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)

        self.assertEqual(raised.exception.code, "invalid_root_structure")
        self.assertIn("PanelBackground", raised.exception.message)

    def test_generated_panel_rejects_renamed_content_container(self):
        data = self._valid_generated_ags_stateful_panel()
        data["root"]["children"][0]["name"] = "WidgetContainer"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)

        self.assertEqual(raised.exception.code, "invalid_root_structure")
        self.assertIn("ContentContainer", raised.exception.message)

    def test_generated_collection_entry_does_not_require_panel_root_contract(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardEntry",
                "parent_class": "/Script/UMG.UserWidget",
                "root": {
                    "type": "Border",
                    "name": "EntryBackground",
                    "children": [
                        {"type": "TextBlock", "name": "PlayerNameText", "is_variable": True}
                    ],
                },
            }
        )

        self.assertEqual(spec.root.name, "EntryBackground")

    def test_generated_ags_state_switcher_validates_project_script_parent(self):
        data = self._valid_generated_ags_stateful_panel()
        data["parent_class"] = "/Script/AccelByteWars.LoginPanelWidget"
        data["root"]["children"][0]["children"][0]["children"][3]["type"] = "AGSStatusMessage"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)

        self.assertEqual(raised.exception.code, "schema_error")
        self.assertIn("Empty state", raised.exception.message)

    def test_generated_ags_state_switcher_rejects_wrong_empty_state_type(self):
        data = self._valid_generated_ags_stateful_panel()
        data["root"]["children"][0]["children"][0]["children"][3]["type"] = "AGSStatusMessage"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)

        self.assertEqual(raised.exception.code, "schema_error")
        self.assertIn("Empty state", raised.exception.message)

    def test_generated_ags_state_switcher_allows_project_class_path_for_state_panels(self):
        data = self._valid_generated_ags_stateful_panel()
        data["root"]["children"][0]["children"][0]["children"][3]["class_path"] = (
            "/Game/ByteWars/UI/W_EmptyState.W_EmptyState_C"
        )

        spec = load_spec_from_dict(data)
        self.assertIsNotNone(spec)

    def test_generated_ags_state_switcher_rejects_invalid_state_order(self):
        data = self._valid_generated_ags_stateful_panel()
        children = data["root"]["children"][0]["children"][0]["children"]
        children[1], children[2] = children[2], children[1]

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)

        self.assertEqual(raised.exception.code, "schema_error")
        self.assertIn("required Loading position", raised.exception.message)

    def test_generated_ags_state_switcher_rejects_renamed_state_like_switcher(self):
        data = self._valid_generated_ags_stateful_panel()
        data["root"]["children"][0]["children"][0]["name"] = "StatusSwitcher"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)

        self.assertEqual(raised.exception.code, "schema_error")
        self.assertIn("must be named StateSwitcher", raised.exception.message)

    def test_generated_ags_allows_feature_specific_non_state_switcher(self):
        data = self._valid_generated_ags_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [
            {
                "type": "WidgetSwitcher",
                "name": "TabContentSwitcher",
                "is_variable": True,
                "slot": {"h_align": "fill", "v_align": "fill"},
                "children": [
                    {"type": "VerticalBox", "name": "OverviewPanel"},
                    {"type": "VerticalBox", "name": "DetailsPanel"},
                ],
            }
        ]

        spec = load_spec_from_dict(data)

        self.assertIn("TabContentSwitcher", spec.variable_widget_names())


    # ------------------------------------------------------------------ #
    #  Common UI mode tests                                               #
    # ------------------------------------------------------------------ #

    def _valid_common_ui_stateful_panel(self):
        data = self._valid_generated_ags_stateful_panel()
        data["parent_class"] = "/Script/AccelByteUITools.AGSCommonActivatableBase"
        data["ui_mode"] = "common_ui"
        return data

    # --- pass cases ---

    def test_common_ui_mode_loads_valid_panel(self):
        spec = load_spec_from_dict(self._valid_common_ui_stateful_panel())
        self.assertEqual(spec.ui_mode, "common_ui")
        self.assertEqual(spec.parent_class, "/Script/AccelByteUITools.AGSCommonActivatableBase")

    def test_common_ui_mode_ags_button_resolves_to_common_ui_path(self):
        data = self._valid_common_ui_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "AGSButton", "name": "SubmitButton", "is_variable": True}]
        spec = load_spec_from_dict(data)
        btn = next(n for n in spec.root.walk() if n.name == "SubmitButton")
        self.assertEqual(btn.class_path, "/AccelByteUITools/AGSUI/Core/WBP_AGS_CommonButton.WBP_AGS_CommonButton_C")

    def test_common_ui_mode_text_block_resolves_to_common_text_path(self):
        data = self._valid_common_ui_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "TextBlock", "name": "TitleText", "is_variable": True}]
        spec = load_spec_from_dict(data)
        txt = next(n for n in spec.root.walk() if n.name == "TitleText")
        self.assertEqual(txt.class_path, "/Script/CommonUI.CommonTextBlock")

    def test_common_ui_mode_button_binding_uses_ags_common_button_type(self):
        data = self._valid_common_ui_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "AGSButton", "name": "SubmitButton", "is_variable": True}]
        spec = load_spec_from_dict(data)
        binding = next(b for b in spec.bindings() if b.widget_name == "SubmitButton")
        self.assertEqual(binding.cpp_type, "UAGSCommonButtonBase")
        self.assertIn("AGSCommonWidgetBase.h", binding.include)

    def test_project_mapped_state_uses_actual_project_binding_contract(self):
        data = self._valid_generated_ags_stateful_panel()
        state_switcher = data["root"]["children"][0]["children"][0]
        idle_panel = state_switcher["children"][0]
        idle_panel["class_path"] = "/Game/UI/Core/WBP_ProjectStatusPanel.WBP_ProjectStatusPanel_C"
        spec = load_spec_from_dict(
            data,
            project_class_mapping={
                "/Game/UI/Core/WBP_ProjectStatusPanel.WBP_ProjectStatusPanel_C": "UAGSPanelBase"
            },
        )

        binding = next(b for b in spec.bindings() if b.widget_name == "IdlePanel")

        self.assertEqual(binding.cpp_type, "UAGSPanelBase")
        self.assertEqual(binding.include, '"AGSUI/AGSWidgetBase.h"')
        self.assertEqual(binding.expected_unreal_class, "/Script/AccelByteUITools.AGSPanelBase")
        self.assertEqual(binding.resolution_source, "style_context")

    def test_ags_fallback_idle_panel_uses_status_message_binding_contract(self):
        spec = load_spec_from_dict(self._valid_generated_ags_stateful_panel())

        binding = next(b for b in spec.bindings() if b.widget_name == "IdlePanel")

        self.assertEqual(binding.cpp_type, "UAGSStatusMessageBase")
        self.assertEqual(binding.include, '"AGSUI/AGSWidgetBase.h"')
        self.assertEqual(binding.expected_unreal_class, "/Script/AccelByteUITools.AGSStatusMessageBase")
        self.assertEqual(binding.resolution_source, "static_contract")

    def test_project_mapped_exact_state_class_keeps_role_specific_binding_contract(self):
        data = self._valid_generated_ags_stateful_panel()
        state_switcher = data["root"]["children"][0]["children"][0]
        idle_panel = state_switcher["children"][0]
        idle_panel["class_path"] = "/Game/AGS/UI/Components/WBP_AGS_ProjectStatusPanel.WBP_AGS_ProjectStatusPanel_C"
        spec = load_spec_from_dict(
            data,
            project_class_mapping={
                "/Game/AGS/UI/Components/WBP_AGS_ProjectStatusPanel.WBP_AGS_ProjectStatusPanel_C": "UAGSStatusMessageBase"
            },
        )

        binding = next(b for b in spec.bindings() if b.widget_name == "IdlePanel")

        self.assertEqual(binding.cpp_type, "UAGSStatusMessageBase")
        self.assertEqual(binding.include, '"AGSUI/AGSWidgetBase.h"')
        self.assertEqual(binding.expected_unreal_class, "/Script/AccelByteUITools.AGSStatusMessageBase")
        self.assertEqual(binding.resolution_source, "static_contract_via_project_mapping")

    def test_core_role_allows_user_widget_state_without_overriding_binding_type(self):
        data = self._valid_generated_ags_stateful_panel()
        state_switcher = data["root"]["children"][0]["children"][0]
        idle_panel = state_switcher["children"][0]
        idle_panel["type"] = "UserWidget"
        idle_panel["core_role"] = "state_idle"
        idle_panel["class_path"] = "/Game/UI/Core/WBP_ProjectStatusPanel.WBP_ProjectStatusPanel_C"
        spec = load_spec_from_dict(
            data,
            project_class_mapping={
                "/Game/UI/Core/WBP_ProjectStatusPanel.WBP_ProjectStatusPanel_C": "UAGSPanelBase"
            },
        )

        binding = next(b for b in spec.bindings() if b.widget_name == "IdlePanel")

        self.assertEqual(binding.spec_type, "UserWidget")
        self.assertEqual(binding.cpp_type, "UAGSPanelBase")
        self.assertEqual(binding.expected_unreal_class, "/Script/AccelByteUITools.AGSPanelBase")
        self.assertEqual(binding.resolution_source, "style_context")

    def test_core_role_without_class_path_does_not_override_user_widget_binding_type(self):
        data = self._valid_generated_ags_stateful_panel()
        state_switcher = data["root"]["children"][0]["children"][0]
        idle_panel = state_switcher["children"][0]
        idle_panel["type"] = "UserWidget"
        idle_panel["core_role"] = "state_idle"
        spec = load_spec_from_dict(data)

        binding = next(b for b in spec.bindings() if b.widget_name == "IdlePanel")

        self.assertEqual(binding.spec_type, "UserWidget")
        self.assertEqual(binding.cpp_type, "UUserWidget")
        self.assertEqual(binding.expected_unreal_class, "/Script/UMG.UserWidget")
        self.assertEqual(binding.resolution_source, "static_contract")

    def test_project_class_path_overrides_ags_button_alias_binding_contract(self):
        data = self._valid_generated_ags_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [
            {
                "type": "AGSBaseButton",
                "name": "Btn_Back",
                "is_variable": True,
                "class_path": "/Game/UI/Common/W_MenuButton.W_MenuButton_C",
            }
        ]
        spec = load_spec_from_dict(
            data,
            project_class_mapping={
                "/Game/UI/Common/W_MenuButton.W_MenuButton_C": "UAccelByteWarsButtonBase"
            },
        )

        binding = next(b for b in spec.bindings() if b.widget_name == "Btn_Back")

        self.assertEqual(binding.cpp_type, "UAccelByteWarsButtonBase")
        self.assertNotEqual(binding.cpp_type, "UAGSButtonBase")
        self.assertEqual(binding.resolution_source, "style_context")

    def test_style_mode_is_validated_and_preserved_when_explicit(self):
        data = self._valid_generated_ags_stateful_panel()
        data["style_mode"] = "agsui"

        spec = load_spec_from_dict(data)

        self.assertEqual(spec.style_mode, "agsui")
        self.assertEqual(spec.to_dict()["style_mode"], "agsui")

    def test_invalid_style_mode_is_rejected(self):
        data = self._valid_generated_ags_stateful_panel()
        data["style_mode"] = "follow_project"

        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)

        self.assertEqual(raised.exception.code, "invalid_style_mode")

    def test_common_ui_mode_text_binding_uses_common_text_block_type(self):
        data = self._valid_common_ui_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "TextBlock", "name": "TitleText", "is_variable": True}]
        spec = load_spec_from_dict(data)
        binding = next(b for b in spec.bindings() if b.widget_name == "TitleText")
        self.assertEqual(binding.cpp_type, "UCommonTextBlock")
        self.assertEqual(binding.include, '"CommonTextBlock.h"')

    def test_common_ui_non_button_aliases_resolve_to_same_paths_as_umg(self):
        for alias, expected_path in [
            ("AGSLoadingIndicator", "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator.WBP_AGS_LoadingIndicator_C"),
            ("AGSEmptyState",       "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState.WBP_AGS_EmptyState_C"),
            ("AGSErrorState",       "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState.WBP_AGS_ErrorState_C"),
            ("AGSTextInput",        "/AccelByteUITools/AGSUI/Core/WBP_AGS_TextInput.WBP_AGS_TextInput_C"),
        ]:
            with self.subTest(alias=alias):
                spec = load_spec_from_dict(
                    {
                        "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CUIAliasTest",
                        "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
                        "ui_mode": "common_ui",
                        "root": {
                            "type": "CanvasPanel",
                            "name": "RootCanvas",
                            "children": [{"type": alias, "name": "AliasWidget"}],
                        },
                    }
                )
                node = next(n for n in spec.root.walk() if n.type == alias)
                self.assertEqual(node.class_path, expected_path)

    def test_common_ui_all_three_parent_classes_accepted(self):
        for parent in [
            "/Script/AccelByteUITools.AGSCommonActivatableBase",
            "/Script/CommonUI.CommonActivatableWidget",
            "/Script/CommonUI.CommonUserWidget",
        ]:
            with self.subTest(parent=parent):
                spec = load_spec_from_dict(
                    {
                        "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_CUIParentTest",
                        "parent_class": parent,
                        "ui_mode": "common_ui",
                        "root": {"type": "CanvasPanel", "name": "RootCanvas"},
                    }
                )
                self.assertEqual(spec.ui_mode, "common_ui")

    # --- fail cases: mode/parent_class mismatch ---

    def test_common_ui_mode_rejects_umg_parent_class(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_CUIPanel",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "ui_mode": "common_ui",
                    "root": {"type": "Border", "name": "PanelBackground"},
                }
            )
        self.assertEqual(raised.exception.code, "schema_error")
        self.assertIn("common_ui", raised.exception.message)

    def test_umg_mode_rejects_common_ui_parent_class(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_CUIPanel",
                    "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
                    "root": {"type": "Border", "name": "PanelBackground"},
                }
            )
        self.assertEqual(raised.exception.code, "schema_error")
        self.assertIn("ui_mode", raised.exception.message)

    def test_rejects_invalid_ui_mode_value(self):
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(
                {
                    "asset_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_Bad",
                    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
                    "ui_mode": "opengl",
                    "root": {"type": "CanvasPanel", "name": "RootCanvas"},
                }
            )
        self.assertEqual(raised.exception.code, "schema_error")

    # --- fail cases: structural rules still enforced for Common UI ---

    def test_common_ui_rejects_non_border_root(self):
        data = self._valid_common_ui_stateful_panel()
        data["root"]["type"] = "Overlay"
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)
        self.assertEqual(raised.exception.code, "invalid_root_structure")

    def test_common_ui_rejects_bare_button_native_type(self):
        data = self._valid_common_ui_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "Button", "name": "SubmitButton"}]
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)
        self.assertEqual(raised.exception.code, "schema_error")

    def test_common_ui_rejects_wrong_state_switcher_order(self):
        data = self._valid_common_ui_stateful_panel()
        children = data["root"]["children"][0]["children"][0]["children"]
        children[1], children[2] = children[2], children[1]
        with self.assertRaises(ValidationError) as raised:
            load_spec_from_dict(data)
        self.assertEqual(raised.exception.code, "schema_error")

    # --- regression: UMG mode still works ---

    def test_umg_mode_ags_button_resolves_to_umg_path(self):
        data = self._valid_generated_ags_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "AGSButton", "name": "SubmitButton", "is_variable": True}]
        spec = load_spec_from_dict(data)
        btn = next(n for n in spec.root.walk() if n.name == "SubmitButton")
        self.assertEqual(btn.class_path, "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C")

    def test_umg_mode_text_block_has_no_class_path(self):
        data = self._valid_generated_ags_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "TextBlock", "name": "TitleText"}]
        spec = load_spec_from_dict(data)
        txt = next(n for n in spec.root.walk() if n.name == "TitleText")
        self.assertIsNone(txt.class_path)

    def test_umg_mode_button_binding_uses_ags_button_base_type(self):
        data = self._valid_generated_ags_stateful_panel()
        success = data["root"]["children"][0]["children"][0]["children"][2]
        success["children"] = [{"type": "AGSButton", "name": "SubmitButton", "is_variable": True}]
        spec = load_spec_from_dict(data)
        binding = next(b for b in spec.bindings() if b.widget_name == "SubmitButton")
        self.assertEqual(binding.cpp_type, "UAGSButtonBase")


if __name__ == "__main__":
    unittest.main()
