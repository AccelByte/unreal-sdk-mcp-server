# Widget Blueprint Generator Plugin

Reusable editor-only Unreal plugin for deterministic Widget Blueprint generation and patching.

The Python CLI, specs, patch examples, smoke wrapper, and tests are shipped in `Tools/`
inside this plugin so the plugin folder is the complete reusable package.

## Install

Copy `Plugins/WidgetBlueprintGenerator` into an Unreal project and enable it in the `.uproject`:

```json
{
  "Name": "WidgetBlueprintGenerator",
  "Enabled": true,
  "TargetAllowList": ["Editor"]
}
```

Rebuild the editor target after enabling the plugin.

## Commandlet

Run the commandlet with a request JSON:

```powershell
UnrealEditor-Cmd.exe MyProject.uproject -run=WidgetBlueprintGenerator -Request=D:\path\to\request.json -unattended -nop4 -stdout -FullStdOutLogOutput
```

The request must include `report_path`. The commandlet writes a JSON report with:

- `ok`
- `asset_path`
- `verified_widget_count`
- `verified_widget_names`
- `errors`

## CLI

```powershell
python Plugins/WidgetBlueprintGenerator/Tools/widget_blueprint_generator.py generate Plugins/WidgetBlueprintGenerator/Tools/specs/login_widget.json --project AccelByteWars.uproject --force
```

For a quick smoke run from the project root:

```powershell
Plugins\WidgetBlueprintGenerator\Tools\run_widget_generator.bat
```

## Generate Request

```json
{
  "mode": "generate",
  "force": true,
  "spec": {
    "asset_path": "/Game/ByteWars/UI/Generated/WBP_Login",
    "parent_class": "/Script/AccelByteWars.LoginWidget",
    "root": {
      "type": "CanvasPanel",
      "name": "RootCanvas"
    }
  },
  "report_path": "D:/project/Saved/WidgetBlueprintGenerator/login_widget.report.json"
}
```

## Patch Request

```json
{
  "mode": "patch",
  "asset_path": "/Game/ByteWars/UI/MainMenu/W_MainMenu",
  "parent_widget_name": "Vb_TutorialModuleButtons",
  "widget": {
    "type": "TextBlock",
    "name": "GeneratedTestLabel",
    "text": "Generated Test"
  },
  "report_path": "D:/project/Saved/WidgetBlueprintGenerator/main_menu_add_button.report.json"
}
```
