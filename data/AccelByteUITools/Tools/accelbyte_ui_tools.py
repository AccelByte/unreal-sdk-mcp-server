from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any
import defusedxml.ElementTree as ET
from defusedxml.common import DefusedXmlException

try:
    from .ags_recipe_selector import select_ags_recipe
    from .project_style_context import (
        CORE_COMPONENT_ROLES,
        StyleContextError,
        approval_status,
        approve_style_context,
        discover_project_style,
        ensure_approved_style_context,
        extra_parent_classes_from_context,
        load_generated_components_registry,
        project_root_from_project,
        register_generated_component,
        register_generated_widget,
        style_findings,
        validate_spec_against_style_context,
        write_style_context,
    )
    from .theme_normalizer import normalize_theme_file
    from .widget_spec import ValidationError, canonicalize_spec, load_spec_file, load_spec_from_dict
except ImportError:
    from ags_recipe_selector import select_ags_recipe
    from project_style_context import (
        CORE_COMPONENT_ROLES,
        StyleContextError,
        approval_status,
        approve_style_context,
        discover_project_style,
        ensure_approved_style_context,
        extra_parent_classes_from_context,
        load_generated_components_registry,
        project_root_from_project,
        register_generated_component,
        register_generated_widget,
        style_findings,
        validate_spec_against_style_context,
        write_style_context,
    )
    from theme_normalizer import normalize_theme_file
    from widget_spec import ValidationError, canonicalize_spec, load_spec_file, load_spec_from_dict


DEFAULT_TIMEOUT_SECONDS = 300


