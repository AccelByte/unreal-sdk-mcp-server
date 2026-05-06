from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import defusedxml.ElementTree as ET
from defusedxml.common import DefusedXmlException

try:
    from .widget_spec import ValidationError, load_spec_file
except ImportError:
    from widget_spec import ValidationError, load_spec_file


DEFAULT_EDITOR_EXE = "E:/EpicGames/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"


def build_unreal_command(editor_exe: str, project: str, request: str | Path) -> list[str]:
    command = [
        editor_exe,
        str(Path(project).resolve()),
        "-run=WidgetBlueprintGenerator",
        f"-Request={Path(request).resolve()}",
        "-unattended",
        "-nop4",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    return command


def write_commandlet_request(project: str, spec: str, force: bool, output_dir: str | Path | None = None) -> Path:
    project_path = Path(project).resolve()
    project_root = project_path.parent
    request_dir = Path(output_dir) if output_dir is not None else project_root / "Saved" / "WidgetBlueprintGenerator"
    request_dir.mkdir(parents=True, exist_ok=True)
    spec_path = Path(spec).resolve()
    report_path = request_dir / f"{spec_path.stem}.report.json"
    request_path = request_dir / f"{spec_path.stem}.request.json"
    request_path.write_text(
        json.dumps(
            {
                "mode": "generate",
                "force": force,
                "spec": json.loads(spec_path.read_text(encoding="utf-8")),
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
    request_dir = Path(output_dir) if output_dir is not None else project_root / "Saved" / "WidgetBlueprintGenerator"
    request_dir.mkdir(parents=True, exist_ok=True)
    patch_path = Path(patch).resolve()
    patch_data = json.loads(patch_path.read_text(encoding="utf-8"))
    for field in ("asset_path", "parent_widget_name", "widget"):
        if field not in patch_data:
            raise ValidationError(field, f"Patch is missing required field: {field}")

    report_path = request_dir / f"{patch_path.stem}.report.json"
    request_path = request_dir / f"{patch_path.stem}.request.json"
    request_path.write_text(
        json.dumps(
            {
                "mode": "patch",
                "asset_path": patch_data["asset_path"],
                "parent_widget_name": patch_data["parent_widget_name"],
                "widget": patch_data["widget"],
                "report_path": str(report_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return request_path


def write_unreal_runner(spec: str, force: bool, output_dir: str | Path | None = None) -> Path:
    target_dir = Path(output_dir) if output_dir is not None else Path(tempfile.gettempdir()) / "WidgetBlueprintGenerator"
    target_dir.mkdir(parents=True, exist_ok=True)
    runner_path = target_dir / "run_widget_blueprint_generator.py"
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
                "import unreal_generate_widget_blueprint",
                f"raise SystemExit(unreal_generate_widget_blueprint.main({args!r}))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return runner_path


def write_startup_request(project: str, spec: str, force: bool, quit_editor: bool = True) -> Path:
    project_path = Path(project).resolve()
    project_root = project_path.parent
    request_dir = project_root / "Saved" / "WidgetBlueprintGenerator"
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
    report_path = project_root / "Saved" / "WidgetBlueprintGenerator" / f"{Path(spec).stem}.report.json"
    return wait_for_report(report_path, timeout_seconds), report_path


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and generate Unreal Widget Blueprints from JSON specs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a widget spec without launching Unreal.")
    validate_parser.add_argument("spec")

    generate_parser = subparsers.add_parser("generate", help="Validate a spec and launch Unreal headless.")
    generate_parser.add_argument("spec")
    generate_parser.add_argument("--project", default="AccelByteWars.uproject")
    generate_parser.add_argument("--editor-exe", default=DEFAULT_EDITOR_EXE)
    generate_parser.add_argument("--force", action="store_true")
    generate_parser.add_argument("--dry-run", action="store_true")

    patch_parser = subparsers.add_parser("patch", help="Patch an existing Widget Blueprint through the commandlet.")
    patch_parser.add_argument("patch")
    patch_parser.add_argument("--project", default="AccelByteWars.uproject")
    patch_parser.add_argument("--editor-exe", default=DEFAULT_EDITOR_EXE)
    patch_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "validate":
        try:
            spec = load_spec_file(args.spec)
        except ValidationError as error:
            print(json.dumps({"ok": False, "error": error.to_dict()}, indent=2))
            return 1
        print(json.dumps({"ok": True, "asset_path": spec.asset_path, "widget_count": spec.widget_count()}, indent=2))
        return 0

    if args.command == "generate":
        try:
            load_spec_file(args.spec)
        except ValidationError as error:
            print(json.dumps({"ok": False, "error": error.to_dict()}, indent=2))
            return 1
        request_path = write_commandlet_request(args.project, args.spec, args.force)
    else:
        try:
            request_path = write_patch_commandlet_request(args.project, args.patch)
        except (json.JSONDecodeError, ValidationError) as error:
            error_body = error.to_dict() if isinstance(error, ValidationError) else {"code": "invalid_json", "message": str(error)}
            print(json.dumps({"ok": False, "error": error_body}, indent=2))
            return 1

    command = build_unreal_command(args.editor_exe, args.project, request_path)
    if args.dry_run:
        print(json.dumps({"ok": True, "command": command}, indent=2))
        return 0

    report_path = report_path_from_request(request_path)
    report_path.unlink(missing_ok=True)

    crash_context_before = latest_crash_context(args.project)
    crash_mtime_before = crash_context_before.stat().st_mtime if crash_context_before else None

    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return completed.returncode

    if not wait_for_report(report_path):
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
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok", False) else 1


if __name__ == "__main__":
    sys.exit(main())
