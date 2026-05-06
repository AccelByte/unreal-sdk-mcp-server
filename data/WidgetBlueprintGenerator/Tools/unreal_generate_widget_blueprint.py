from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

import unreal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--force", action="store_true")
    args, _unknown = parser.parse_known_args(argv)

    try:
        spec_path = Path(args.spec)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        report = generate_widget_blueprint(spec, force=args.force)
        write_report(spec_path, report)
        if report["errors"]:
            unreal.log_error(json.dumps(report, indent=2))
            return 1
        unreal.log(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        report = {
            "ok": False,
            "asset_path": None,
            "parent_class": None,
            "expected_widget_count": 0,
            "verified_widget_count": 0,
            "verified_widget_names": [],
            "warnings": [],
            "errors": [
                {
                    "code": "unreal_generation_failed",
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ],
        }
        write_report(Path(args.spec), report)
        unreal.log_error(json.dumps(report, indent=2))
        return 1


def generate_widget_blueprint(spec: dict, force: bool) -> dict:
    asset_path = spec["asset_path"]
    parent_class_path = spec["parent_class"]
    parent_class = unreal.load_class(None, parent_class_path)
    warnings = []
    errors = []
    expected_widget_count = count_widgets(spec["root"])
    verified_widget_count = 0
    verified_widget_names = []

    if parent_class is None:
        return _report(
            False,
            asset_path,
            parent_class_path,
            expected_widget_count,
            verified_widget_count,
            verified_widget_names,
            warnings,
            [{"code": "parent_class_missing", "message": parent_class_path}],
        )

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path) and not force:
        return _report(
            False,
            asset_path,
            parent_class_path,
            expected_widget_count,
            verified_widget_count,
            verified_widget_names,
            warnings,
            [
                {
                    "code": "asset_path_denied",
                    "message": "Asset already exists. Use --force to overwrite generated assets.",
                }
            ],
        )

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    package_path, asset_name = asset_path.rsplit("/", 1)
    factory = unreal.WidgetBlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)

    widget_blueprint = asset_tools.create_asset(asset_name, package_path, unreal.WidgetBlueprint, factory)
    if widget_blueprint is None:
        return _report(
            False,
            asset_path,
            parent_class_path,
            expected_widget_count,
            verified_widget_count,
            verified_widget_names,
            warnings,
            [{"code": "unreal_generation_failed", "message": "create_asset returned None"}],
        )

    widget_tree = get_widget_tree(widget_blueprint)
    if widget_tree is None:
        warnings.append(
            {
                "code": "widget_tree_unavailable",
                "message": "Widget Blueprint asset was created, but UE Python did not expose WidgetTree editing for this asset.",
            }
        )
        populated, populate_error = populate_widget_blueprint_from_json(asset_path, spec)
        if not populated:
            errors.append(
                {
                    "code": "widget_hierarchy_unverified",
                    "message": "Widget Blueprint hierarchy could not be created by the editor helper.",
                    "detail": populate_error,
                }
            )
    else:
        root_widget = build_widget_tree(widget_tree, spec["root"])
        widget_tree.set_editor_property("root_widget", root_widget)

    kismet_editor_utilities = getattr(unreal, "KismetEditorUtilities", None)
    if kismet_editor_utilities is None:
        warnings.append(
            {
                "code": "compile_unavailable",
                "message": "unreal.KismetEditorUtilities is not exposed in this Unreal Python environment; asset was saved without explicit compile.",
            }
        )
    else:
        try:
            kismet_editor_utilities.compile_blueprint(widget_blueprint)
        except Exception as exc:
            errors.append({"code": "compile_failed", "message": str(exc)})

    if not unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False):
        errors.append({"code": "save_failed", "message": asset_path})

    verified_widget_names, verify_error = verify_widget_blueprint_hierarchy(asset_path, widget_tree)
    verified_widget_count = len(verified_widget_names)
    expected_widget_names = get_spec_widget_names(spec["root"])
    missing_widget_names = [name for name in expected_widget_names if name not in verified_widget_names]
    if verify_error:
        errors.append({"code": "widget_hierarchy_unverified", "message": verify_error})
    elif missing_widget_names:
        errors.append(
            {
                "code": "widget_hierarchy_mismatch",
                "message": "Generated Widget Blueprint is missing widgets from the spec.",
                "missing_widget_names": missing_widget_names,
                "expected_widget_names": expected_widget_names,
                "verified_widget_names": verified_widget_names,
            }
        )
    elif verified_widget_count == 0:
        errors.append(
            {
                "code": "widget_hierarchy_empty",
                "message": "Generated Widget Blueprint has an empty widget hierarchy.",
            }
        )

    return _report(
        not errors,
        asset_path,
        parent_class_path,
        expected_widget_count,
        verified_widget_count,
        verified_widget_names,
        warnings,
        errors,
    )


def build_widget_tree(widget_tree, node: dict):
    widget = widget_tree.construct_widget(resolve_widget_class(node["type"]), node["name"])
    apply_widget_properties(widget, node)
    for child in node.get("children", []):
        child_widget = build_widget_tree(widget_tree, child)
        attach_child(widget, child_widget)
    return widget