def build_unreal_command(editor_exe: str, project: str, request: str | Path) -> list[str]:
    command = [
        editor_exe,
        str(Path(project).resolve()),
        "-run=AccelByteUITools",
        f"-Request={Path(request).resolve()}",
        "-unattended",
        "-nop4",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    return command


def resolve_editor_exe(editor_exe: str | None) -> str | None:
    return editor_exe or os.environ.get("UNREAL_EDITOR_EXE")


def editor_exe_missing_error() -> dict[str, object]:
    return {
        "ok": False,
        "error": {
            "code": "editor_exe_missing",
            "message": "Pass --editor-exe or set UNREAL_EDITOR_EXE to the full path of UnrealEditor-Cmd.exe.",
        },
    }


def write_commandlet_request(
    project: str,
    spec: str,
    force: bool,
    output_dir: str | Path | None = None,
    spec_data: dict[str, object] | None = None,
) -> Path:
    project_path = Path(project).resolve()
    project_root = project_path.parent
    request_dir = Path(output_dir) if output_dir is not None else project_root / "Saved" / "AccelByteUITools"
    request_dir.mkdir(parents=True, exist_ok=True)
    spec_path = Path(spec).resolve()
    report_path = request_dir / f"{spec_path.stem}.report.json"
    request_path = request_dir / f"{spec_path.stem}.request.json"
    normalized_spec = spec_data if spec_data is not None else canonicalize_spec(normalize_theme_file(spec_path))
    request_path.write_text(
        json.dumps(
            {
                "mode": "generate",
                "force": force,
                "spec": normalized_spec,
                "report_path": str(report_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return request_path


def write_patch_commandlet_request(project: str, patch: str, output_dir: str | Path | None = None) -> Path:
    project_path = Path(project).resolve()
    project_root = project_path.parent
    request_dir = Path(output_dir) if output_dir is not None else project_root / "Saved" / "AccelByteUITools"
    request_dir.mkdir(parents=True, exist_ok=True)
    patch_path = Path(patch).resolve()
    patch_data = json.loads(patch_path.read_text(encoding="utf-8"))
    if patch_data.get("op") == "set_widget_properties":
        for field in ("asset_path", "widget_name", "properties"):
            if field not in patch_data:
                raise ValidationError(field, f"Patch is missing required field: {field}")
    else:
        for field in ("asset_path", "parent_widget_name", "widget"):
            if field not in patch_data:
                raise ValidationError(field, f"Patch is missing required field: {field}")

    report_path = request_dir / f"{patch_path.stem}.report.json"
    request_path = request_dir / f"{patch_path.stem}.request.json"
    request = {
        "mode": "patch",
        "asset_path": patch_data["asset_path"],
        "report_path": str(report_path),
    }
    if patch_data.get("op") == "set_widget_properties":
        request["op"] = "set_widget_properties"
        request["widget_name"] = patch_data["widget_name"]
        request["properties"] = patch_data["properties"]
    else:
        request["parent_widget_name"] = patch_data["parent_widget_name"]
        request["widget"] = patch_data["widget"]
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    return request_path


def write_unreal_runner(spec: str, force: bool, output_dir: str | Path | None = None) -> Path:
    target_dir = Path(output_dir) if output_dir is not None else Path(tempfile.gettempdir()) / "AccelByteUITools"
    target_dir.mkdir(parents=True, exist_ok=True)
    runner_path = target_dir / "run_accelbyte_ui_tools.py"
    script_dir = Path(__file__).resolve().parent
    args = ["--spec", str(Path(spec).resolve())]
    if force:
        args.append("--force")
    runner_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                f"sys.path.insert(0, {str(script_dir)!r})",
                "import unreal_generate_accelbyte_ui",
                f"raise SystemExit(unreal_generate_accelbyte_ui.main({args!r}))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return runner_path


def write_startup_request(project: str, spec: str, force: bool, quit_editor: bool = True) -> Path:
    project_path = Path(project).resolve()
    project_root = project_path.parent
    request_dir = project_root / "Saved" / "AccelByteUITools"
    request_dir.mkdir(parents=True, exist_ok=True)
    request_path = request_dir / "run_request.json"
    request_path.write_text(
        json.dumps(
            {
                "spec": str(Path(spec).resolve()),
                "force": force,
                "quit_editor": quit_editor,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return request_path


def report_path_from_request(request_path: str | Path) -> Path:
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    return Path(request["report_path"])


def wait_for_report(report_path: str | Path, timeout_seconds: int = 5) -> bool:
    report = Path(report_path)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if report.exists():
            return True
        time.sleep(1)
    return False


def wait_for_generation_report(project: str, spec: str, timeout_seconds: int = 180) -> tuple[bool, Path]:
    project_root = Path(project).resolve().parent
    report_path = project_root / "Saved" / "AccelByteUITools" / f"{Path(spec).stem}.report.json"
    return wait_for_report(report_path, timeout_seconds), report_path


def print_style_context_report(context: dict[str, object], project: str, *, approved: bool = False) -> None:
    status = approval_status(context, project)
    print(
        json.dumps(
            {
                "ok": True,
                "style_context_path": str(write_style_context(context, project).resolve()),
                "approved": approved or status["approved"],
                "approval_reasons": [] if approved else status["reasons"],
                "findings": style_findings(context),
            },
            indent=2,
        )
    )


def load_approved_style_context_for_generation(project: str, *, approve: bool = False) -> dict[str, object]:
    context = discover_project_style(project)
    write_style_context(context, project)
    if approve:
        approve_style_context(context, project)
        return context
    status = approval_status(context, project)
    if not status["approved"]:
        raise StyleContextError(
            "style_context_approval_required",
            "Project style context must be reviewed and approved before generation.",
            {"approval_reasons": status["reasons"], "findings": style_findings(context)},
        )
    return context


def validate_with_style_context(spec: dict[str, object], context: dict[str, object]) -> None:
    style_errors = validate_spec_against_style_context(spec, context)
    if style_errors:
        raise StyleContextError(
            "style_context_validation_failed",
            "Widget spec does not match the approved project style context.",
            {"errors": style_errors},
        )


def prepare_spec_for_generation(spec_path: str, style_context: dict[str, object] | None = None, *, output_path: str | None = None) -> dict[str, object]:
    normalized = normalize_theme_file(spec_path, style_context=style_context)
    if style_context is not None:
        # Run style-context normalization before schema canonicalization. Some valid
        # project-style specs are intentionally corrected here, such as generated
        # collection entries accidentally authored with ui_mode=common_ui.
        validate_with_style_context(normalized, style_context)
    canonical_kwargs: dict[str, object] = {}
    if style_context is not None:
        project_class_mapping = style_context.get("project_class_mapping")
        if isinstance(project_class_mapping, dict) and project_class_mapping:
            canonical_kwargs["project_class_mapping"] = project_class_mapping
        extra_parent_classes = extra_parent_classes_from_context(style_context)
        if extra_parent_classes:
            canonical_kwargs["extra_parent_classes"] = extra_parent_classes
    canonical = canonicalize_spec(normalized, **canonical_kwargs)
    if style_context is not None:
        validate_with_style_context(canonical, style_context)
    if output_path:
        normalized_path = Path(output_path).resolve()
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_text(json.dumps(canonical, indent=2), encoding="utf-8")
    return canonical


def latest_crash_context(project: str) -> Path | None:
    crash_root = Path(project).resolve().parent / "Saved" / "Crashes"
    if not crash_root.exists():
        return None

    contexts = list(crash_root.rglob("CrashContext.runtime-xml"))
    if not contexts:
        return None

    return max(contexts, key=lambda item: item.stat().st_mtime)


def read_crash_error(context_path: Path) -> str | None:
    try:
        root = ET.parse(context_path).getroot()
    except (ET.ParseError, DefusedXmlException):
        return None

    error = root.findtext(".//ErrorMessage")
    return error.strip() if error else None


BRIDGE_DEFAULT_URL = "http://127.0.0.1:48757"
CORE_TEMPLATES_DIR = Path(__file__).parent / "specs" / "core_templates"
_STATE_ROLES = {"state_loading", "state_empty", "state_error", "state_idle"}


def _bridge_generate_sync(spec: dict, force: bool = False, bridge_url: str = BRIDGE_DEFAULT_URL) -> dict:
    payload = json.dumps({"force": force, "spec": spec}).encode("utf-8")
    req = urllib.request.Request(
        f"{bridge_url.rstrip('/')}/accelbyte-ui-tools/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _inject_styles(spec: dict, enforced_roles: dict) -> dict:
    spec = json.loads(json.dumps(spec))

    def _role_candidates(role: str, *, kind: str | None = None) -> list[dict]:
        candidates = list(enforced_roles.get(role, {}).get("project_candidates", []))
        if kind is None:
            return candidates
        return [item for item in candidates if item.get("kind") == kind]

    def _all_button_widget_candidates() -> list[dict]:
        seen: set[str] = set()
        result: list[dict] = []
        for role in ("primary_button", "secondary_button", "danger_button", "tab_button"):
            for item in _role_candidates(role, kind="widget"):
                ref = item.get("class_path") or item.get("asset_path")
                if isinstance(ref, str) and ref not in seen:
                    result.append(item)
                    seen.add(ref)
        return result

    def _inject_node(node: dict) -> None:
        inject_role = node.pop("__style_inject", None)
        if inject_role:
            role_candidates = _role_candidates(inject_role)
            if not role_candidates and inject_role in {"title_text", "warning_text"}:
                role_candidates = _role_candidates("body_text")
            if role_candidates:
                widget_type = str(node.get("type", ""))
                widget_candidate = next((item for item in role_candidates if item.get("kind") == "widget"), None)
                if widget_candidate is None and _is_button_template_node(widget_type):
                    widget_candidate = next(iter(_all_button_widget_candidates()), None)
                style_candidate = next((item for item in role_candidates if item.get("kind") == "style"), None)
                if widget_candidate and _is_button_template_node(widget_type):
                    node["class_path"] = widget_candidate["class_path"]
                if style_candidate:
                    if _can_apply_button_style_to_template_node(widget_type, node.get("class_path")):
                        node["button_style_class"] = style_candidate["class_path"]
                    elif not _is_button_template_node(widget_type):
                        node["text_style_class"] = style_candidate["class_path"]
        for child in node.get("children", []):
            if isinstance(child, dict):
                _inject_node(child)

    root = spec.get("root")
    if isinstance(root, dict):
        _inject_node(root)
    return spec


def _is_button_template_node(widget_type: str) -> bool:
    return "button" in widget_type.casefold() or widget_type in {
        "AGSBaseButton", "AGSButton", "AGSSecondaryButton", "AGSDangerButton"
    }


def _can_apply_button_style_to_template_node(widget_type: str, class_path: Any = None) -> bool:
    if widget_type in {"AGSBaseButton", "AGSButton", "AGSSecondaryButton", "AGSDangerButton"} and not _is_project_class_path(class_path):
        return False
    return "button" in widget_type.casefold() or widget_type == "Button"


def _is_project_class_path(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("/Game/")


def _bridge_result_asset_already_exists(result: dict) -> bool:
    values = [result.get("message"), result.get("error")]
    errors = result.get("errors", [])
    if isinstance(errors, list):
        values.extend(errors)
    for value in values:
        if isinstance(value, dict):
            value = " ".join(str(value.get(key, "")) for key in ("code", "message", "detail"))
        text = str(value).casefold()
        if "asset already exists" in text or ("already exists" in text and "asset" in text):
            return True
    return False


def _strip_template_directives(spec: dict) -> dict:
    spec = json.loads(json.dumps(spec))

    def _strip_node(node: dict) -> None:
        node.pop("_comment", None)
        node.pop("_core_role", None)
        node.pop("core_role", None)
        node.pop("__style_inject", None)
        for child in node.get("children", []):
            if isinstance(child, dict):
                _strip_node(child)

    spec.pop("_comment", None)
    spec.pop("_core_role", None)
    spec.pop("core_role", None)
    root = spec.get("root")
    if isinstance(root, dict):
        _strip_node(root)
    return spec


def cmd_generate_core_widgets(
    project: str,
    roles: list[str] | None = None,
    all_roles: bool = False,
    force: bool = False,
    bridge_url: str = BRIDGE_DEFAULT_URL,
) -> dict:
    project_root = project_root_from_project(project)
    registry = load_generated_components_registry(project_root)

    try:
        context = ensure_approved_style_context(project_root)
    except StyleContextError as exc:
        return {"ok": False, "error": exc.to_dict()}

    enforced_roles = context.get("enforced_roles", {})

    def _refresh_approved_style_context() -> str | None:
        refreshed = discover_project_style(project_root)
        write_style_context(refreshed, project_root)
        approve_style_context(refreshed, project_root)
        return refreshed.get("fingerprint") if isinstance(refreshed, dict) else None

    if all_roles:
        target_roles = list(CORE_COMPONENT_ROLES.keys())
    elif roles:
        target_roles = roles
    else:
        target_roles = list(_STATE_ROLES)

    results = []
    for role in target_roles:
        info = CORE_COMPONENT_ROLES.get(role)
        if not info:
            results.append({"role": role, "status": "unknown_role"})
            continue

        if role in registry and not force:
            results.append({"role": role, "status": "already_generated", "asset_path": registry[role]["asset_path"]})
            continue

        template_name = info.get("template")
        if not template_name:
            results.append({"role": role, "status": "no_template", "message": f"No template defined for role '{role}'; generate manually."})
            continue

        template_path = CORE_TEMPLATES_DIR / f"{template_name}.json"
        if not template_path.exists():
            results.append({"role": role, "status": "template_missing", "message": str(template_path)})
            continue

        spec_out_dir = project_root / "Content" / "AGS" / "UI" / "Generated" / "Specs" / "Components"
        spec_out_dir.mkdir(parents=True, exist_ok=True)
        asset_name = info["generated_asset_name"]
        spec_path = spec_out_dir / f"{asset_name}.json"

        raw_spec = json.loads(template_path.read_text(encoding="utf-8"))
        injected_spec = _inject_styles(raw_spec, enforced_roles)
        spec_path.write_text(json.dumps(injected_spec, indent=2), encoding="utf-8")
        try:
            spec = prepare_spec_for_generation(str(spec_path), context, output_path=str(spec_path))
            spec = _strip_template_directives(spec)
            spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        except StyleContextError as exc:
            results.append({"role": role, "status": "style_validation_failed", "error": exc.to_dict()})
            continue
        except ValidationError as exc:
            results.append({"role": role, "status": "style_validation_failed", "error": exc.to_dict()})
            continue

        try:
            bridge_result = _bridge_generate_sync(spec, force=force, bridge_url=bridge_url)
            retried_with_force = False
            if not bridge_result.get("ok") and not force and _bridge_result_asset_already_exists(bridge_result):
                bridge_result = _bridge_generate_sync(spec, force=True, bridge_url=bridge_url)
                retried_with_force = True
        except urllib.error.URLError as exc:
            results.append({"role": role, "status": "bridge_unavailable", "spec_path": str(spec_path), "message": str(exc)})
            continue
        except Exception as exc:
            results.append({"role": role, "status": "bridge_error", "spec_path": str(spec_path), "message": str(exc)})
            continue

        if bridge_result.get("ok"):
            asset_path = spec.get("asset_path", "")
            register_generated_component(project_root, role, asset_path, str(spec_path))
            item = {"role": role, "status": "generated", "asset_path": asset_path, "spec_path": str(spec_path)}
            if retried_with_force:
                item["force_retry"] = True
            results.append(item)
        else:
            item = {"role": role, "status": "bridge_rejected", "spec_path": str(spec_path), "bridge_result": bridge_result}
            if retried_with_force:
                item["force_retry"] = True
            results.append(item)

    failed_statuses = {
        "unknown_role",
        "template_missing",
        "style_validation_failed",
        "bridge_unavailable",
        "bridge_error",
        "bridge_rejected",
    }
    ok = not any(result.get("status") in failed_statuses for result in results)
    response: dict[str, object] = {"ok": ok, "results": results}
    if any(result.get("status") in {"generated", "already_generated"} for result in results):
        try:
            fingerprint = _refresh_approved_style_context()
            response["style_context_refreshed"] = True
            if fingerprint:
                response["style_context_fingerprint"] = fingerprint
        except Exception as exc:
            response["style_context_refreshed"] = False
            response["warnings"] = [
                {
                    "code": "style_context_refresh_failed",
                    "message": (
                        "Generated project core widget registry was updated, but the approved style context "
                        f"could not be refreshed automatically: {exc}"
                    ),
                }
            ]
    if not ok:
        response["errors"] = [
            {
                "code": "core_widget_generation_failed",
                "message": "One or more requested project core widgets failed to generate.",
                "failed_roles": [
                    result.get("role")
                    for result in results
                    if result.get("status") in failed_statuses
                ],
            }
        ]
    return response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and generate Unreal Widget Blueprints from JSON specs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a widget spec without launching Unreal.")
    validate_parser.add_argument("spec")
    validate_parser.add_argument("--project")
    validate_parser.add_argument("--write-normalized-spec")

    select_parser = subparsers.add_parser("select-ags-recipe", help="Select a fallback AGS UI recipe for a request.")
    select_parser.add_argument("request")

    style_discover_parser = subparsers.add_parser("style-discover", help="Discover project UI style context before generation.")
    style_discover_parser.add_argument("--project", required=True)
    style_discover_parser.add_argument("--approve", action="store_true")

    generate_parser = subparsers.add_parser("generate", help="Validate a spec and launch Unreal headless or POST to the bridge.")
    generate_parser.add_argument("spec")
    generate_parser.add_argument("--project", default="AccelByteWars.uproject")
    generate_parser.add_argument("--editor-exe", default=None, help="Path to UnrealEditor-Cmd.exe (required unless --bridge-url is given)")
    generate_parser.add_argument("--bridge-url", default=None, help="If given, POST to this bridge URL instead of running a commandlet")
    generate_parser.add_argument("--force", action="store_true")
    generate_parser.add_argument("--dry-run", action="store_true")
    generate_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    generate_parser.add_argument("--write-normalized-spec")
    generate_parser.add_argument("--approve-style-context", action="store_true")

    patch_parser = subparsers.add_parser("patch", help="Patch an existing Widget Blueprint through the commandlet.")
    patch_parser.add_argument("patch")
    patch_parser.add_argument("--project", default="AccelByteWars.uproject")
    patch_parser.add_argument("--editor-exe")
    patch_parser.add_argument("--dry-run", action="store_true")
    patch_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    patch_parser.add_argument("--approve-style-context", action="store_true")

    gcw_parser = subparsers.add_parser(
        "generate-core-widgets",
        help="Generate project-style blueprint replacements for AGSUI/Core atoms that have no project equivalent.",
    )
    gcw_parser.add_argument("--project", required=True)
    gcw_parser.add_argument(
        "--roles",
        help="Comma-separated list of core roles to generate (default: state_loading,state_empty,state_error,state_idle).",
    )
    gcw_parser.add_argument("--all", dest="all_roles", action="store_true", help="Generate for all roles with a template.")
    gcw_parser.add_argument("--force", action="store_true", help="Re-generate even if already generated.")
    gcw_parser.add_argument("--bridge-url", default=BRIDGE_DEFAULT_URL)

    args = parser.parse_args(argv)

    if args.command == "select-ags-recipe":
        print(json.dumps(select_ags_recipe(args.request).__dict__, indent=2))
        return 0

    if args.command == "generate-core-widgets":
        roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
        result = cmd_generate_core_widgets(
            project=args.project,
            roles=roles,
            all_roles=args.all_roles,
            force=args.force,
            bridge_url=args.bridge_url,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.command == "style-discover":
        context = discover_project_style(args.project)
        write_style_context(context, args.project)
        approved = False
        if args.approve:
            approve_style_context(context, args.project)
            approved = True
        print_style_context_report(context, args.project, approved=approved)
        return 0

    if args.command == "validate":
        try:
            style_context = load_approved_style_context_for_generation(args.project) if args.project else None
            normalized = prepare_spec_for_generation(args.spec, style_context, output_path=args.write_normalized_spec)
            extra = extra_parent_classes_from_context(style_context) if style_context else None
            project_class_mapping = style_context.get("project_class_mapping") if style_context else None
            spec = load_spec_from_dict(
                normalized,
                extra_parent_classes=extra,
                project_class_mapping=project_class_mapping if isinstance(project_class_mapping, dict) else None,
            )
        except ValidationError as error:
            print(json.dumps({"ok": False, "error": error.to_dict()}, indent=2))
            return 1
        except StyleContextError as error:
            print(json.dumps({"ok": False, "error": error.to_dict()}, indent=2))
            return 1
        result = {
            "ok": True,
            "asset_path": spec.asset_path,
            "widget_count": spec.widget_count(),
            "variable_widget_names": spec.variable_widget_names(),
            "bindings": [binding.to_dict() for binding in spec.bindings()],
        }
        if args.write_normalized_spec:
            result["normalized_spec_path"] = str(Path(args.write_normalized_spec).resolve())
        print(json.dumps(result, indent=2))
        return 0

    generated_spec_data: dict[str, object] | None = None
    generated_spec_path_for_registry: str | None = None
    if args.command == "generate":
        try:
            style_context = load_approved_style_context_for_generation(args.project, approve=args.approve_style_context)
            normalized = prepare_spec_for_generation(args.spec, style_context, output_path=args.write_normalized_spec)
            generated_spec_data = normalized
            generated_spec_path_for_registry = args.write_normalized_spec or args.spec
            extra = extra_parent_classes_from_context(style_context) if style_context else None
            project_class_mapping = style_context.get("project_class_mapping") if style_context else None
            load_spec_from_dict(
                normalized,
                extra_parent_classes=extra,
                project_class_mapping=project_class_mapping if isinstance(project_class_mapping, dict) else None,
            )
        except ValidationError as error:
            print(json.dumps({"ok": False, "error": error.to_dict()}, indent=2))
            return 1
        except StyleContextError as error:
            print(json.dumps({"ok": False, "error": error.to_dict()}, indent=2))
            return 1
        if args.bridge_url:
            try:
                result = _bridge_generate_sync(normalized, force=args.force, bridge_url=args.bridge_url)
            except Exception as exc:  # noqa: BLE001
                print(json.dumps({"ok": False, "error": {"code": "bridge_error", "message": str(exc)}}, indent=2))
                return 1
            print(json.dumps(result, indent=2))
            return 0 if result.get("ok") else 1
        if not resolve_editor_exe(args.editor_exe):
            print(json.dumps(editor_exe_missing_error(), indent=2))
            return 1
        request_path = write_commandlet_request(args.project, args.spec, args.force, spec_data=normalized)
    else:
        try:
            style_context = load_approved_style_context_for_generation(args.project, approve=args.approve_style_context)
            patch_data = json.loads(Path(args.patch).read_text(encoding="utf-8"))
            if isinstance(patch_data, dict) and isinstance(patch_data.get("widget"), dict):
                validate_with_style_context({"asset_path": patch_data.get("asset_path"), "root": patch_data["widget"]}, style_context)
            request_path = write_patch_commandlet_request(args.project, args.patch)
        except (json.JSONDecodeError, ValidationError) as error:
            error_body = error.to_dict() if isinstance(error, ValidationError) else {"code": "invalid_json", "message": str(error)}
            print(json.dumps({"ok": False, "error": error_body}, indent=2))
            return 1
        except StyleContextError as error:
            print(json.dumps({"ok": False, "error": error.to_dict()}, indent=2))
            return 1

    editor_exe = resolve_editor_exe(args.editor_exe)
    if not editor_exe:
        print(json.dumps(editor_exe_missing_error(), indent=2))
        return 1

    command = build_unreal_command(editor_exe, args.project, request_path)
    if args.dry_run:
        print(json.dumps({"ok": True, "command": command}, indent=2))
        return 0

    report_path = report_path_from_request(request_path)
    report_path.unlink(missing_ok=True)

    crash_context_before = latest_crash_context(args.project)
    crash_mtime_before = crash_context_before.stat().st_mtime if crash_context_before else None

    completed = subprocess.run(command, check=False)
    if completed.returncode != 0 and not report_path.exists():
        return completed.returncode

    if not wait_for_report(report_path, args.timeout):
        crash_context_after = latest_crash_context(args.project)
        crash_error = None
        if crash_context_after is not None:
            crash_mtime_after = crash_context_after.stat().st_mtime
            if crash_context_after != crash_context_before or crash_mtime_before is None or crash_mtime_after > crash_mtime_before:
                crash_error = read_crash_error(crash_context_after)

        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "unreal_generation_failed",
                        "message": f"Unreal exited 0 but did not create report: {report_path}",
                        "crash": crash_error,
                    },
                },
                indent=2,
            )
        )
        return 1

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if args.command == "generate" and report.get("ok", False) and isinstance(generated_spec_data, dict):
        register_generated_widget(
            args.project,
            str(generated_spec_data.get("asset_path") or ""),
            str(generated_spec_path_for_registry or args.spec),
        )
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok", False) else 1


if __name__ == "__main__":
    sys.exit(main())
