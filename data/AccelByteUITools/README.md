# AccelByte UI Tools

Reusable Unreal Engine editor plugin that builds and patches Widget Blueprints (UMG `.uasset` files) from JSON specs.

## What's inside

- A **live HTTP bridge** inside the running editor — fast, in-process generation (seconds per asset), used internally by the MCP tools and CLI.
- A **headless commandlet** for CI / scripted regeneration via `UnrealEditor-Cmd.exe`.
- A **Python CLI** (`Tools/accelbyte_ui_tools.py`) that drives either path.
- A **bundled AGS UI kit** under `Content/AGSUI/`: 49 themed components (Core widgets, list rows, feature blocks) plus 20 ready-made recipe panels under `Tools/specs/recipes/`.

The Python CLI, specs, patch examples, smoke wrapper, and tests are shipped in `Tools/` inside the plugin folder so the plugin is a complete reusable package.

## PowerShell CLI notes

The Python CLI prints JSON reports to stdout. In PowerShell, avoid piping direct CLI
output into early-closing consumers such as `Select-Object -First 1`; Python may see a
closed stdout pipe and exit with `255` after the command itself has succeeded. Capture
the full output first, check `$LASTEXITCODE`, then filter the captured lines:

```powershell
$output = & python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py style-discover --project YourGame.uproject --approve 2>&1
if ($LASTEXITCODE -ne 0) { $output; exit $LASTEXITCODE }
$output | Select-String '"approved"' | Select-Object -First 1
```

Use the same collect-then-filter pattern for `validate`, `generate`,
`generate-core-widgets`, and `select-ags-recipe` when probing their JSON output.

## Install

Copy `Plugins/AccelByteUITools` into an Unreal project, then enable it in the `.uproject`:

```json
{
  "Name": "AccelByteUITools",
  "Enabled": true,
  "TargetAllowList": ["Editor"]
}
```

Rebuild the editor target after enabling.

## Quick start

### Validate a spec without launching Unreal

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py validate `
       Plugins/AccelByteUITools/Tools/specs/login_widget.json
```

### Generate via MCP / CLI bridge mode (recommended, editor must be open)

```json
{
  "tool": "accelbyte_ui_generate",
  "arguments": {
    "projectPath": "D:/Path/To/Project",
    "specPath": "Content/AGS/UI/Generated/Specs/login_widget.json",
    "mode": "bridge",
    "force": true
  }
}
```

The bridge takes seconds per asset and works in-process inside the editor. Use the MCP `accelbyte_ui_validate` and `accelbyte_ui_generate` tools so specs are normalized against `Tools/specs/theme_tokens.json` before Unreal receives them. Direct localhost POSTs are an internal transport detail and should not be used by agents.

### Generate via the commandlet (headless, slower)

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py generate `
       Plugins/AccelByteUITools/Tools/specs/login_widget.json `
       --project AccelByteWars.uproject --force
```

The CLI writes `Saved/AccelByteUITools/<spec>.request.json`, launches:

```
UnrealEditor-Cmd.exe AccelByteWars.uproject -run=AccelByteUITools `
  -Request=<request.json> -unattended -nop4 -stdout -FullStdOutLogOutput
```

…then reads `Saved/AccelByteUITools/<spec>.report.json` for the result. Use `--dry-run` to print the command without launching the editor.

### Pick an AGS recipe by intent

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py select-ags-recipe "friends list panel"
```

Returns the layout + recipe JSON best matching the request. Unknown async operations fall back to `AGS_CenteredPanel` with `WBP_AGS_GenericAsyncActionBlock`.

### Patch an existing Widget Blueprint

```powershell
python Plugins/AccelByteUITools/Tools/accelbyte_ui_tools.py patch `
       Plugins/AccelByteUITools/Tools/patches/main_menu_add_button.json `
       --project AccelByteWars.uproject
