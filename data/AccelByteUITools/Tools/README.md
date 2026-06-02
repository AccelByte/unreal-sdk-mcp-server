# AccelByte UI Tools

Reusable CLI shipped inside the `Plugins/AccelByteUITools` editor plugin.

The CLI writes a request JSON file, launches Unreal through the `AccelByteUITools`
commandlet, then prints the commandlet report JSON. The commandlet does the actual
Widget Blueprint creation or modification in C++ editor code.

## PowerShell output probing

Several CLI commands print pretty JSON to stdout, including `validate`, `style-discover`,
`generate`, `generate-core-widgets`, and `select-ags-recipe`. When checking a single
field from PowerShell, do not pipe the Python process directly into an early-closing
consumer such as `Select-Object -First 1`. That can close stdout while Python is still
writing and surface as exit code `255`, even when the command already succeeded.

Collect the full output first, then filter it:

```powershell
$output = & python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py style-discover --project YourGame.uproject --approve 2>&1
if ($LASTEXITCODE -ne 0) { $output; exit $LASTEXITCODE }
$output | Select-String '"approved"' | Select-Object -First 1
```

The `"approved": true` field from `style-discover --approve` is the style-context
approval state. It is not the same as MCP `userApproved` safety gates for editor
close/build/launch actions.

## Validate

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py validate Plugins/AccelByteUITools/Tools/specs/sample_menu.json
```

## Style Discovery Gate

Before generating or patching project UI, discover the active project's existing UI conventions:

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py style-discover --project YourGame.uproject
```

The command writes `Saved/AccelByteUITools/project_style_context.json` and prints the detected UI backend, reusable widget/style candidates, enforced validation rules, warnings, and unresolved ambiguities. The context separates project candidates from AGSUI fallback candidates and emits `enforced_roles` for buttons, text, inputs, list rows, panels, modals, and state widgets. Review those findings with the user before generation.

Once the findings are approved, persist that approval:

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py style-discover --project YourGame.uproject --approve
```

Generation refuses to run when the approved style-context fingerprint is missing or stale. Approved findings are mandatory defaults for generated project widgets; AGSUI/Core and literal theme styling are fallback only when the relevant role has no project candidate. `--approve-style-context` is available for explicit automation where the current findings have already been accepted by the caller.

## Generate

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py generate Plugins/AccelByteUITools/Tools/specs/sample_menu.json --project YourGame.uproject
```

Use `--dry-run` to print the Unreal command without launching the editor.

Generation writes `Saved/AccelByteUITools/<spec-name>.request.json`, then launches:

```powershell
UnrealEditor-Cmd.exe YourGame.uproject -run=AccelByteUITools -Request=<request.json>
```

The report is written to `Saved/AccelByteUITools/<spec-name>.report.json`.

## Select AGS Recipe

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py select-ags-recipe "friends list panel"
```

The command returns the fallback layout and recipe JSON that match the AGS UI selection rules.
Unknown AGS async operations return `AGS_CenteredPanel` with `WBP_AGS_GenericAsyncActionBlock`.

## Patch

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py patch Plugins/AccelByteUITools/Tools/patches/main_menu_add_button.json --project YourGame.uproject
```

Patch requests add or replace one widget under an existing parent widget. The commandlet
verifies the saved Widget Blueprint hierarchy before returning success.
Patch uses the same approved project style context as generation.

The CLI does not trust Unreal's process exit code by itself. If Unreal exits without writing the report, the command returns failure.
If Unreal writes a crash context before the report appears, the CLI includes the crash
message in the failure JSON.

For a quick local smoke run, use:

```powershell
Plugins\AccelByteUITools\Tools\run_widget_generator.bat
```

## Smoke Spec

`Plugins/AccelByteUITools/Tools/specs/smoke_info_widget.json` targets an existing project widget class so the generator can be exercised without first creating a new C++ widget class.

## Current Scope

The MVP supports `CanvasPanel`, `Overlay`, `VerticalBox`, `HorizontalBox`, `SizeBox`, `Border`, `Button`, `SafeZone`, `ScaleBox`, `ScrollBox`, `ListView`, `TileView`, `TreeView`, `WidgetSwitcher`, `UniformGridPanel`, `WrapBox`, `TextBlock`, `EditableTextBox`, `Image`, `Spacer`, project button wrappers, and arbitrary widget classes loaded through `class_path`.

Prefer `Overlay` as the root for full-screen generated panels: first child full-fill background `Border`, second child main `WidgetSwitcher` or content. Use `CanvasPanel` only for explicit coordinate/anchor placement such as HUD overlays or precise floating regions.

Use native collection widgets for runtime data-backed lists:

- `ListView` for rosters, feeds, inboxes, servers, friends, guild members, reports, and row-based inventories.
- `TileView` for reward cards, achievements, cosmetics, loadouts, store items, and selectable cards.
- `TreeView` for hierarchical categories such as channels, nested guild roles, or grouped settings.

Collection widgets require `entry_widget_class` in `/Root/Path/Asset.Asset_C` form. They may also set `selection_mode` (`none`, `single`, `multi`), `orientation` (`horizontal`, `vertical`), and `preview_entries` for design-time mock data. Runtime population belongs in the generated backing widget class.

