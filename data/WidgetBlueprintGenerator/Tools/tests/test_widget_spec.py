import unittest

try:
    from Plugins.WidgetBlueprintGenerator.Tools.widget_spec import (
        ValidationError,
        load_spec_from_dict,
    )
except ModuleNotFoundError:
    from data.WidgetBlueprintGenerator.Tools.widget_spec import (
        ValidationError,
        load_spec_from_dict,
    )


class WidgetSpecTests(unittest.TestCase):
    def test_loads_valid_spec_and_counts_widgets(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_SampleMenu",
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

        self.assertEqual(spec.asset_path, "/Game/ByteWars/UI/Generated/WBP_SampleMenu")
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
                    "root": {"type": "ScrollBox", "name": "UnsupportedRoot"},
                }
            )

        self.assertEqual(raised.exception.code, "unsupported_widget")

    def test_accepts_class_path_widget_type(self):
        spec = load_spec_from_dict(
            {
                "asset_path": "/Game/ByteWars/UI/Generated/WBP_CustomWidgetHost",
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


if __name__ == "__main__":
    unittest.main()