```

Patches add or replace a single widget under a named parent in the target asset. The commandlet verifies the hierarchy before returning success.

The CLI does not trust Unreal's exit code by itself — if Unreal exits without writing the report, the command fails. If a crash context appears, the CLI includes the crash message in the failure JSON.

## Bridge endpoints

While the editor is loaded, the plugin exposes three localhost routes on its configured bridge port. These routes are internal transport for MCP and CLI callers; agents should not POST raw specs directly.

| Method | Route | Body |
|---|---|---|
| `GET`  | `/accelbyte-ui-tools/health`   | – |
| `POST` | `/accelbyte-ui-tools/generate` | `{ "force": <bool>, "spec": { ... } }` |
| `POST` | `/accelbyte-ui-tools/resolve`  | `{ "spec": { ... } }` |
| `POST` | `/accelbyte-ui-tools/patch`    | `{ "asset_path": ..., "parent_widget_name": ..., "widget": { ... } }` |

All responses use the same report shape: `ok`, `asset_path`, `verified_widget_count`, `verified_widget_names`, `verified_widget_classes`, `verified_backing_bindings`, `verified_collection_entries`, `errors`. Each `verified_widget_classes` item includes `class_stability`; `stale_live_coding` means the editor is holding a Live Coding / hot-reload class identity and generation is rejected until the editor is restarted or fully rebuilt. Script-backed generated parent classes are also checked through `verified_backing_bindings`; mismatches fail with `backing_binding_mismatch`.

MCP-tooled consumers (e.g. the AccelByte Unreal SDK MCP server) wrap these as `accelbyte_ui_bridge_health`, `accelbyte_ui_validate`, `accelbyte_ui_resolve`, `accelbyte_ui_generate`, and `accelbyte_ui_patch`. Use `accelbyte_ui_resolve` before writing script-backed C++ so project `class_path` overrides and collection entries are resolved without creating assets. **Always pass `mode: "bridge"`** when invoking generate / patch — `mode: "auto"` silently falls back to the commandlet (a minutes-long path) when the bridge is unavailable.

For script-backed widgets with freshly Live Coded C++ parent classes, the commandlet path is not safe: it launches a separate Unreal process that may not see the already-running editor's Live Coding state. Run Live Coding compile in the open editor, then validate and generate through bridge mode. Live Coding does not normally require an editor restart; restart the editor or run a full rebuild only if the bridge reports `stale_live_coding_class`.

## Spec format

A spec is a JSON object with three top-level fields:

```json
{
  "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_LoginPanel",
  "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
  "root": { /* widget tree */ }
}
```

- **`asset_path`** — destination. Project widgets live under `/Game/<...>/UI/Generated/`. AGS-kit plugin widgets live under `/AccelByteUITools/AGSUI/`.
- **`parent_class`** — must start with `/Script/`. Pick an AGS focused base (below) or any Unreal `UUserWidget` subclass.
- **`root`** — the widget tree. Each node has `type`, `name`, plus optional fields described below.

### Widget node fields

| Field | Type | Effect |
|---|---|---|
| `type` | string | One of the supported widget types, or a semantic alias when `class_path` is set |
| `name` | string | Variable / binding name (must be a valid Unreal identifier) |
| `is_variable` | bool | Expose to Blueprint as a variable |
| `class_path` | string | `/Path/Asset.Asset_C` reference to load a Widget Blueprint or C++ widget class |
| `text` | string | Body text for `TextBlock`/`EditableTextBox`; sets `DefaultLabel` on `UAGSButtonBase` class_path references |
| `hint_text` | string | Placeholder for `EditableTextBox`; sets `DefaultHintText` on `UAGSTextInputBase` class_path references |
| `is_password` | bool | Mask input on `EditableTextBox` |
| `padding` | `[L, T, R, B]` | Inner padding on `Border` |
| `width` / `height` | number | Override on `SizeBox` |
| `visibility` | string | `visible` / `collapsed` / `hidden` / `hit_test_invisible` / `self_hit_test_invisible` |
| `style` | object | See below |
| `slot` | object | See below |
| `children` | array | Nested nodes |

### Style

```json
"style": {
  "color":            [R, G, B, A],
  "background_color": [R, G, B, A],
  "hint_color":       [R, G, B, A],
  "corner_radius":    8,
  "border_color":     [R, G, B, A],
  "border_width":     1,
  "hover_color":      [R, G, B, A],
  "pressed_color":    [R, G, B, A]
}
```

- `color` — text color on `TextBlock`; typed text color on `EditableTextBox`; background tint on `Button`
- `background_color` — brush color on `Border`; tint on `Image`; input fill on `EditableTextBox`
- `hint_color` — placeholder / hint text color on `EditableTextBox`
- `corner_radius`, `border_color`, `border_width` - rounded surfaces/outlines for `Border`, `Button`, and `EditableTextBox`
- `hover_color`, `pressed_color` - optional button/input state fills

### Layout guidance

Prefer `Overlay` as the root for full-screen generated panels. Use the first child as a full-fill background `Border`, the second child as the main `WidgetSwitcher` or content surface, and nested flow containers for layout. Use `CanvasPanel` only when the widget truly needs coordinate or anchor placement, such as HUD regions, minimap placement, or precise floating elements.

### Slot properties per parent

| Parent | Slot keys |
|---|---|
| `CanvasPanel` | `anchors [L, T, R, B]`, `alignment [X, Y]`, `offsets [L, T, R, B]` *or* `position [X, Y]` + `size [W, H]`, `auto_size` |
| `UniformGridPanel` | `row`, `column` |
| `WrapBox` | `padding [L, T, R, B]`, `h_align`, `v_align` |
| `VerticalBox` / `HorizontalBox` | `padding [L, T, R, B]`, `size: {fill: N}` or `{auto: true}`, `h_align`, `v_align` |
| `Overlay` | `padding`, `h_align`, `v_align` |
| `ScrollBox` | `padding`, `h_align` |
| `ListView` / `TileView` / `TreeView` | `entry_widget_class`, `selection_mode`, `orientation`, `preview_entries` |

When `CanvasPanel` anchors are stretched (min ≠ max on either axis), use `offsets` (FMargin). For point anchors, use `position` + `size`.

## Supported widget types

| Category | Types |
|---|---|
| Containers | `CanvasPanel`, `Overlay`, `VerticalBox`, `HorizontalBox`, `SizeBox`, `Border`, `Button`, `SafeZone`, `ScaleBox`, `ScrollBox`, `ListView`, `TileView`, `TreeView`, `WidgetSwitcher`, `UniformGridPanel`, `WrapBox` |
| Leaves | `TextBlock`, `EditableTextBox`, `Image`, `Spacer` |
| Custom via `class_path` | Any compiled Widget Blueprint or C++ widget class |

`Button` is a content widget — it accepts a single child (typically a `TextBlock` for the label).

`ListView`, `TileView`, and `TreeView` are runtime collection widgets. Set `entry_widget_class` to the row/card widget class and populate items from the generated backing widget class. Use `preview_entries` only as design-time metadata for the agent and future tooling; it does not create runtime data by itself.

When `class_path` is present, `type` is a semantic alias for readability:

```json
{
  "type": "AGSButton",
  "name": "SubmitButton",
  "class_path": "/AccelByteUITools/AGSUI/Core/WBP_AGS_BaseButton.WBP_AGS_BaseButton_C",
  "is_variable": true,
  "text": "Sign in"
}
```

## Generate request

```json
{
  "mode": "generate",
  "force": true,
  "spec": {
    "asset_path": "/Game/AGS/UI/Generated/WBP_AGS_LoginPanel",
    "parent_class": "/Script/AccelByteUITools.AGSPanelBase",
    "root": {
      "type": "AGSLoginBlock",
      "name": "Login_SuccessBlock",
      "class_path": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_LoginBlock.WBP_AGS_LoginBlock_C",
      "is_variable": true
    }
  },
  "report_path": "D:/project/Saved/AccelByteUITools/login_widget.report.json"
}
```

`report_path` is required for the commandlet path. The bridge path returns the report inline.

## Patch request

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
  "report_path": "D:/project/Saved/AccelByteUITools/main_menu_add_button.report.json"
}
```

