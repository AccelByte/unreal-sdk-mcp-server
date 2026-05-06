# Widget Blueprint Generator

Reusable CLI shipped inside the `Plugins/WidgetBlueprintGenerator` editor plugin.

The CLI writes a request JSON file, launches Unreal through the `WidgetBlueprintGenerator`
commandlet, then prints the commandlet report JSON. The commandlet does the actual
Widget Blueprint creation or modification in C++ editor code.

## Validate

```powershell
python Plugins/WidgetBlueprintGenerator/Tools/widget_blueprint_generator.py validate Plugins/WidgetBlueprintGenerator/Tools/specs/sample_menu.json
```

## Generate

```powershell
python Plugins/WidgetBlueprintGenerator/Tools/widget_blueprint_generator.py generate Plugins/WidgetBlueprintGenerator/Tools/specs/sample_menu.json --project AccelByteWars.uproject
```

Use `--dry-run` to print the Unreal command without launching the editor.

Generation writes `Saved/WidgetBlueprintGenerator/<spec-name>.request.json`, then launches:

```powershell
UnrealEditor-Cmd.exe AccelByteWars.uproject -run=WidgetBlueprintGenerator -Request=<request.json>
```

The report is written to `Saved/WidgetBlueprintGenerator/<spec-name>.report.json`.

## Patch

```powershell
python Plugins/WidgetBlueprintGenerator/Tools/widget_blueprint_generator.py patch Plugins/WidgetBlueprintGenerator/Tools/patches/main_menu_add_button.json --project AccelByteWars.uproject
```

Patch requests add or replace one widget under an existing parent widget. The commandlet
verifies the saved Widget Blueprint hierarchy before returning success.

The CLI does not trust Unreal's process exit code by itself. If Unreal exits without writing the report, the command returns failure.
If Unreal writes a crash context before the report appears, the CLI includes the crash
message in the failure JSON.

For a quick local smoke run, use:

```powershell
Plugins\WidgetBlueprintGenerator\Tools\run_widget_generator.bat
```

## Smoke Spec

`Plugins/WidgetBlueprintGenerator/Tools/specs/smoke_info_widget.json` targets the existing `/Script/AccelByteWars.InfoWidget` class so the generator can be exercised without first creating a new C++ widget class.

## Current Scope

The MVP supports `CanvasPanel`, `Overlay`, `VerticalBox`, `HorizontalBox`, `SizeBox`, `Border`, `TextBlock`, `Button`, `EditableTextBox`, `Image`, `Spacer`, `AccelByteWarsButtonBase`, and arbitrary widget blueprint classes loaded through `class_path`.

The generator only writes generated assets under `/Game/ByteWars/UI/Generated`.
