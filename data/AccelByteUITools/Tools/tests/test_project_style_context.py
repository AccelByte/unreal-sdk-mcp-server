import json
import tempfile
import unittest
from pathlib import Path

try:
    from Plugins.AccelByteUITools.Tools.project_style_context import (
        approval_status,
        approve_style_context,
        discover_project_style,
        load_generated_components_registry,
        register_generated_widget,
        validate_spec_against_style_context,
        write_style_context,
    )
except ModuleNotFoundError:
    from data.AccelByteUITools.Tools.project_style_context import (
        approval_status,
        approve_style_context,
        discover_project_style,
        load_generated_components_registry,
        register_generated_widget,
        validate_spec_against_style_context,
        write_style_context,
    )


class ProjectStyleContextTests(unittest.TestCase):
    def _write_project(self, root: Path, plugins: list[str]) -> Path:
        project = root / "SampleProject.uproject"
        project.write_text(
            json.dumps({"Plugins": [{"Name": plugin, "Enabled": True} for plugin in plugins]}),
            encoding="utf-8",
        )
        return project

    def test_discovers_common_ui_project_roles_without_project_specific_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["CommonUI"])
            source = root / "Source" / "Game" / "UI"
            source.mkdir(parents=True)
            (source / "MenuButton.h").write_text(
                "class GAME_API UMenuButton : public UCommonButtonBase {};",
                encoding="utf-8",
            )
            styles = root / "Content" / "UI" / "Styles"
            styles.mkdir(parents=True)
            (styles / "PrimaryButtonStyle.uasset").write_text("", encoding="utf-8")
            (styles / "BodyTextStyle.uasset").write_text("", encoding="utf-8")

            context = discover_project_style(project)

        self.assertEqual(context["ui_backend"], "common_ui")
        self.assertIn("CommonUI", context["enabled_ui_modules"])
        self.assertIn("common_button", context["source_classes"])
        self.assertIn("primary_button", context["semantic_roles"]["styles"])
        self.assertIn("body_text", context["semantic_roles"]["styles"])
        self.assertTrue(context["enforced_roles"]["primary_button"]["project_candidates"])
        self.assertTrue(context["enforced_roles"]["body_text"]["project_candidates"])

    def test_discovers_project_common_activatable_parent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["CommonUI"])
            source = root / "Source" / "Game" / "UI"
            source.mkdir(parents=True)
            (source / "AccelByteWarsActivatableWidget.h").write_text(
                "class GAME_API UAccelByteWarsActivatableWidget : public UCommonActivatableWidget {};",
                encoding="utf-8",
            )

            context = discover_project_style(project)

        self.assertIn("common_activatable", context["source_classes"])
        self.assertEqual(context["source_classes"]["common_activatable"][0]["name"], "UAccelByteWarsActivatableWidget")

    def test_discovers_generated_subclass_of_project_common_activatable_parent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["CommonUI"])
            source = root / "Source" / "Game" / "AGS" / "UI" / "Generated" / "Leaderboard"
            source.mkdir(parents=True)
            (source / "AccelByteWarsActivatableWidget.h").write_text(
                "class GAME_API UAccelByteWarsActivatableWidget : public UCommonActivatableWidget {};",
                encoding="utf-8",
            )
            (source / "LeaderboardWidget.h").write_text(
                "class GAME_API ULeaderboardWidget : public UAccelByteWarsActivatableWidget {};",
                encoding="utf-8",
            )

            context = discover_project_style(project)

        common_names = {entry["name"] for entry in context["source_classes"]["common_activatable"]}
        self.assertIn("UAccelByteWarsActivatableWidget", common_names)
        self.assertIn("ULeaderboardWidget", common_names)
        self.assertIn("/Script/Game.LeaderboardWidget", context["allowed_class_references"])

    def test_discovers_transitive_list_entry_compatible_class(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            source = root / "Source" / "Game" / "AGS" / "UI" / "Generated" / "Leaderboard"
            source.mkdir(parents=True)
            (source / "AccelByteWarsWidgetEntry.h").write_text(
                "class GAME_API UAccelByteWarsWidgetEntry : public UUserWidget, public IUserObjectListEntry {};",
                encoding="utf-8",
            )
            (source / "LeaderboardEntryWidget.h").write_text(
                "class GAME_API ULeaderboardEntryWidget : public UAccelByteWarsWidgetEntry {};",
                encoding="utf-8",
            )

            context = discover_project_style(project)

        entry_names = {entry["name"] for entry in context["source_classes"]["list_entry_compatible"]}
        self.assertIn("UAccelByteWarsWidgetEntry", entry_names)
        self.assertIn("ULeaderboardEntryWidget", entry_names)
        self.assertIn("/Script/Game.LeaderboardEntryWidget", context["allowed_class_references"])

    def test_common_ui_generated_spec_uses_project_parent_when_unambiguous(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {
                "common_activatable": [
                    {
                        "name": "UAccelByteWarsActivatableWidget",
                        "module": "AccelByteWars",
                        "source": "Source/AccelByteWars/UI/AccelByteWarsActivatableWidget.h",
                    }
                ]
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Leaderboard",
            "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
            "ui_mode": "common_ui",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])
        self.assertEqual(spec["parent_class"], "/Script/AccelByteWars.AccelByteWarsActivatableWidget")

    def test_common_ui_generated_spec_rejects_fallback_parent_when_project_parent_is_ambiguous(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {
                "common_activatable": [
                    {"name": "UMenuActivatableWidget", "module": "Game", "source": "Source/Game/UI/MenuActivatableWidget.h"},
                    {"name": "UPopupActivatableWidget", "module": "Game", "source": "Source/Game/UI/PopupActivatableWidget.h"},
                ]
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Leaderboard",
            "parent_class": "/Script/AccelByteUITools.AGSCommonActivatableBase",
            "ui_mode": "common_ui",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "project_parent_class_required" for error in errors))

    def test_discovers_umg_only_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            content = root / "Content" / "UI"
            content.mkdir(parents=True)
            (content / "WBP_ListRow.uasset").write_text("", encoding="utf-8")

            context = discover_project_style(project)

        self.assertEqual(context["ui_backend"], "umg")
        self.assertIn("list_row", context["semantic_roles"]["widgets"])

    def test_discovery_separates_project_and_fallback_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["CommonUI"])
            project_styles = root / "Content" / "UI" / "Styles"
            project_styles.mkdir(parents=True)
            (project_styles / "PrimaryButtonStyle.uasset").write_text("", encoding="utf-8")
            (project_styles / "TitleTextStyle.uasset").write_text("", encoding="utf-8")
            plugin_core = root / "Plugins" / "AccelByteUITools" / "Content" / "AGSUI" / "Core"
            plugin_core.mkdir(parents=True)
            (plugin_core / "WBP_AGS_BaseButton.uasset").write_text("", encoding="utf-8")

            context = discover_project_style(project)

        primary = context["enforced_roles"]["primary_button"]
        self.assertTrue(any(item["asset_path"].startswith("/Game/") for item in primary["project_candidates"]))
        self.assertTrue(any(item["asset_path"].startswith("/AccelByteUITools/") for item in primary["fallback_candidates"]))
        self.assertFalse(any(item["asset_path"].startswith("/AccelByteUITools/") for item in primary["project_candidates"]))

    def test_discovery_ignores_non_ui_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            for rel_path in (
                "Content/Audio/MainMenuButtonClick.uasset",
                "Content/Blueprints/GameModes/BP_MainMenuGameMode.uasset",
                "Content/Materials/M_ButtonGlow.uasset",
                "Content/Input/IA_MenuConfirm.uasset",
            ):
                path = root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            ui = root / "Content" / "UI"
            ui.mkdir(parents=True)
            (ui / "WBP_PrimaryButton.uasset").write_text("", encoding="utf-8")

            context = discover_project_style(project)

        candidates = context["candidate_widget_assets"]
        self.assertEqual([item["name"] for item in candidates], ["WBP_PrimaryButton"])

    def test_approval_tracks_source_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            context = discover_project_style(project)
            write_style_context(context, project)

            self.assertFalse(approval_status(context, project)["approved"])
            approve_style_context(context, project)
            self.assertTrue(approval_status(context, project)["approved"])

            changed = {**context, "source_fingerprint": "changed"}
            self.assertFalse(approval_status(changed, project)["approved"])

    def test_validation_rejects_raw_control_when_project_style_exists(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": ["/Game/UI/WBP_PrimaryButton.WBP_PrimaryButton_C"],
            "allowed_style_references": ["/Game/UI/Styles/PrimaryButtonStyle.PrimaryButtonStyle_C"],
            "discouraged_raw_widget_types": ["Button", "TextBlock"],
            "enforced_roles": {
                "primary_button": {
                    "project_candidates": [{"class_path": "/Game/UI/Styles/PrimaryButtonStyle.PrimaryButtonStyle_C"}],
                    "fallback_candidates": [],
                }
            },
        }
        spec = {
            "asset_path": "/Game/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "Button", "name": "RawButton"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors[0]["code"], "discouraged_raw_widget")

    def test_validation_rejects_ags_button_when_project_button_exists(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": ["/Game/UI/WBP_PrimaryButton.WBP_PrimaryButton_C"],
            "allowed_style_references": ["/Game/UI/Styles/PrimaryButtonStyle.PrimaryButtonStyle_C"],
            "discouraged_raw_widget_types": ["Button", "TextBlock"],
            "enforced_roles": {
                "primary_button": {
                    "project_candidates": [{"class_path": "/Game/UI/WBP_PrimaryButton.WBP_PrimaryButton_C"}],
                    "fallback_candidates": [{"class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C"}],
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "AGSButton",
                "name": "SubmitButton",
                "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "project_button_required" for error in errors))

    def test_validation_rejects_native_button_without_project_style(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": [],
            "allowed_style_references": ["/Game/UI/Styles/PrimaryButtonStyle.PrimaryButtonStyle_C"],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "primary_button": {
                    "project_candidates": [{"class_path": "/Game/UI/Styles/PrimaryButtonStyle.PrimaryButtonStyle_C", "kind": "style"}],
                    "fallback_candidates": [],
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "Button", "name": "SubmitButton"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "missing_project_button_style" for error in errors))

    def test_validation_rejects_text_without_project_text_style(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": [],
            "allowed_style_references": ["/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C"],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "body_text": {
                    "project_candidates": [{"class_path": "/Game/UI/Styles/BodyTextStyle.BodyTextStyle_C"}],
                    "fallback_candidates": [],
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "TextBlock", "name": "BodyText", "class_path": "/Script/CommonUI.CommonTextBlock"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "missing_project_text_style" for error in errors))

    def test_validation_rejects_agsui_list_row_when_project_list_entry_exists(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/UI/WBP_ListEntry.WBP_ListEntry_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "list_row": {
                    "project_candidates": [{"class_path": "/Game/UI/WBP_ListEntry.WBP_ListEntry_C"}],
                    "fallback_candidates": [{"class_path": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C"}],
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "ListView",
                "name": "ItemsList",
                "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors[0]["code"], "project_list_entry_required")
        self.assertTrue(any(error["code"] == "no_compatible_project_list_entry" for error in errors))

    def test_validation_rejects_scroll_box_for_runtime_collection_intent(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "list_row": {
                    "project_candidates": [{"class_path": "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C", "kind": "entry_widget"}],
                    "compatible_project_candidates": [
                        {"class_path": "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C", "kind": "entry_widget"}
                    ],
                }
            },
        }
        spec = {
            "asset_path": "/Game/UI/Generated/WBP_Leaderboard",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "ScrollBox", "name": "LeaderboardRows"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "runtime_collection_requires_virtualized_list" for error in errors))

    def test_validation_rejects_complex_store_widget_missing_project_components(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/ByteWars/UI/Lists/WBP_ApprovedEntry.WBP_ApprovedEntry_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "core_component_roles": {
                "state_idle": {"resolved": "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C", "resolution_tier": "agsui_fallback"},
                "state_loading": {"resolved": "/AccelByteUITools/AGSUI/Core/WBP_AGS_LoadingIndicator.WBP_AGS_LoadingIndicator_C", "resolution_tier": "agsui_fallback"},
                "state_empty": {"resolved": "/AccelByteUITools/AGSUI/Core/WBP_AGS_EmptyState.WBP_AGS_EmptyState_C", "resolution_tier": "agsui_fallback"},
                "state_error": {"resolved": "/AccelByteUITools/AGSUI/Core/WBP_AGS_ErrorState.WBP_AGS_ErrorState_C", "resolution_tier": "agsui_fallback"},
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_StoreCatalogue",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "WidgetSwitcher",
                "name": "StateSwitcher",
                "children": [
                    {"type": "AGSStatusMessage", "name": "IdleState"},
                    {"type": "AGSLoadingIndicator", "name": "LoadingState"},
                    {
                        "type": "VerticalBox",
                        "name": "SuccessState",
                        "children": [
                            {"type": "AGSSecondaryButton", "name": "Btn_TabWeapons"},
                            {
                                "type": "TileView",
                                "name": "StoreItemsTileView",
                                "entry_widget_class": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard.WBP_AGS_StoreItemCard_C",
                            },
                        ],
                    },
                    {"type": "AGSEmptyState", "name": "EmptyState"},
                    {"type": "AGSErrorState", "name": "ErrorState"},
                ],
            },
        }

        errors = validate_spec_against_style_context(spec, context)
        codes = {error["code"] for error in errors}

        self.assertIn("project_tab_button_required", codes)
        self.assertIn("project_list_entry_required", codes)
        self.assertIn("no_compatible_project_list_entry", codes)
        self.assertIn("project_core_widget_required", codes)

    def test_validation_accepts_agsui_state_fallbacks_in_low_confidence_auto_mode(self):
        context = {
            "ui_backend": "umg",
            "confidence": "low",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "core_component_roles": {
                "state_idle": {
                    "resolved": "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C",
                    "resolution_tier": "agsui_fallback",
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Status",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "AGSStatusMessage", "name": "IdleState"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])

    def test_validation_accepts_agsui_state_fallbacks_with_explicit_agsui_style_mode(self):
        context = {
            "ui_backend": "umg",
            "confidence": "high",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "core_component_roles": {
                "state_idle": {
                    "resolved": "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C",
                    "resolution_tier": "agsui_fallback",
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Status",
            "parent_class": "/Script/UMG.UserWidget",
            "style_mode": "agsui",
            "root": {"type": "AGSStatusMessage", "name": "IdleState"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])

    def test_validation_agsui_style_mode_does_not_swap_to_generated_project_state_panel(self):
        context = {
            "ui_backend": "umg",
            "confidence": "high",
            "allowed_class_references": [
                "/Game/AGS/UI/Components/WBP_AGS_ProjectStatusPanel.WBP_AGS_ProjectStatusPanel_C"
            ],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "core_component_roles": {
                "state_idle": {
                    "resolved": "/Game/AGS/UI/Components/WBP_AGS_ProjectStatusPanel.WBP_AGS_ProjectStatusPanel_C",
                    "resolution_tier": "generated",
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Status",
            "parent_class": "/Script/UMG.UserWidget",
            "style_mode": "agsui",
            "root": {"type": "AGSStatusMessage", "name": "IdleState"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])
        self.assertNotIn("class_path", spec["root"])

    def test_validation_requires_project_core_widgets_with_explicit_project_style_mode(self):
        context = {
            "ui_backend": "umg",
            "confidence": "low",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "core_component_roles": {
                "state_idle": {
                    "resolved": "/AccelByteUITools/AGSUI/Core/WBP_AGS_StatusMessage.WBP_AGS_StatusMessage_C",
                    "resolution_tier": "agsui_fallback",
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Status",
            "parent_class": "/Script/UMG.UserWidget",
            "style_mode": "project",
            "root": {"type": "AGSStatusMessage", "name": "IdleState"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertIn("project_core_widget_required", {error["code"] for error in errors})

    def test_validation_accepts_complex_store_widget_with_project_components(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": [
                "/Game/UI/Buttons/WBP_TabButton.WBP_TabButton_C",
                "/Game/UI/Cards/WBP_StoreItemCard.WBP_StoreItemCard_C",
                "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C",
            ],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "tab_button": {
                    "project_candidates": [
                        {"class_path": "/Game/UI/Buttons/WBP_TabButton.WBP_TabButton_C", "kind": "widget"}
                    ]
                },
                "list_row": {
                    "project_candidates": [
                        {"class_path": "/Game/UI/Cards/WBP_StoreItemCard.WBP_StoreItemCard_C", "kind": "entry_widget"}
                    ],
                    "compatible_project_candidates": [
                        {"class_path": "/Game/UI/Cards/WBP_StoreItemCard.WBP_StoreItemCard_C", "kind": "entry_widget"}
                    ],
                },
            },
            "core_component_roles": {
                "state_empty": {
                    "resolved": "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C",
                    "resolution_tier": "generated",
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_StoreCatalogue",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "VerticalBox",
                "name": "SuccessState",
                "children": [
                    {
                        "type": "AGSSecondaryButton",
                        "name": "Btn_TabWeapons",
                        "class_path": "/Game/UI/Buttons/WBP_TabButton.WBP_TabButton_C",
                    },
                    {
                        "type": "TileView",
                        "name": "StoreItemsTileView",
                        "entry_widget_class": "/Game/UI/Cards/WBP_StoreItemCard.WBP_StoreItemCard_C",
                    },
                    {"type": "UserWidget", "name": "EmptyState", "core_role": "state_empty"},
                ],
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])
        self.assertEqual(
            spec["root"]["children"][2]["class_path"],
            "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C",
        )

    def test_validation_rejects_generic_entry_for_leaderboard_recipe(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": [
                "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C",
                "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C",
            ],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "list_row": {
                    "project_candidates": [
                        {
                            "class_path": "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["friends"],
                        },
                        {
                            "class_path": "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["leaderboard"],
                        },
                    ],
                    "compatible_project_candidates": [
                        {
                            "class_path": "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["friends"],
                        },
                        {
                            "class_path": "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["leaderboard"],
                        },
                    ],
                },
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_LeaderboardPanel",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "ListView",
                "name": "LeaderboardRows",
                "entry_widget_class": "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "recipe_list_entry_required" for error in errors))
        recipe_error = next(error for error in errors if error["code"] == "recipe_list_entry_required")
        self.assertEqual(
            recipe_error["recommended_project_candidates"][0]["class_path"],
            "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C",
        )

    def test_validation_auto_wires_recipe_matching_leaderboard_entry(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": [
                "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C",
                "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C",
            ],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "list_row": {
                    "project_candidates": [
                        {
                            "class_path": "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["friends"],
                        },
                        {
                            "class_path": "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["leaderboard"],
                        },
                    ],
                    "compatible_project_candidates": [
                        {
                            "class_path": "/Game/UI/WBP_PlayerEntry.WBP_PlayerEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["friends"],
                        },
                        {
                            "class_path": "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C",
                            "kind": "entry_widget",
                            "recipe_intents": ["leaderboard"],
                        },
                    ],
                },
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_LeaderboardPanel",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "ListView", "name": "LeaderboardRows"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])
        self.assertEqual(spec["root"]["entry_widget_class"], "/Game/UI/WBP_LeaderboardEntry.WBP_LeaderboardEntry_C")

    def test_validation_rejects_generated_entry_without_list_entry_parent(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/ByteWars/UI/Lists/WBP_ApprovedEntry.WBP_ApprovedEntry_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {
                "list_entry_compatible": [
                    {"name": "UStoreItemCardEntry", "module": "Game", "source": "Source/Game/UI/StoreItemCardEntry.h"}
                ]
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_StoreItemCard",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "collection_entry_parent_required" for error in errors))

    def test_validation_allows_generated_entry_with_list_entry_parent(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {
                "list_entry_compatible": [
                    {"name": "UStoreItemCardEntry", "module": "Game", "source": "Source/Game/UI/StoreItemCardEntry.h"}
                ]
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_StoreItemCard",
            "parent_class": "/Script/Game.UStoreItemCardEntry",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])

    def test_validation_normalizes_collection_entry_ui_mode_to_umg(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {
                "list_entry_compatible": [
                    {"name": "UAccelByteWarsWidgetEntry", "module": "AccelByteWars", "source": "Source/AccelByteWars/UI/AccelByteWarsWidgetEntry.h"}
                ]
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_LeaderboardEntry",
            "parent_class": "/Script/AccelByteWars.AccelByteWarsWidgetEntry",
            "ui_mode": "common_ui",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])
        self.assertEqual(spec["ui_mode"], "umg")

    def test_validation_does_not_treat_entry_named_panel_as_collection_entry(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {"list_entry_compatible": []},
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_LeaderboardEntryPanel",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "Border", "name": "PanelBackground"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertFalse(any(error["code"] == "collection_entry_parent_required" for error in errors))

    def test_validation_allows_generated_subfolder_class_reference_before_registry_refresh(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {},
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_LeaderboardPanel",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "ListView",
                "name": "LeaderboardRows",
                "entry_widget_class": "/Game/ByteWars/UI/Generated/Leaderboard/WBP_NewLeaderboardEntry.WBP_NewLeaderboardEntry_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertFalse(any(error["code"] == "unknown_class_reference" for error in errors))

    def test_validation_rejects_arbitrary_game_class_reference_outside_generated_or_components(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/ByteWars/UI/Lists/WBP_ApprovedEntry.WBP_ApprovedEntry_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "source_classes": {},
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_LeaderboardPanel",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "ListView",
                "name": "LeaderboardRows",
                "entry_widget_class": "/Game/ByteWars/UI/Random/WBP_NewLeaderboardEntry.WBP_NewLeaderboardEntry_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertTrue(any(error["code"] == "unknown_class_reference" for error in errors))

    def test_discovery_marks_unknown_list_entries_as_unresolved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            content = root / "Content" / "UI" / "Lists"
            content.mkdir(parents=True)
            (content / "WBP_PlayerEntry.uasset").write_text("", encoding="utf-8")

            context = discover_project_style(project)

        list_role = context["enforced_roles"]["list_row"]
        self.assertFalse(list_role["compatible_project_candidates"])
        self.assertTrue(list_role["incompatible_or_unknown_project_candidates"])

    def test_discovery_marks_source_backed_list_entries_compatible(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            content = root / "Content" / "UI" / "Lists"
            content.mkdir(parents=True)
            (content / "WBP_PlayerEntry.uasset").write_text("", encoding="utf-8")
            source = root / "Source" / "Game" / "UI"
            source.mkdir(parents=True)
            (source / "PlayerEntry.h").write_text(
                "class GAME_API UPlayerEntry : public UUserWidget, public IUserObjectListEntry {};",
                encoding="utf-8",
            )

            context = discover_project_style(project)

        self.assertTrue(context["enforced_roles"]["list_row"]["compatible_project_candidates"])

    def test_discovery_maps_project_widget_assets_to_matching_cpp_classes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            content = root / "Content" / "UI" / "Lists"
            content.mkdir(parents=True)
            (content / "WBP_PlayerEntry.uasset").write_text("", encoding="utf-8")
            source = root / "Source" / "Game" / "UI"
            source.mkdir(parents=True)
            (source / "PlayerEntry.h").write_text(
                "class GAME_API UPlayerEntry : public UUserWidget, public IUserObjectListEntry {};",
                encoding="utf-8",
            )

            context = discover_project_style(project)

        class_path = "/Game/UI/Lists/WBP_PlayerEntry.WBP_PlayerEntry_C"
        self.assertEqual(context["project_class_mapping"][class_path], "UPlayerEntry")

    def test_register_generated_leaderboard_entry_merges_into_discovery(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            source = root / "Source" / "Game" / "UI"
            source.mkdir(parents=True)
            (source / "LeaderboardEntryWidget.h").write_text(
                "class GAME_API ULeaderboardEntryWidget : public UUserWidget, public IUserObjectListEntry {};",
                encoding="utf-8",
            )
            spec_path = root / "Saved" / "Generated" / "Spec" / "Entries" / "leaderboard_entry.json"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text(
                json.dumps(
                    {
                        "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardEntry",
                        "parent_class": "/Script/Game.LeaderboardEntryWidget",
                        "root": {
                            "type": "Border",
                            "name": "PanelBackground",
                            "children": [
                                {"type": "TextBlock", "name": "Tb_Rank", "text": "#1"},
                                {"type": "TextBlock", "name": "Tb_PlayerName", "text": "Player"},
                                {"type": "TextBlock", "name": "Tb_Score", "text": "1000"},
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            register_generated_widget(
                project,
                "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardEntry",
                str(spec_path),
            )
            context = discover_project_style(project)

        class_path = "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardEntry.WBP_AGS_LeaderboardEntry_C"
        list_role = context["enforced_roles"]["list_row"]
        compatible = list_role["compatible_project_candidates"]
        self.assertTrue(any(candidate["class_path"] == class_path for candidate in compatible))
        self.assertTrue(any("leaderboard" in candidate.get("recipe_intents", []) for candidate in compatible))
        self.assertIn(class_path, context["allowed_class_references"])
        self.assertEqual(context["project_class_mapping"][class_path], "ULeaderboardEntryWidget")

    def test_register_generated_panel_is_not_list_entry_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            spec_path = root / "Saved" / "Generated" / "Spec" / "leaderboard_panel.json"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text(
                json.dumps(
                    {
                        "asset_path": "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardPanel",
                        "parent_class": "/Script/UMG.UserWidget",
                        "root": {"type": "Border", "name": "PanelBackground"},
                    }
                ),
                encoding="utf-8",
            )

            register_generated_widget(project, "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardPanel", str(spec_path))
            context = discover_project_style(project)

        self.assertIn("panel", context["enforced_roles"])
        self.assertNotIn("list_row", context["enforced_roles"])

    def test_stale_generated_registry_entry_does_not_become_compatible_list_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            source = root / "Source" / "Game" / "UI"
            source.mkdir(parents=True)
            (source / "LeaderboardEntryWidget.h").write_text(
                "class GAME_API ULeaderboardEntryWidget : public UUserWidget, public IUserObjectListEntry {};",
                encoding="utf-8",
            )

            register_generated_widget(
                project,
                "/Game/AGS/UI/Generated/Leaderboard/WBP_AGS_LeaderboardEntry",
                str(root / "Saved" / "Generated" / "Spec" / "missing.json"),
                roles=["leaderboard_entry"],
            )
            context = discover_project_style(project)

        list_role = context["enforced_roles"]["list_row"]
        self.assertFalse(list_role["compatible_project_candidates"])
        self.assertTrue(list_role["incompatible_or_unknown_project_candidates"])

    def test_generated_registry_keeps_multiple_widgets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["UMG"])
            spec_path = root / "Saved" / "Generated" / "Spec" / "panel.json"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text(
                json.dumps({"asset_path": "/Game/AGS/UI/Generated/WBP_OnePanel", "parent_class": "/Script/UMG.UserWidget", "root": {"type": "Border", "name": "PanelBackground"}}),
                encoding="utf-8",
            )

            register_generated_widget(project, "/Game/AGS/UI/Generated/WBP_OnePanel", str(spec_path))
            register_generated_widget(project, "/Game/AGS/UI/Generated/WBP_TwoPanel", str(spec_path))
            registry = load_generated_components_registry(project)

        self.assertEqual(len(registry["__generated_widgets"]), 2)

    def test_discovery_allows_source_classes_with_real_module_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = self._write_project(root, ["CommonUI"])
            source = root / "Source" / "AccelByteWars" / "UI"
            source.mkdir(parents=True)
            (source / "AccelByteWarsActivatableWidget.h").write_text(
                "class ACCELBYTEWARS_API UAccelByteWarsActivatableWidget : public UCommonActivatableWidget {};",
                encoding="utf-8",
            )

            context = discover_project_style(project)

        self.assertIn(
            "/Script/AccelByteWars.AccelByteWarsActivatableWidget",
            context["allowed_class_references"],
        )
        self.assertIn(
            "/Script/AccelByteWars.UAccelByteWarsActivatableWidget",
            context["allowed_class_references"],
        )

    def test_validation_applies_core_role_marker_to_project_state_panel(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {},
            "core_component_roles": {
                "state_empty": {
                    "resolved": "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C"
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {"type": "UserWidget", "name": "EmptyPanel", "core_role": "state_empty"},
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])
        self.assertEqual(
            spec["root"]["class_path"],
            "/Game/AGS/UI/Components/WBP_AGS_ProjectEmptyPanel.WBP_AGS_ProjectEmptyPanel_C",
        )

    def test_validation_allows_agsui_fallback_when_no_project_candidate_exists(self):
        context = {
            "ui_backend": "common_ui",
            "allowed_class_references": [],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
            "enforced_roles": {
                "primary_button": {
                    "project_candidates": [],
                    "fallback_candidates": [{"class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C"}],
                }
            },
        }
        spec = {
            "asset_path": "/Game/AGS/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "AGSButton",
                "name": "SubmitButton",
                "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])

    def test_validation_rejects_unknown_project_class_reference(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/UI/WBP_Approved.WBP_Approved_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
        }
        spec = {
            "asset_path": "/Game/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "UserWidget",
                "name": "UnknownWidget",
                "class_path": "/Game/UI/WBP_Unknown.WBP_Unknown_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors[0]["code"], "unknown_class_reference")

    def test_validation_allows_new_generated_project_component_before_registry_refresh(self):
        context = {
            "ui_backend": "umg",
            "allowed_class_references": ["/Game/UI/WBP_Approved.WBP_Approved_C"],
            "allowed_style_references": [],
            "discouraged_raw_widget_types": [],
        }
        spec = {
            "asset_path": "/Game/UI/Generated/WBP_Test",
            "parent_class": "/Script/UMG.UserWidget",
            "root": {
                "type": "UserWidget",
                "name": "GeneratedComponent",
                "class_path": "/Game/ByteWars/UI/Generated/WBP_NewComponent.WBP_NewComponent_C",
            },
        }

        errors = validate_spec_against_style_context(spec, context)

        self.assertEqual(errors, [])

    def test_validation_rejects_common_ui_spec_in_umg_context(self):
        errors = validate_spec_against_style_context(
            {
                "asset_path": "/Game/UI/Generated/WBP_Test",
                "parent_class": "/Script/UMG.UserWidget",
                "ui_mode": "common_ui",
                "root": {"type": "Border", "name": "Root"},
            },
            {
                "ui_backend": "umg",
                "allowed_class_references": [],
                "allowed_style_references": [],
                "discouraged_raw_widget_types": [],
            },
        )

        self.assertEqual(errors[0]["code"], "ui_backend_mismatch")


if __name__ == "__main__":
    unittest.main()