def attach_child(parent, child) -> None:
    if hasattr(parent, "add_child"):
        parent.add_child(child)
        return
    if hasattr(parent, "set_content"):
        parent.set_content(child)
        return
    raise RuntimeError(f"Widget '{parent.get_name()}' cannot contain child '{child.get_name()}'.")


def get_widget_tree(widget_blueprint):
    if hasattr(widget_blueprint, "widget_tree"):
        return widget_blueprint.widget_tree
    try:
        return widget_blueprint.get_editor_property("widget_tree")
    except Exception:
        return None


def get_widget_tree_names(widget_tree) -> list[str]:
    root_widget = None
    try:
        root_widget = widget_tree.get_editor_property("root_widget")
    except Exception:
        root_widget = getattr(widget_tree, "root_widget", None)

    if root_widget is None:
        return []

    names = []
    visit_widget(root_widget, names)
    return names


def visit_widget(widget, names: list[str]) -> None:
    names.append(widget.get_name())
    if hasattr(widget, "get_children_count") and hasattr(widget, "get_child_at"):
        for index in range(widget.get_children_count()):
            visit_widget(widget.get_child_at(index), names)
        return
    if hasattr(widget, "get_content"):
        child = widget.get_content()
        if child is not None:
            visit_widget(child, names)


def populate_widget_blueprint_from_json(asset_path: str, spec: dict) -> tuple[bool, str | None]:
    helper = getattr(unreal, "WidgetBlueprintGeneratorLibrary", None)
    if helper is None:
        return False, "unreal.WidgetBlueprintGeneratorLibrary is not exposed."
    try:
        result = helper.populate_widget_blueprint_from_json(asset_path, json.dumps(spec))
    except Exception as exc:
        return False, str(exc)
    if isinstance(result, tuple):
        return bool(result[0]), result[1] if len(result) > 1 else None
    return bool(result), None


def verify_widget_blueprint_hierarchy(asset_path: str, widget_tree) -> tuple[list[str], str | None]:
    helper = getattr(unreal, "WidgetBlueprintGeneratorLibrary", None)
    if helper is not None:
        try:
            result = helper.read_widget_blueprint_hierarchy(asset_path)
        except Exception as exc:
            return [], str(exc)
        if isinstance(result, tuple):
            count = int(result[0])
            names = list(result[1]) if len(result) > 1 and result[1] is not None else []
            error = result[2] if len(result) > 2 else None
            return names[:count] if names else names, error or None

    if widget_tree is None:
        return [], "WidgetTree is unavailable."
    return get_widget_tree_names(widget_tree), None


def resolve_widget_class(widget_type: str):
    classes = {
        "CanvasPanel": unreal.CanvasPanel,
        "Overlay": unreal.Overlay,
        "VerticalBox": unreal.VerticalBox,
        "HorizontalBox": unreal.HorizontalBox,
        "SizeBox": unreal.SizeBox,
        "Border": unreal.Border,
        "TextBlock": unreal.TextBlock,
        "Button": unreal.Button,
        "EditableTextBox": unreal.EditableTextBox,
        "Image": unreal.Image,
        "Spacer": unreal.Spacer,
    }
    if widget_type == "AccelByteWarsButtonBase":
        loaded = unreal.load_class(None, "/Script/AccelByteWars.AccelByteWarsButtonBase")
        if loaded is None:
            raise RuntimeError("AccelByteWarsButtonBase could not be loaded.")
        return loaded
    return classes[widget_type]


def apply_widget_properties(widget, node: dict) -> None:
    if "text" in node and hasattr(widget, "set_text"):
        widget.set_text(unreal.Text(node["text"]))
    style = node.get("style", {})
    if "color" in style and hasattr(widget, "set_color_and_opacity"):
        widget.set_color_and_opacity(unreal.SlateColor(unreal.LinearColor(*style["color"])))


def count_widgets(node: dict) -> int:
    return 1 + sum(count_widgets(child) for child in node.get("children", []))


def get_spec_widget_names(node: dict) -> list[str]:
    names = [node["name"]]
    for child in node.get("children", []):
        names.extend(get_spec_widget_names(child))
    return names


def _report(
    ok: bool,
    asset_path: str | None,
    parent_class: str | None,
    expected_widget_count: int,
    verified_widget_count: int,
    verified_widget_names: list[str],
    warnings: list,
    errors: list,
) -> dict:
    return {
        "ok": ok,
        "asset_path": asset_path,
        "parent_class": parent_class,
        "expected_widget_count": expected_widget_count,
        "verified_widget_count": verified_widget_count,
        "verified_widget_names": verified_widget_names,
        "warnings": warnings,
        "errors": errors,
    }


def write_report(spec_path: Path, report: dict) -> None:
    output_dir = find_project_root(spec_path) / "Saved" / "WidgetBlueprintGenerator"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{spec_path.stem}.report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def find_project_root(path: Path) -> Path:
    resolved = path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if any(parent.glob("*.uproject")):
            return parent
    return Path.cwd()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