## AGS UI kit

The bundled kit lives under `Content/AGSUI/`:

- `Core/` — 20 atoms: badge, avatar, divider, currency pill, buttons (Base / Secondary / Danger / Icon), inputs (Text / Password / Search), state widgets (StatusMessage / LoadingIndicator / EmptyState / ErrorState / Toast), panels (BasePanel / ModalPanel / SectionHeader / KeyValueRow)
- `Lists/` — 5 list templates: `WBP_AGS_ListRow`, `WBP_AGS_PlayerRow`, `WBP_AGS_LeaderboardRow`, `WBP_AGS_EntitlementRow`, `WBP_AGS_ListPanel`
- `FeatureBlocks/` — 24 composite blocks: login, account link, session expired, friends list / friend row / incoming friend request / block user, party, matchmaking, session browser / row, leaderboard, achievements grid / card, stats summary, store grid / item card, wallet, entitlements, cloud saves, notifications, generic async

Generated AGS project widgets under `/Game/AGS/UI/Generated` may reference `AGSUI/Core` components by `class_path`, but must not reference `AGSUI/FeatureBlocks` or `AGSUI/Lists` directly. Use FeatureBlocks as structural references only, Core components for semantic controls/state atoms, and native UMG for layout and runtime collections. Inter-component spacing belongs in child `slot.padding`; node-level `padding` is inner padding.