`EditableTextBox` supports `style.color` for typed text, `style.hint_color` for placeholder text, and the rounded-surface fields `style.background_color`, `style.corner_radius`, `style.border_color`, and `style.border_width`. `Button` also supports `style.hover_color` and `style.pressed_color` for light-theme control states. Common UI buttons may use `button_style_class` and Common UI text blocks may use `text_style_class`; both must reference approved project style classes when discovery found project candidates.

Generated project widgets must use a project UI generated path such as `/Game/AGS/UI/Generated/WBP_AGS_LoginPanel`.
Bundled AGS kit components may be generated under plugin content paths such as `/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton`.

When `class_path` is present, `type` is treated as a semantic alias for readability. For example:

```json
{
  "type": "AGSBaseButton",
  "name": "Btn_Login",
  "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
  "is_variable": true
}
```

Generated AGS project widgets under `/Game/AGS/UI/Generated` must use approved project class/style references for semantic controls when `enforced_roles` has project candidates. They must not reference AGSUI FeatureBlocks directly; AGSUI/Core controls and AGSUI list rows are fallback only when the matching project role is absent. Use child `slot.padding` for gaps between flow-container children; node-level `padding` is inner padding for controls and surfaces.

AGS fallback recipes live in `Plugins/AccelByteUITools/Tools/specs/recipes`.
Bundled component source specs live in `Plugins/AccelByteUITools/Tools/specs/components/agsui`.

The bundled AGS kit is generated from 49 component specs and 19 recipe specs. Project screens are expected to live under `/Game/AGS/UI/Generated`; reusable fallback components are expected to live under `/AccelByteUITools/AGSUI`.

## AGS Contract Notes

The AGS kit uses native Unreal widgets only. `UAGSWidgetBase` only provides shared enable/disable behavior; component behavior lives in focused bases:

- `UAGSButtonBase` for button assets with `InteractiveButton` and `ButtonText`.
- `UAGSTextInputBase` for input assets with `LabelText`, `ValueInput`, and optional `SubmitButton`.
- `UAGSStatusMessageBase` for status/error display with `ValueText`.
- `UAGSLabelValueWidgetBase` for visual label/value components.
- `UAGSStateWidgetBase`, `UAGSActionPanelBase`, `UAGSListRowBase`, `UAGSFeatureBlockBase`, and `UAGSPanelBase` for larger stateful surfaces.

Stateful recipe panels should bind a `WidgetSwitcher` named `StateSwitcher` with children ordered `Idle`, `Loading`, `Success`, `Empty`, `Error`. `UAGSStateWidgetBase` drives this switcher directly and defaults to `Success` so generated widgets preview usable content. `SetLoading(false)` also returns to `Success`. The older `IdlePanel`, `LoadingPanel`, `SuccessPanel`, `EmptyPanel`, and `ErrorPanel` bindings remain supported as a fallback for component widgets that do not use a switcher.

Generated AGS panels that define `StateSwitcher` are fail-fast validated: AGSUI fallback states use `AGSStatusMessage`, `AGSLoadingIndicator`, `AGSEmptyState`, and `AGSErrorState`; project/generated state panels may use `UserWidget` plus the matching `core_role` and `/Game/...` `class_path`. `core_role` is only a schema/normalization hint. `validate` also reports a `bindings` array for every `is_variable: true` node; generated script-backed C++ must use those entries with required `BindWidget`.

For generated project panels, `PanelBackground`, `ContentContainer`, and `StateSwitcher` are enforced schema names, not style suggestions. A state-like `WidgetSwitcher` with a different name is rejected so `UAGSStateWidgetBase` behavior and theme normalization stay deterministic.

Generation also verifies runtime class stability in the running editor. If the bridge reports `stale_live_coding_class`, the editor is holding a Live Coding / hot-reload class identity for a widget binding class; restart the editor or run a full rebuild, then regenerate. This is a recovery path only, not part of normal generation.

Common UI screens should use `/Script/AccelByteUITools.AGSCommonActivatableBase` for interactive panels, plus project-specific `CommonButtonBase` / tab-list Blueprint class paths for interactive controls. The plugin depends on `CommonUI` and `EditorScriptingUtilities`.

When restyling or replacing bundled AGS widgets, keep generated references compatible:

- Keep `class_path` values in specs in `/Root/Path/Asset.Asset_C` form and update all references if a widget moves.
- Preserve binding names used by focused parent classes: `StateSwitcher`, `InteractiveButton`, `ButtonText`, `LabelText`, `ValueText`, `ValueInput`, `SubmitButton`, `ConfirmButton`, `CancelButton`, `RetryButton`, `IdlePanel`, `LoadingPanel`, `SuccessPanel`, `EmptyPanel`, and `ErrorPanel`. These names are enforced for specs whose `parent_class` is one of the AGS focused base classes.
- Keep compatible Blueprint-callable functions on the same focused parent class or a compatible subclass.
- Regenerate a consuming component or recipe after changes and verify the corresponding report has `ok: true`.
