# AGS UI Theme - AccelByte Light

`theme_tokens.json` is the canonical source of truth for AGS UI colors, radii, spacing, and component style presets. Specs may contain literal JSON values because the generator does not resolve tokens at runtime, but those literals must match `theme_tokens.json` and are covered by tests.

Use `data/AccelByteUITools/Tools/theme_tokens.py` from Python tooling instead of copying constants into scripts.

## Token File

Path:

```text
data/AccelByteUITools/Tools/specs/theme_tokens.json
```

Main groups:

| Group | Purpose |
|---|---|
| `colors.bg.*` | White panel/card/input backgrounds, subtle bands, and off-white item surfaces |
| `colors.primary.*` | AccelByte blue primary actions (`#0B6CFF`) and interaction states |
| `colors.danger.*` | Red destructive accents and error states |
| `colors.text.*` | Dark primary text, muted helper text, black input text, white action text |
| `colors.border.*` | Subtle panel borders, darker control/item borders, action borders |
| `radius.*` | 6px controls, 8px surfaces, 999px pills |
| `spacing.*` | 8px control padding, 4px collection spacing, row/card/panel padding |
| `presets.*` | Exact style objects for panels, cards, rows, inputs, buttons, status, error, divider |

Current key values:

| Token | Value |
|---|---|
| `colors.bg.primary` | `[1.0, 1.0, 1.0, 1.0]` |
| `colors.bg.item` | `[0.980392, 0.988235, 0.996078, 1.0]` |
| `colors.bg.input` | `[1.0, 1.0, 1.0, 1.0]` |
| `colors.primary.base` | `[0.043, 0.424, 1.0, 1.0]` |
| `colors.text.primary` | `[0.05, 0.06, 0.08, 1.0]` |
| `colors.text.input` | `[0.0, 0.0, 0.0, 1.0]` |
| `colors.border.control` | `[0.31, 0.36, 0.43, 1.0]` |
| `spacing.controlPadding` | `[8, 8, 8, 8]` |
| `spacing.entrySpacing` | `4` |

## Contract

- Core inputs use the `input` preset directly on the `ValueInput` `EditableTextBox`: white `background_color`, black `color`, muted `hint_color`, dark control border, 6px radius, and 8px padding.
- Primary, secondary, and danger buttons use their matching button preset on `InteractiveButton`, with 8px padding.
- List rows and tile cards use `rowItem` or `cardItem`: `#FAFCFEFF` surface, dark slate outline, and 8px radius.
- `ListView` and `TileView` collections use `horizontal_entry_spacing: 4` and `vertical_entry_spacing: 4`.
- Collection-like AGS components and recipes use `ListView` or `TileView`, not `ScrollBox`.
- Bundled AGSUI specs may keep FeatureBlocks and Lists as reusable plugin assets, but agent-generated project widgets must not reference those composites directly. Generated AGS project widgets use AGSUI/Core components for semantic controls and state atoms, and native UMG for layout and runtime collections.
- Agent-generated AGS project screens under `/Game/AGS/UI/Generated` are validated more strictly: bare native `Button` and `EditableTextBox` are rejected, collections need 4px entry spacing, and collection entry widgets must be project-owned rather than AGSUI plugin rows/cards.
- Script-backed C++ binding properties must be generated from the final validation result's `bindings` exactly, preserving spelling and case. Every generated property uses required `BindWidget`; the validator and generation report enforce type compatibility and reject `BindWidgetOptional`.
- `verified_widget_classes.class_stability` must be `stable` for generated output. `stale_live_coding` is a runtime editor-state failure; restart the editor or run a full rebuild only when that error is reported.
- Inter-component spacing belongs in child `slot.padding`; node-level `padding` is inner padding for controls and surfaces.

## Widget Property Reference

| Widget | Property in JSON | Effect |
|---|---|---|
| TextBlock | `style.color` | Text color |
| Border | `style.background_color` | Background brush color |
| Border | `style.corner_radius`, `style.border_color`, `style.border_width` | Rounded surface and outline |
| Border | `padding` | Inner padding |
| Image | `style.background_color` | Tint color |
| Button | `style.color`, `style.hover_color`, `style.pressed_color` | Button fill states |
| Button | `style.corner_radius`, `style.border_color`, `style.border_width` | Rounded button and outline |
| Button | `padding` | Normal and pressed content padding |
| EditableTextBox | `text`, `hint_text`, `is_password` | Field content and behavior |
| EditableTextBox | `style.color`, `style.hint_color` | Typed text and placeholder text colors |
| EditableTextBox | `style.background_color`, `style.corner_radius`, `style.border_color`, `style.border_width` | Rounded input field surface |
| EditableTextBox | `padding` | Text field content padding |
| ListView / TileView | `horizontal_entry_spacing`, `vertical_entry_spacing` | Native item gap |

## Layout Patterns

| Pattern | Implementation |
|---|---|
| Full-screen generated screen | `Overlay` root; full-fill `Border` background; full-fill `WidgetSwitcher` or content as the next layer |
| Card / panel background | `Border` wrapping content, using the `card` or `panel` preset and card/panel padding |
| Runtime row collection | `ListView` with `entry_widget_class`, populated by the backing widget class |
| Runtime card collection | `TileView` with `entry_widget_class`, populated by the backing widget class |
| Proportional row | `HorizontalBox` with `slot.size: {auto: true}` for fixed columns and `slot.size: {fill: 1.0}` for stretchy columns |
| Centered button row | `HorizontalBox` with `slot.h_align: right` on the box's own slot and `slot.size: {auto: true}` per button |
| Fixed-size icon / avatar | `SizeBox` with `width` and `height`, child Image inside |
| Visual separator | Thin `Border` or `SizeBox` using the `divider` preset |

Use `CanvasPanel` only for explicit coordinate/anchor placement such as HUD overlays, minimap regions, or precise floating widgets. For generated panels and menus, prefer `Overlay` plus flow containers (`VerticalBox`, `HorizontalBox`, `ListView`, `TileView`, `WrapBox`, `SizeBox`).

Stateful recipe panels default to the `Success` state for design-time preview and after `SetLoading(false)`. Keep `StateSwitcher` children ordered `Idle`, `Loading`, `Success`, `Empty`, `Error`. Generated AGS project panels that include `StateSwitcher` fail validation unless those states use the canonical aliases: `AGSStatusMessage`, `AGSLoadingIndicator`, native success container, `AGSEmptyState`, and `AGSErrorState`.
