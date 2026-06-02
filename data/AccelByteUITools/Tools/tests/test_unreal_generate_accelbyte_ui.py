import sys
import types
import unittest


class UnrealGenerateWidgetBlueprintTests(unittest.TestCase):
    def _import_module(self):
        sys.modules.setdefault("unreal", types.SimpleNamespace())

        try:
            from Plugins.AccelByteUITools.Tools import unreal_generate_accelbyte_ui
        except ModuleNotFoundError:
            from data.AccelByteUITools.Tools import unreal_generate_accelbyte_ui

        return unreal_generate_accelbyte_ui

    def test_counts_and_flattens_spec_widget_names(self):
        unreal_generate_accelbyte_ui = self._import_module()

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

        self.assertEqual(unreal_generate_accelbyte_ui.count_widgets(spec_root), 5)
        self.assertEqual(
            unreal_generate_accelbyte_ui.get_spec_widget_names(spec_root),
            ["RootCanvas", "Tb_Title", "FormStack", "Et_Username", "Et_Password"],
        )

    def test_resolve_widget_class_reports_unsupported_type(self):
        unreal_generate_accelbyte_ui = self._import_module()
        unreal_generate_accelbyte_ui.unreal = types.SimpleNamespace(
            CanvasPanel=object,
            Overlay=object,
            VerticalBox=object,
            HorizontalBox=object,
            SizeBox=object,
            Border=object,
            SafeZone=object,
            ScaleBox=object,
            ScrollBox=object,
            ListView=object,
            TileView=object,
            TreeView=object,
            WidgetSwitcher=object,
            UniformGridPanel=object,
            WrapBox=object,
            TextBlock=object,
            Button=object,
            EditableTextBox=object,
            Image=object,
            Spacer=object,
        )

        with self.assertRaises(ValueError) as raised:
            unreal_generate_accelbyte_ui.resolve_widget_class("VirtualList")

        self.assertEqual(str(raised.exception), "Unsupported widget type: VirtualList")

    def test_resolve_widget_class_supports_native_collection_types(self):
        unreal_generate_accelbyte_ui = self._import_module()
        list_view = object()
        tile_view = object()
        tree_view = object()
        unreal_generate_accelbyte_ui.unreal = types.SimpleNamespace(
            CanvasPanel=object,
            Overlay=object,
            VerticalBox=object,
            HorizontalBox=object,
            SizeBox=object,
            Border=object,
            SafeZone=object,
            ScaleBox=object,
            ScrollBox=object,
            ListView=list_view,
            TileView=tile_view,
            TreeView=tree_view,
            WidgetSwitcher=object,
            UniformGridPanel=object,
            WrapBox=object,
            TextBlock=object,
            Button=object,
            EditableTextBox=object,
            Image=object,
            Spacer=object,
        )

        self.assertIs(unreal_generate_accelbyte_ui.resolve_widget_class("ListView"), list_view)
        self.assertIs(unreal_generate_accelbyte_ui.resolve_widget_class("TileView"), tile_view)
        self.assertIs(unreal_generate_accelbyte_ui.resolve_widget_class("TreeView"), tree_view)

    def test_resolve_widget_class_uses_class_path_when_present(self):
        unreal_generate_accelbyte_ui = self._import_module()
        loaded_class = object()
        calls = []

        def load_class(_outer, class_path):
            calls.append(class_path)
            return loaded_class

        unreal_generate_accelbyte_ui.unreal = types.SimpleNamespace(load_class=load_class)

        resolved = unreal_generate_accelbyte_ui.resolve_widget_class(
            {
                "type": "AGSBaseButton",
                "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
            }
        )

        self.assertIs(resolved, loaded_class)
        self.assertEqual(
            calls,
            ["/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C"],
        )


if __name__ == "__main__":
    unittest.main()
