import json
import tempfile
import unittest
from pathlib import Path

from Plugins.WidgetBlueprintGenerator.Tools.widget_blueprint_generator import (
    build_unreal_command,
    main,
    read_crash_error,
    write_commandlet_request,
    write_patch_commandlet_request,
    write_startup_request,
    write_unreal_runner,
)


VALID_SPEC = {
    "asset_path": "/Game/ByteWars/UI/Generated/WBP_SampleMenu",
    "parent_class": "/Script/AccelByteWars.SampleMenuWidget",
    "root": {"type": "CanvasPanel", "name": "RootCanvas"},
}

VALID_PATCH = {
    "asset_path": "/Game/ByteWars/UI/MainMenu/W_MainMenu",
    "parent_widget_name": "Vb_TutorialModuleButtons",
    "widget": {
        "type": "TextBlock",
        "name": "GeneratedTestLabel",
        "text": "Generated Test",
    },
}


class WidgetBlueprintGeneratorCliTests(unittest.TestCase):
    def test_validate_returns_zero_for_valid_spec(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            spec_path = Path(temp_dir) / "valid.json"
            spec_path.write_text(json.dumps(VALID_SPEC), encoding="utf-8")

            self.assertEqual(main(["validate", str(spec_path)]), 0)

    def test_validate_returns_nonzero_for_invalid_spec(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            spec_path = Path(temp_dir) / "invalid.json"
            spec_path.write_text(
                json.dumps({**VALID_SPEC, "asset_path": "/Game/ByteWars/UI/WBP_Bad"}),
                encoding="utf-8",
            )

            self.assertEqual(main(["validate", str(spec_path)]), 1)

    def test_build_unreal_command_uses_commandlet_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "AccelByteWars.uproject"
            project.write_text("{}", encoding="utf-8")
            request = Path(temp_dir) / "request.json"
            request.write_text("{}", encoding="utf-8")

            command = build_unreal_command(
                editor_exe="E:/EpicGames/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe",
                project=str(project),
                request=request,
            )

        self.assertIn("UnrealEditor-Cmd.exe", command[0])
        self.assertIn("AccelByteWars.uproject", command[1])
        self.assertIn("-run=WidgetBlueprintGenerator", command)
        self.assertTrue(any(item.startswith("-Request=") for item in command))
        self.assertIn("-unattended", command)
        self.assertIn("-nop4", command)
        self.assertNotIn("--spec", command)

    def test_write_commandlet_request_embeds_spec_and_report_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "AccelByteWars.uproject"
            project.write_text("{}", encoding="utf-8")
            spec_path = Path(temp_dir) / "sample_menu.json"
            spec_path.write_text(json.dumps(VALID_SPEC), encoding="utf-8")

            request_path = write_commandlet_request(
                project=str(project),
                spec=str(spec_path),
                force=True,
                output_dir=Path(temp_dir),
            )

            request = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(request["mode"], "generate")
            self.assertTrue(request["force"])
            self.assertEqual(request["spec"]["asset_path"], VALID_SPEC["asset_path"])
            self.assertTrue(request["report_path"].endswith("sample_menu.report.json"))

    def test_write_patch_commandlet_request_embeds_patch_and_report_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "AccelByteWars.uproject"
            project.write_text("{}", encoding="utf-8")
            patch_path = Path(temp_dir) / "main_menu_add_button.json"
            patch_path.write_text(json.dumps(VALID_PATCH), encoding="utf-8")

            request_path = write_patch_commandlet_request(
                project=str(project),
                patch=str(patch_path),
                output_dir=Path(temp_dir),
            )

            request = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(request["mode"], "patch")
            self.assertEqual(request["asset_path"], VALID_PATCH["asset_path"])
            self.assertEqual(request["parent_widget_name"], VALID_PATCH["parent_widget_name"])
            self.assertEqual(request["widget"]["name"], "GeneratedTestLabel")
            self.assertTrue(request["report_path"].endswith("main_menu_add_button.report.json"))

    def test_read_crash_error_from_unreal_crash_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            context_path = Path(temp_dir) / "CrashContext.runtime-xml"
            context_path.write_text(
                "<FGenericCrashContext><RuntimeProperties>"
                "<ErrorMessage>Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x0</ErrorMessage>"
                "</RuntimeProperties></FGenericCrashContext>",
                encoding="utf-8",
            )

            self.assertEqual(
                read_crash_error(context_path),
                "Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x0",
            )

    def test_write_unreal_runner_embeds_spec_and_force(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = write_unreal_runner(
                spec="D:/demo/bytewarscore/Plugins/WidgetBlueprintGenerator/Tools/specs/sample_menu.json",
                force=True,
                output_dir=Path(temp_dir),
            )

            content = runner.read_text(encoding="utf-8")
            self.assertIn("unreal_generate_widget_blueprint", content)
            self.assertIn("sample_menu.json", content)
            self.assertIn("--force", content)

    def test_write_startup_request_uses_project_saved_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "AccelByteWars.uproject"
            project.write_text("{}", encoding="utf-8")

            request_path = write_startup_request(
                project=str(project),
                spec="D:/demo/bytewarscore/Plugins/WidgetBlueprintGenerator/Tools/specs/sample_menu.json",
                force=True,
            )

            self.assertEqual(request_path.name, "run_request.json")
            self.assertEqual(request_path.parent.name, "WidgetBlueprintGenerator")
            request = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertTrue(request["force"])
            self.assertTrue(request["quit_editor"])
            self.assertIn("sample_menu.json", request["spec"])


if __name__ == "__main__":
    unittest.main()
