import sys
import types
import unittest


class UnrealGenerateWidgetBlueprintTests(unittest.TestCase):
    def _import_module(self):
        sys.modules.setdefault("unreal", types.SimpleNamespace())

        try:
            from Plugins.WidgetBlueprintGenerator.Tools import unreal_generate_widget_blueprint
        except ModuleNotFoundError:
            from data.WidgetBlueprintGenerator.Tools import unreal_generate_widget_blueprint

        return unreal_generate_widget_blueprint

    def test_counts_and_flattens_spec_widget_names(self):
        unreal_generate_widget_blueprint = self._import_module()

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

        self.assertEqual(unreal_generate_widget_blueprint.count_widgets(spec_root), 5)
        self.assertEqual(
            unreal_generate_widget_blueprint.get_spec_widget_names(spec_root),
            ["RootCanvas", "Tb_Title", "FormStack", "Et_Username", "Et_Password"],
        )

    def test_resolve_widget_class_reports_unsupported_type(self):
        unreal_generate_widget_blueprint = self._import_module()
        unreal_generate_widget_blueprint.unreal = types.SimpleNamespace(
            CanvasPanel=object,
            Overlay=object,
            VerticalBox=object,
            HorizontalBox=object,
            SizeBox=object,
            Border=object,
            TextBlock=object,
            Button=object,
            EditableTextBox=object,
            Image=object,
            Spacer=object,
        )

        with self.assertRaises(ValueError) as raised:
            unreal_generate_widget_blueprint.resolve_widget_class("ScrollBox")

        self.assertEqual(str(raised.exception), "Unsupported widget type: ScrollBox")


if __name__ == "__main__":
    unittest.main()