All assets share a single **AccelByte light theme** with white/light surfaces, near-black text, blue primary actions, white secondary actions, subtle borders, and rounded controls. See [`Tools/specs/THEME.md`](Tools/specs/THEME.md) for the token reference.

The AGS kit uses native Unreal widgets. The plugin also depends on Unreal's `CommonUI` module so generated Common UI screens can use `/Script/AccelByteUITools.AGSCommonActivatableBase`.

### Common UI mode

Interactive Common UI panels should use `/Script/AccelByteUITools.AGSCommonActivatableBase` as `parent_class`. It subclasses `CommonActivatableWidget` and implements desired-focus selection by checking stable widget names such as `SubmitButton`, `ConfirmButton`, and `ValueInput`, then falling back to the first interactive widget.

Common UI specs should still use standard UMG layout containers (`Overlay`, `VerticalBox`, `WidgetSwitcher`, `ListView`, etc.). Use project-specific `CommonButtonBase` / tab-list Blueprint class paths for interactive controls instead of AGSUI component class paths.

### Focused parent classes

Use the smallest parent contract that fits the component. Each focused base declares which named widgets it binds and which methods / events it exposes:

| Class | Used by | Bindings | API |
|---|---|---|---|
| `UAGSButtonBase` | `WBP_AGS_BaseButton`, `WBP_AGS_SecondaryButton`, `WBP_AGS_DangerButton`, `WBP_AGS_IconButton` | `InteractiveButton: UButton`, `ButtonText: UTextBlock` | `DefaultLabel: FText` UPROPERTY, `SetLabel(FText)`, `OnClicked` event |
| `UAGSTextInputBase` | `WBP_AGS_TextInput`, `WBP_AGS_PasswordInput`, `WBP_AGS_SearchInput` | `LabelText: UTextBlock`, `ValueInput: UEditableTextBox`, `SubmitButton: UButton` | `DefaultHintText: FText` UPROPERTY, `SetLabel`, `SetValue`, `OnSubmit` event |
| `UAGSLabelValueWidgetBase` | Badge, Avatar, CurrencyPill, Toast, SectionHeader, KeyValueRow, all list rows | `LabelText`, `ValueText: UTextBlock` | `SetLabel`, `SetValue` |
| `UAGSStatusMessageBase` | `WBP_AGS_StatusMessage` | inherits `UAGSLabelValueWidgetBase` | `SetStatus`, `SetError` |
| `UAGSStateWidgetBase` | `WBP_AGS_BasePanel`, `WBP_AGS_EmptyState`, `WBP_AGS_ErrorState`, `WBP_AGS_LoadingIndicator`, recipe panels | `StateSwitcher: UWidgetSwitcher`; fallback `IdlePanel`, `LoadingPanel`, `SuccessPanel`, `EmptyPanel`, `ErrorPanel: UWidget` | `SetState`, `SetLoading` |
| `UAGSActionPanelBase` | `WBP_AGS_ModalPanel` | `ConfirmButton`, `CancelButton`, `RetryButton: UButton` | `OnConfirm`, `OnCancel`, `OnRetry` events |
| `UAGSListRowBase` | all `*Row` widgets | inherits `UAGSLabelValueWidgetBase` | – |
| `UAGSFeatureBlockBase` | all `*Block` widgets | inherits `UAGSStateWidgetBase` | – |
| `UAGSPanelBase` | top-level recipe panels | inherits `UAGSStateWidgetBase` | – |

### Component reuse via `class_path`

Feature blocks reference the core components by `class_path` rather than inlining duplicates. Examples:

- `WBP_AGS_LoginBlock` references `WBP_AGS_TextInput`, `WBP_AGS_PasswordInput`, and `WBP_AGS_BaseButton`
- `WBP_AGS_FriendsListBlock` references `WBP_AGS_FriendRow` (sample rows in a `ScrollBox`)
- `WBP_AGS_AchievementGridBlock` references `WBP_AGS_AchievementCard` (cells in a `UniformGridPanel`)

