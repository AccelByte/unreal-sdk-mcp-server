from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

import unreal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", required=True)
    args, _unknown = parser.parse_known_args(argv)

    patch_path = Path(args.patch)
    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
        report = apply_patch(patch)
        write_report(patch_path, report)
        if report["errors"]:
            unreal.log_error(json.dumps(report, indent=2))
            return 1
        unreal.log(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        report = {
            "ok": False,
            "asset_path": None,
            "verified_widget_count": 0,
            "verified_widget_names": [],
            "errors": [
                {
                    "code": "widget_patch_failed",
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            ],
        }
        write_report(patch_path, report)
        unreal.log_error(json.dumps(report, indent=2))
        return 1


def apply_patch(patch: dict) -> dict:
    asset_path = patch["asset_path"]
    errors = []

    helper = getattr(unreal, "AccelByteUIToolsLibrary", None)
    if helper is None:
        return _report(
            False,
            asset_path,
            [],
            [{"code": "editor_helper_missing", "message": "unreal.AccelByteUIToolsLibrary is not exposed."}],
        )

    op = patch.get("op", "add_widget")
    if op == "set_widget_properties":
        widget_name = patch["widget_name"]
        properties = patch["properties"]
        result = helper.update_widget_properties_in_accelbyte_ui_from_json(
            asset_path,
            widget_name,
            json.dumps(properties),
        )
    else:
        parent_widget_name = patch["parent_widget_name"]
        widget = patch["widget"]
        result = helper.add_widget_to_accelbyte_ui_from_json(asset_path, parent_widget_name, json.dumps(widget))

    if isinstance(result, tuple):
        patched = bool(result[0])
        patch_error = result[1] if len(result) > 1 else None
    elif isinstance(result, str):
        patched = result == ""
        patch_error = result or None
    else:
        patched = bool(result)
        patch_error = None

    if not patched:
        return _report(
            False,
            asset_path,
            [],
            [
                {
                    "code": "widget_patch_failed",
                    "message": patch_error or "Patch failed.",
                    "raw_result": repr(result),
                }
            ],
        )

    if not unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False):
        errors.append({"code": "save_failed", "message": asset_path})

    verify_result = helper.read_accelbyte_ui_hierarchy(asset_path)
    if isinstance(verify_result, tuple):
        count = int(verify_result[0])
        names = list(verify_result[1]) if len(verify_result) > 1 and verify_result[1] is not None else []
        verify_error = verify_result[2] if len(verify_result) > 2 else None
    else:
        count = int(verify_result)
        names = []
        verify_error = None

    if verify_error:
        errors.append({"code": "widget_hierarchy_unverified", "message": verify_error})
    patched_widget_name = patch["widget_name"] if op == "set_widget_properties" else patch["widget"]["name"]
    if patched_widget_name not in names:
        errors.append(
            {
                "code": "widget_missing_after_patch",
                "message": f"{patched_widget_name} was not found in the patched hierarchy.",
                "verified_widget_names": names,
            }
        )

    report = {
        "ok": not errors,
        "asset_path": asset_path,
        "verified_widget_count": count,
        "verified_widget_names": names,
        "errors": errors,
    }
    if op == "set_widget_properties":
        report["updated_widget_names"] = [patched_widget_name]
    else:
        report["parent_widget_name"] = patch["parent_widget_name"]
        report["added_widget_name"] = patched_widget_name
    return report


def _report(ok: bool, asset_path: str, verified_widget_names: list[str], errors: list[dict]) -> dict:
    return {
        "ok": ok,
        "asset_path": asset_path,
        "verified_widget_count": len(verified_widget_names),
        "verified_widget_names": verified_widget_names,
        "errors": errors,
    }


def write_report(patch_path: Path, report: dict) -> None:
    output_dir = find_project_root(patch_path) / "Saved" / "AccelByteUITools"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{patch_path.stem}.report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def find_project_root(path: Path) -> Path:
    resolved = path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if any(parent.glob("*.uproject")):
            return parent
    return Path.cwd()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
