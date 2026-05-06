import sys
import types
import unittest


class UnrealGenerateWidgetBlueprintTests(unittest.TestCase):
    def test_counts_and_flattens_spec_widget_names(self):
        sys.modules.setdefault("unreal", types.SimpleNamespace())

        from Plugins.WidgetBlueprintGenerator.Tools.unreal_generate_widget_blueprint import (
            count_widgets,
            get_spec_widget_names,
        )

        spec_root = {
            "type": "CanvasPanel",
            "name": "RootCanvas",
            "children": [
                {"type": "TextBlock", "name": "Tb_Title"},
                {
                    "type": "VerticalBox",
                    "name": "FormStack",
                    "children": [
                        {"type": "EditableTextBox", "name": "Et_Username"},
                        {"type": "EditableTextBox", "name": "Et_Password"},
                    ],
                },
            ],
        }

        self.assertEqual(count_widgets(spec_root), 5)
        self.assertEqual(
            get_spec_widget_names(spec_root),
            ["RootCanvas", "Tb_Title", "FormStack", "Et_Username", "Et_Password"],
        )


if __name__ == "__main__":
    unittest.main()