This means a styling change to a core asset propagates automatically — change `WBP_AGS_BaseButton`'s color, every feature block updates on next regen.

Top-level recipe panels use an `Overlay` root with a `WidgetSwitcher` named `StateSwitcher` for stateful layout. Its children must stay ordered `Idle`, `Loading`, `Success`, `Empty`, `Error` so `UAGSStateWidgetBase::SetState` can map the enum directly to `SetActiveWidgetIndex`. Generated AGS project panels that include this switcher are validated against canonical state roles: AGSUI fallback states use `AGSStatusMessage`, `AGSLoadingIndicator`, a native success container, `AGSEmptyState`, and `AGSErrorState`; project/generated state panels may use `UserWidget` with the matching `core_role` and `/Game/...` `class_path`. `core_role` does not override the C++ binding type. `UAGSStateWidgetBase` defaults to `Success`, and `SetLoading(false)` returns to `Success`, so generated widgets preview their usable content by default. The individual `IdlePanel`, `LoadingPanel`, `SuccessPanel`, `EmptyPanel`, and `ErrorPanel` bindings remain supported for older component widgets.

Generated project panels must use the schema names `PanelBackground`, `ContentContainer`, and `StateSwitcher` for the root panel hierarchy and state switcher. Focused AGS parent classes also enforce their inner binding names, such as `InteractiveButton`, `ButtonText`, `ValueInput`, `ConfirmButton`, `CancelButton`, and `RetryButton`, because those names drive runtime behavior.

### Per-instance label customization

When you place an `AGS*Button` derivative as a child of another widget, edit its **Default Label** field in the Details panel to set the displayed text. `NativePreConstruct` pushes the value into the inner `ButtonText` at edit-time preview and runtime construction, so the editor preview and the live game show the same label.

The same pattern works for `AGS*Input` widgets via **Default Hint Text**, which propagates to `ValueInput`.

To change the label at runtime:

```cpp
ButtonInstance->SetLabel(FText::FromString(TEXT("Resume")));
```

The runtime API is independent of `DefaultLabel`.

## Restyling / replacing AGS widgets

You can restyle bundled widgets in the editor or replace them with project-local variants, but keep the generated contract stable:

- Preserve generated asset class paths used by specs, or update every `class_path` reference that points at the replaced widget.
- Preserve variable widget names bound with required `BindWidget` in generated script-backed classes — especially `InteractiveButton`, `ButtonText`, `LabelText`, `ValueText`, `ValueInput`, `SubmitButton`, `ConfirmButton`, `CancelButton`, `RetryButton`, `IdlePanel`, `LoadingPanel`, `SuccessPanel`, `EmptyPanel`, `ErrorPanel`. Each must match the type declared by validation `bindings`.
- Keep Blueprint-callable behavior (`SetLabel`, `SetValue`, `SetState`, `SetStatus`, `SetError`) available from the same focused parent class or a compatible subclass.
- Prefer cosmetic changes inside the existing Widget Blueprint for color, typography, spacing, and icons. Use a new asset path only when the project needs a different layout contract.
- After replacing a widget, regenerate or patch at least one consuming recipe and confirm its `Saved/AccelByteUITools/*.report.json` has `ok: true` and non-empty `verified_widget_names`.

## Generated asset paths

| Use | Path prefix |
|---|---|
| Project-generated screens | `/Game/<project>/UI/Generated/WBP_AGS_<Name>` |
| Generated specs | `<project-root>/Content/AGS/UI/Generated/Specs/<Name>.json` |
| Generator metadata | `<project-root>/Config/AccelByteUITools/` |
| Plugin AGS-kit Core | `/AccelByteUITools/AGSUI/Core/WBP_AGS_<Name>` |
| Plugin AGS-kit Lists | `/AccelByteUITools/AGSUI/Lists/WBP_AGS_<Name>` |
| Plugin AGS-kit FeatureBlocks | `/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_<Name>` |

Recipe specs for top-level project panels: `Tools/specs/recipes/` (20 templates: `ags_login_panel.json`, `ags_leaderboard_panel.json`, `ags_tabbed_social_panel.json`, etc.).

Source specs for the bundled kit: `Tools/specs/components/agsui/` (49 component specs).
