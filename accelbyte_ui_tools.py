from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import httpx

from _unreal_common import (
    DEFAULT_BRIDGE_URL,
    bridge_url as _bridge_url,
    project_file as _project_file,
    resolve_project_root,
)

WIDGET_SPEC_RUNTIME_MODULE_PREFIX = "widget_spec_runtime_"
UPROPERTY_BINDING_PATTERN = re.compile(
    r"UPROPERTY\s*\((?P<meta>.*?)\)\s*"
    r"(?:(?:class|struct)\s+)?"
    r"(?P<type>"
    r"TObjectPtr\s*<\s*(?:(?:class|struct)\s+)?[A-Za-z_][A-Za-z0-9_:]*\s*>"
    r"|[A-Za-z_][A-Za-z0-9_:]*"
    r")"
    r"\s*(?:\*\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.DOTALL,
)
TOBJECTPTR_PATTERN = re.compile(
    r"^TObjectPtr\s*<\s*(?:(?:class|struct)\s+)?(?P<type>[A-Za-z_][A-Za-z0-9_:]*)\s*>$"
)
HEADER_CLASS_PATTERN = re.compile(
    r"class\s+(?:[A-Za-z_][A-Za-z0-9_]*_API\s+)?(?P<name>U[A-Za-z_][A-Za-z0-9_]*)\s*:\s*public\s+(?P<base>[A-Za-z_][A-Za-z0-9_]*)"
)


def ensure_path_inside(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()

    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Path is outside project root: {candidate_resolved}") from exc

    return candidate_resolved


def _resolve_project_file_path(project_root: Path, path_value: str) -> Path:
    raw_path = Path(path_value)
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    return ensure_path_inside(project_root, candidate)


def _load_json_file(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return loaded


def _module_name_for_source(project_root: Path, path: Path) -> str:
    try:
        rel_parts = path.resolve().relative_to(project_root.resolve()).parts
    except ValueError:
        rel_parts = path.parts
    if len(rel_parts) >= 2 and rel_parts[0] == "Source":
        return rel_parts[1]
    return "Project"


def _script_class_path_variants(module_name: str, class_name: str) -> set[str]:
    variants = {f"/Script/{module_name}.{class_name}"}
    if class_name.startswith("U") and len(class_name) > 1 and class_name[1].isupper():
        variants.add(f"/Script/{module_name}.{class_name[1:]}")
    return variants


def _declared_source_classes_from_header(project_root: Path, header_path: Path) -> list[dict[str, str]]:
    header_text = header_path.read_text(encoding="utf-8", errors="ignore")
    module_name = _module_name_for_source(project_root, header_path)
    try:
        source = header_path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        source = header_path.as_posix()
    return [
        {
            "name": match.group("name"),
            "base": match.group("base"),
            "module": module_name,
            "source": source,
        }
        for match in HEADER_CLASS_PATTERN.finditer(header_text)
    ]


def _header_declared_parent_paths(project_root: Path, header_path: Path) -> set[str]:
    paths: set[str] = set()
    for entry in _declared_source_classes_from_header(project_root, header_path):
        paths.update(_script_class_path_variants(entry["module"], entry["name"]))
    return paths


def _is_parent_class_declared_by_header(project_root: Path, header_path: Path, parent_class: str) -> bool:
    declared_paths = _header_declared_parent_paths(project_root, header_path)
    return not declared_paths or parent_class in declared_paths


def _final_parent_required_error(project_root: Path, spec_data: dict[str, Any], header_path: Path) -> dict[str, str]:
    parent_class = str(spec_data.get("parent_class") or "")
    declared = sorted(_header_declared_parent_paths(project_root, header_path))
    recommended = declared[0] if declared else "<the UCLASS declared by the backing header>"
    return {
        "code": "final_parent_required",
        "message": (
            f"Spec parent_class is '{parent_class}', but the backing header declares {', '.join(declared) or 'no UCLASS'}. "
            f"Set parent_class to the final script-backed class, usually '{recommended}', before verification. "
            "Do not temporarily switch to AGSCommonActivatableBase, CommonActivatableWidget, UUserWidget, "
            "AccelByteWarsWidgetEntry, or another fallback parent to extract bindings."
        ),
    }


def _augment_style_context_with_provisional_parent(
    context: dict[str, Any],
    project_root: Path,
    header_path: Path | None,
    parent_class: str,
) -> dict[str, Any]:
    if header_path is None or not parent_class:
        return context

    source_entries = _declared_source_classes_from_header(project_root, header_path)
    matching_entries = [
        entry for entry in source_entries if parent_class in _script_class_path_variants(entry["module"], entry["name"])
    ]
    if not matching_entries:
        return context

    augmented = json.loads(json.dumps(context))
    source_classes = augmented.setdefault("source_classes", {})
    existing_common_names = {
        entry.get("name", "")
        for entry in source_classes.get("common_activatable", [])
    }
    existing_entry_names = {
        entry.get("name", "")
        for entry in source_classes.get("list_entry_compatible", [])
    }

    def add_role(role: str, entry: dict[str, str]) -> None:
        values = source_classes.setdefault(role, [])
        key = (entry.get("name"), entry.get("module"))
        if not any((item.get("name"), item.get("module")) == key for item in values):
            values.append({k: v for k, v in entry.items() if k in {"name", "module", "source"}})

    for entry in matching_entries:
        base = entry.get("base", "")
        if base in {"UCommonActivatableWidget", "UAGSCommonActivatableBase"} or base in existing_common_names:
            add_role("common_activatable", entry)
        if base in {"UUserWidget", "UCommonUserWidget"}:
            add_role("user_widget", entry)
        if base in existing_entry_names:
            add_role("list_entry_compatible", entry)

    header_text = header_path.read_text(encoding="utf-8", errors="ignore")
    if "IUserObjectListEntry" in header_text or "UUserObjectListEntry" in header_text:
        for entry in matching_entries:
            add_role("list_entry_compatible", entry)

    allowed = set(augmented.get("allowed_class_references", []))
    for entry in matching_entries:
        allowed.update(_script_class_path_variants(entry["module"], entry["name"]))
    augmented["allowed_class_references"] = sorted(allowed)
    return augmented


def _project_cli_path(project_root: Path) -> Path:
    cli_path = (
        project_root
        / "Plugins"
        / "AccelByteUITools"
        / "Tools"
        / "accelbyte_ui_tools.py"
    )
    if not cli_path.exists():
        raise ValueError(f"Project AccelByteUITools CLI not found: {cli_path}")
    return cli_path


def _normalize_cli_result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if stdout:
        try:
            loaded = json.loads(stdout)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass

    return {
        "ok": False,
        "errors": [
            {
                "code": "cli_failed",
                "message": stderr or stdout or f"CLI exited {completed.returncode}",
            }
        ],
    }


async def _post_bridge(
    url: str,
    route: str,
    payload: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if client is None:
        async with httpx.AsyncClient(timeout=60.0) as owned_client:
            return await _post_bridge(url, route, payload, client=owned_client)
    response = await client.post(f"{url}{route}", json=payload)
    response.raise_for_status()
    loaded = response.json()
    if not isinstance(loaded, dict):
        raise ValueError("Bridge response must be a JSON object")
    return loaded


def _run_cli_generate(
    project_root: Path, spec_path: Path, force: bool, editor_exe: str | None
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(_project_cli_path(project_root)),
        "generate",
        str(spec_path),
        "--project",
        str(_project_file(project_root)),
        "--timeout",
        "60",
    ]
    if force:
        command.append("--force")
    if editor_exe:
        command.extend(["--editor-exe", editor_exe])

    completed = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return _normalize_cli_result(completed)


def _run_cli_patch(project_root: Path, patch_path: Path, editor_exe: str | None) -> dict[str, Any]:
    command = [
        sys.executable,
        str(_project_cli_path(project_root)),
        "patch",
        str(patch_path),
        "--project",
        str(_project_file(project_root)),
        "--timeout",
        "60",
    ]
    if editor_exe:
        command.extend(["--editor-exe", editor_exe])

    completed = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return _normalize_cli_result(completed)


def _load_widget_spec_module(project_root: Path):
    tool_path = project_root / "Plugins" / "AccelByteUITools" / "Tools" / "widget_spec.py"
    if not tool_path.exists():
        tool_path = Path(__file__).parent / "data" / "AccelByteUITools" / "Tools" / "widget_spec.py"
    if not tool_path.exists():
        raise ValueError("AccelByteUITools widget_spec.py could not be found")

    tool_path = tool_path.resolve()
    path_hash = hashlib.sha256(str(tool_path).encode("utf-8")).hexdigest()[:16]
    module_name = f"{WIDGET_SPEC_RUNTIME_MODULE_PREFIX}{path_hash}"

    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load widget_spec.py from {tool_path}")

    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    tool_dir = str(tool_path.parent)
    inserted_tool_dir = False
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)
        inserted_tool_dir = True
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted_tool_dir:
            try:
                sys.path.remove(tool_dir)
            except ValueError:
                pass
        if previous_module is None:
            if sys.modules.get(module_name) is module:
                del sys.modules[module_name]
        else:
            sys.modules[module_name] = previous_module
    return module


def _load_theme_normalizer_module(project_root: Path):
    tool_path = project_root / "Plugins" / "AccelByteUITools" / "Tools" / "theme_normalizer.py"
    if not tool_path.exists():
        tool_path = Path(__file__).parent / "data" / "AccelByteUITools" / "Tools" / "theme_normalizer.py"
    if not tool_path.exists():
        return None

    tool_path = tool_path.resolve()
    path_hash = hashlib.sha256(str(tool_path).encode("utf-8")).hexdigest()[:16]
    module_name = f"theme_normalizer_runtime_{path_hash}"

    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load theme_normalizer.py from {tool_path}")

    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    tool_dir = str(tool_path.parent)
    inserted_tool_dir = False
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)
        inserted_tool_dir = True
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted_tool_dir:
            try:
                sys.path.remove(tool_dir)
            except ValueError:
                pass
        if previous_module is None:
            if sys.modules.get(module_name) is module:
                del sys.modules[module_name]
        else:
            sys.modules[module_name] = previous_module
    return module


def _load_project_style_context_module(project_root: Path):
    tool_path = project_root / "Plugins" / "AccelByteUITools" / "Tools" / "project_style_context.py"
    if not tool_path.exists():
        tool_path = Path(__file__).parent / "data" / "AccelByteUITools" / "Tools" / "project_style_context.py"
    if not tool_path.exists():
        return None

    tool_path = tool_path.resolve()
    path_hash = hashlib.sha256(str(tool_path).encode("utf-8")).hexdigest()[:16]
    module_name = f"project_style_context_runtime_{path_hash}"

    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load project_style_context.py from {tool_path}")

    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    tool_dir = str(tool_path.parent)
    inserted_tool_dir = False
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)
        inserted_tool_dir = True
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted_tool_dir:
            try:
                sys.path.remove(tool_dir)
            except ValueError:
                pass
        if previous_module is None:
            if sys.modules.get(module_name) is module:
                del sys.modules[module_name]
        else:
            sys.modules[module_name] = previous_module
    return module


def _normalize_spec_data(
    project_root: Path,
    spec_data: dict[str, Any],
    style_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    theme_normalizer = _load_theme_normalizer_module(project_root)
    if theme_normalizer is None:
        return spec_data
    if style_context is None:
        project_style_context = _load_project_style_context_module(project_root)
        if project_style_context is not None:
            try:
                style_context = project_style_context.ensure_approved_style_context(project_root)
            except Exception:
                style_context = None
    return theme_normalizer.normalize_theme(spec_data, style_context=style_context)


def _get_project_class_mapping(project_root: Path) -> dict[str, str]:
    """Load the project class mapping from the approved style context (if available)."""
    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None:
        return {}
    try:
        context = project_style_context.ensure_approved_style_context(project_root)
        return context.get("project_class_mapping") or {}
    except Exception:
        return {}


def _get_extra_parent_classes(project_root: Path) -> frozenset[str]:
    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None or not hasattr(project_style_context, "extra_parent_classes_from_context"):
        return frozenset()
    try:
        context = project_style_context.ensure_approved_style_context(project_root)
        return project_style_context.extra_parent_classes_from_context(context)
    except Exception:
        return frozenset()


def _canonicalize_spec_data(
    project_root: Path,
    spec_data: dict[str, Any],
    project_class_mapping: dict[str, str] | None = None,
    extra_parent_classes: frozenset[str] | None = None,
) -> dict[str, Any]:
    widget_spec = _load_widget_spec_module(project_root)
    if hasattr(widget_spec, "canonicalize_spec"):
        kwargs: dict[str, Any] = {}
        if project_class_mapping is not None:
            kwargs["project_class_mapping"] = project_class_mapping
        if extra_parent_classes:
            kwargs["extra_parent_classes"] = extra_parent_classes
        return widget_spec.canonicalize_spec(spec_data, **kwargs)
    if hasattr(widget_spec, "load_spec_from_dict"):
        kwargs = {}
        if project_class_mapping is not None:
            kwargs["project_class_mapping"] = project_class_mapping
        if extra_parent_classes:
            kwargs["extra_parent_classes"] = extra_parent_classes
        spec = widget_spec.load_spec_from_dict(spec_data, **kwargs)
        if hasattr(spec, "to_dict"):
            return spec.to_dict()
    return spec_data


def _auto_approve_style_context(project_root: Path) -> None:
    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None:
        return
    if not hasattr(project_style_context, "discover_project_style"):
        return
    context = project_style_context.discover_project_style(project_root)
    if hasattr(project_style_context, "write_style_context"):
        project_style_context.write_style_context(context, project_root)
    if hasattr(project_style_context, "approve_style_context"):
        project_style_context.approve_style_context(context, project_root)


def _style_context_validation_result(project_root: Path, spec_data: dict[str, Any]) -> list[dict[str, Any]]:
    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None:
        return []
    try:
        context = project_style_context.ensure_approved_style_context(project_root)
    except Exception as exc:
        to_dict = getattr(exc, "to_dict", None)
        if callable(to_dict):
            return [to_dict()]
        return [{"code": "style_context_unavailable", "message": str(exc)}]
    return list(project_style_context.validate_spec_against_style_context(spec_data, context))


def _validate_patch_request(patch_request: dict[str, Any]) -> list[dict[str, Any]]:
    if "asset_path" not in patch_request:
        return [{"code": "invalid_patch", "message": "Patch is missing required field: asset_path"}]
    if patch_request.get("op") == "set_widget_properties":
        missing = [field for field in ("widget_name", "properties") if field not in patch_request]
        if missing:
            return [
                {
                    "code": "invalid_patch",
                    "message": f"Patch is missing required field: {missing[0]}",
                }
            ]
        if not isinstance(patch_request.get("properties"), dict):
            return [{"code": "invalid_patch", "message": "Patch field properties must be an object"}]
        return []
    if isinstance(patch_request.get("operations"), list):
        return []

    missing = [field for field in ("parent_widget_name", "widget") if field not in patch_request]
    if missing:
        return [{"code": "invalid_patch", "message": f"Patch is missing required field: {missing[0]}"}]
    if not isinstance(patch_request.get("widget"), dict):
        return [{"code": "invalid_patch", "message": "Patch field widget must be an object"}]
    return []


def _apply_style_context_normalization(project_root: Path, spec_data: dict[str, Any]) -> dict[str, Any]:
    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None:
        return spec_data
    if not hasattr(project_style_context, "validate_spec_against_style_context"):
        return spec_data
    normalized = json.loads(json.dumps(spec_data))
    try:
        context = project_style_context.ensure_approved_style_context(project_root)
        project_style_context.validate_spec_against_style_context(normalized, context)
    except Exception:
        return spec_data
    return normalized


def _strip_spec_directives(spec_data: dict[str, Any]) -> dict[str, Any]:
    """Remove generator-only planning directives before bridge/commandlet payloads."""
    spec = json.loads(json.dumps(spec_data))

    def _clean_node(node: dict[str, Any]) -> None:
        node.pop("_core_role", None)
        node.pop("core_role", None)
        for child in node.get("children", []):
            if isinstance(child, dict):
                _clean_node(child)

    spec.pop("_core_role", None)
    spec.pop("core_role", None)
    root = spec.get("root")
    if isinstance(root, dict):
        _clean_node(root)
    return spec


def _register_generated_widget_if_possible(project_root: Path, spec_data: dict[str, Any], spec_path: Path) -> None:
    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None or not hasattr(project_style_context, "register_generated_widget"):
        return
    asset_path = spec_data.get("asset_path")
    if not isinstance(asset_path, str):
        return
    try:
        project_style_context.register_generated_widget(project_root, asset_path, str(spec_path))
    except Exception:
        return


def _prepare_spec_data(
    project_root: Path,
    raw_spec_data: dict[str, Any],
    *,
    provisional_parent_header_path: Path | None = None,
) -> tuple[dict[str, Any] | None, Any | None, list[dict[str, Any]], list[dict[str, Any]]]:
    widget_spec = _load_widget_spec_module(project_root)
    project_style_context = _load_project_style_context_module(project_root)
    style_context: dict[str, Any] | None = None
    style_context_error: dict[str, Any] | None = None
    project_class_mapping: dict[str, str] = {}
    extra_parent_classes: frozenset[str] = frozenset()
    if project_style_context is not None:
        try:
            style_context = project_style_context.ensure_approved_style_context(project_root)
            style_context = _augment_style_context_with_provisional_parent(
                style_context,
                project_root,
                provisional_parent_header_path,
                str(raw_spec_data.get("parent_class") or ""),
            )
            project_class_mapping = style_context.get("project_class_mapping") or {}
            if hasattr(project_style_context, "extra_parent_classes_from_context"):
                extra_parent_classes = project_style_context.extra_parent_classes_from_context(style_context)
        except Exception as exc:
            to_dict = getattr(exc, "to_dict", None)
            style_context_error = to_dict() if callable(to_dict) else {"code": "style_context_unavailable", "message": str(exc)}
    try:
        normalized = _normalize_spec_data(project_root, raw_spec_data, style_context)
        if style_context is not None and hasattr(project_style_context, "validate_spec_against_style_context"):
            normalized = json.loads(json.dumps(normalized))
            project_style_context.validate_spec_against_style_context(normalized, style_context)
        canonical = _canonicalize_spec_data(
            project_root,
            normalized,
            project_class_mapping or None,
            extra_parent_classes or None,
        )
        if style_context_error is not None:
            return canonical, None, [style_context_error], []
        style_errors = (
            list(project_style_context.validate_spec_against_style_context(canonical, style_context))
            if style_context is not None and hasattr(project_style_context, "validate_spec_against_style_context")
            else []
        )
        blocking = [e for e in style_errors if not e.get("advisory")]
        advisory = [e for e in style_errors if e.get("advisory")]
        if blocking:
            return canonical, None, blocking, advisory
        if hasattr(widget_spec, "load_spec_from_dict"):
            kwargs: dict[str, Any] = {}
            if project_class_mapping:
                kwargs["project_class_mapping"] = project_class_mapping
            if extra_parent_classes:
                kwargs["extra_parent_classes"] = extra_parent_classes
            parsed = widget_spec.load_spec_from_dict(canonical, **kwargs)
        else:
            parsed = None
        canonical = _strip_spec_directives(canonical)
        return canonical, parsed, [], advisory
    except Exception as exc:
        if style_context_error is not None:
            return None, None, [style_context_error], []
        to_dict = getattr(exc, "to_dict", None)
        if callable(to_dict):
            return None, None, [to_dict()], []
        return None, None, [{"code": "spec_validation_failed", "message": str(exc)}], []


def _validate_spec_data(project_root: Path, spec_data: dict[str, Any]) -> dict[str, Any]:
    canonical, _spec, errors, _warnings = _prepare_spec_data(project_root, spec_data)
    if errors:
        raise ValueError(json.dumps({"ok": False, "errors": errors}, indent=2))
    return canonical or spec_data


def _validated_spec(project_root: Path, spec_path: Path, *, provisional_parent_header_path: Path | None = None):
    _spec_data, spec, errors, _warnings = _prepare_spec_data(
        project_root,
        _load_json_file(spec_path),
        provisional_parent_header_path=provisional_parent_header_path,
    )
    if errors:
        raise ValueError(json.dumps({"ok": False, "errors": errors}, indent=2))
    if spec is None:
        raise ValueError("Spec preparation did not produce a parsed spec.")
    return spec


def _has_bind_widget(meta: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_])BindWidget(?!Optional|[A-Za-z0-9_])", meta) is not None


def _parse_backing_bindings(header_text: str) -> dict[str, dict[str, str]]:
    parsed: dict[str, dict[str, str]] = {}
    for match in UPROPERTY_BINDING_PATTERN.finditer(header_text):
        cpp_type = match.group("type").strip()
        object_ptr_match = TOBJECTPTR_PATTERN.match(cpp_type)
        if object_ptr_match:
            cpp_type = object_ptr_match.group("type")
        parsed[match.group("name")] = {
            "cpp_type": cpp_type,
            "meta": " ".join(match.group("meta").split()),
        }
    return parsed


def _cpp_type_from_unreal_class_path(class_path: str) -> str | None:
    if not class_path.startswith("/Script/") or "." not in class_path:
        return None
    class_name = class_path.rsplit(".", 1)[-1]
    if not class_name:
        return None
    return class_name if class_name.startswith("U") else f"U{class_name}"


def _merge_bridge_resolved_bindings(
    bindings: list[dict[str, Any]],
    bridge_result: dict[str, Any],
) -> list[dict[str, Any]]:
    assignments = bridge_result.get("verified_widget_classes")
    if not isinstance(assignments, list):
        return bindings

    expected_by_name: dict[str, str] = {}
    for item in assignments:
        if not isinstance(item, dict):
            continue
        widget_name = item.get("widget_name")
        expected_class = item.get("expected_widget_class")
        if isinstance(widget_name, str) and isinstance(expected_class, str) and expected_class:
            expected_by_name[widget_name] = expected_class

    if not expected_by_name:
        return bindings

    resolved: list[dict[str, Any]] = []
    for binding in bindings:
        updated = dict(binding)
        expected_class = expected_by_name.get(str(updated.get("widget_name") or ""))
        cpp_type = _cpp_type_from_unreal_class_path(expected_class) if expected_class else None
        if expected_class and cpp_type:
            updated["expected_unreal_class"] = expected_class
            updated["cpp_type"] = cpp_type
            updated["include"] = f'"{cpp_type}.h"'
            updated["resolution_source"] = "bridge"
        resolved.append(updated)
    return resolved


async def _bridge_verify_only_bindings(
    args: dict[str, Any],
    spec_data: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    try:
        bridge_result = await _post_bridge(
            _bridge_url(args),
            "/accelbyte-ui-tools/resolve",
            {"spec": spec_data},
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        return bindings, None, {
            "code": "bridge_verify_only_unavailable",
            "message": (
                "Editor bridge was not reachable; using Python/style-context binding resolution. "
                f"{exc}"
            ),
            "advisory": True,
        }
    except Exception as exc:
        return bindings, None, {
            "code": "bridge_verify_only_failed",
            "message": (
                "Editor bridge verify-only resolution failed; using Python/style-context binding resolution. "
                f"{exc}"
            ),
            "advisory": True,
        }

    if not bridge_result.get("ok"):
        return bindings, bridge_result, {
            "code": "bridge_verify_only_failed",
            "message": "Editor bridge verify-only resolution returned errors; using Python/style-context binding resolution.",
            "bridge_errors": bridge_result.get("errors"),
            "advisory": True,
        }
    return _merge_bridge_resolved_bindings(bindings, bridge_result), bridge_result, None


async def accelbyte_ui_resolve(args: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(args.get("projectPath"), args.get("workspaceRoot"))
    if args.get("auto_approve_style", True):
        _auto_approve_style_context(project_root)
    spec_path = _resolve_project_file_path(project_root, args["specPath"])
    spec_data, parsed_spec, errors, warnings = _prepare_spec_data(project_root, _load_json_file(spec_path))
    if errors:
        return {"ok": False, "errors": errors}
    if spec_data is None or parsed_spec is None:
        return {"ok": False, "errors": [{"code": "spec_validation_failed", "message": "Spec preparation did not produce a canonical spec."}]}

    normalized_path = _write_normalized_spec_if_requested(project_root, args, spec_data)
    bindings = [binding.to_dict() for binding in parsed_spec.bindings()] if hasattr(parsed_spec, "bindings") else []
    bindings, bridge_result, bridge_warning = await _bridge_verify_only_bindings(args, spec_data, bindings)
    collection_expectations = _collection_entry_expectations_from_spec(spec_data)

    result: dict[str, Any] = {
        "ok": True,
        "asset_path": parsed_spec.asset_path,
        "widget_count": parsed_spec.widget_count(),
        "variable_widget_names": parsed_spec.variable_widget_names(),
        "bindings": bindings,
        "resolve_only": True,
        "normalized_spec": spec_data,
        "expected_collection_entries": collection_expectations,
        "warnings": [],
        "errors": [],
        "rebuild_advisories": [
            {
                "code": "new_uclasses_before_rebuild",
                "message": (
                    "For multi-widget script-backed flows, write every required UCLASS header before "
                    "the first full Build.bat rebuild so dependent specs can resolve all classes in one cycle."
                ),
                "advisory": True,
            },
            {
                "code": "uproperty_type_change_intermediate_cache",
                "message": (
                    "If an existing UPROPERTY widget type changed, delete the affected Unreal Intermediate "
                    "build artifacts before rebuilding; incremental/unity builds can keep stale reflected types."
                ),
                "advisory": True,
            },
        ],
    }
    if bridge_result is not None:
        result["bridge_resolve"] = bridge_result
        if isinstance(bridge_result.get("verified_widget_classes"), list):
            result["verified_widget_classes"] = bridge_result["verified_widget_classes"]
        if isinstance(bridge_result.get("expected_collection_entries"), list):
            result["expected_collection_entries"] = bridge_result["expected_collection_entries"]
    all_warnings = list(warnings)
    if bridge_warning:
        all_warnings.append(bridge_warning)
    result["warnings"] = all_warnings
    if normalized_path:
        result["normalized_spec_path"] = normalized_path
    return result


def _verify_backing_bindings(header_text: str, bindings: list[Any]) -> list[dict[str, Any]]:
    declarations = _parse_backing_bindings(header_text)
    verified: list[dict[str, Any]] = []
    for binding in bindings:
        expected = binding.to_dict() if hasattr(binding, "to_dict") else dict(binding)
        actual = declarations.get(str(expected["widget_name"]))
        actual_type = actual["cpp_type"] if actual else ""
        actual_meta = actual["meta"] if actual else ""
        has_required_bind = bool(actual) and _has_bind_widget(actual_meta)
        has_optional_bind = "BindWidgetOptional" in actual_meta
        type_matches = bool(actual) and actual_type == expected["cpp_type"]
        optional_expected = "BindWidgetOptional" in str(expected.get("bind_meta", ""))
        if optional_expected:
            ok = type_matches and has_optional_bind
        else:
            ok = type_matches and has_required_bind and not has_optional_bind
        reason = ""
        if not actual:
            reason = "missing_property"
        elif optional_expected and not has_optional_bind:
            reason = "required_binding_when_optional_expected"
        elif not optional_expected and has_optional_bind:
            reason = "optional_binding_not_allowed"
        elif not has_required_bind and not optional_expected:
            reason = "missing_bind_widget"
        elif not type_matches:
            reason = "wrong_cpp_type"
        verified.append(
            {
                "widget_name": expected["widget_name"],
                "expected_cpp_type": expected["cpp_type"],
                "actual_cpp_type": actual_type or None,
                "expected_bind_meta": expected["bind_meta"],
                "actual_bind_meta": actual_meta or None,
                "verified": ok,
                "reason": reason,
            }
        )
    return verified


def _first_backing_binding_error(verified: list[dict[str, Any]], header_path: Path) -> dict[str, str] | None:
    for item in verified:
        if item["verified"]:
            continue
        widget_name = item["widget_name"]
        expected_type = item["expected_cpp_type"]
        actual_type = item.get("actual_cpp_type") or "<missing>"
        if item["reason"] == "optional_binding_not_allowed":
            detail = "uses BindWidgetOptional; spec requires BindWidget (add optional_binding: true to spec node to allow optional)"
        elif item["reason"] == "required_binding_when_optional_expected":
            detail = "uses BindWidget but spec declares optional_binding: true (change to BindWidgetOptional)"
        elif item["reason"] == "missing_bind_widget":
            detail = "is missing BindWidget metadata"
        elif item["reason"] == "missing_property":
            detail = "is not declared in the backing class"
        else:
            detail = f"has actual C++ type {actual_type}"
        return {
            "code": "backing_binding_mismatch",
            "message": (
                f"Backing binding '{widget_name}' in {header_path} is invalid: "
                f"expected {expected_type} with BindWidget, actual {actual_type}; {detail}."
            ),
        }
    return None


def _write_normalized_spec_if_requested(project_root: Path, args: dict[str, Any], spec_data: dict[str, Any]) -> str | None:
    output_value = args.get("writeNormalizedSpecPath") or args.get("normalizedSpecPath")
    if not output_value:
        return None
    output_path = _resolve_project_file_path(project_root, str(output_value))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec_data, indent=2), encoding="utf-8")
    return str(output_path)


def _write_runtime_normalized_spec(project_root: Path, source_spec_path: Path, spec_data: dict[str, Any]) -> Path:
    output_dir = project_root / "Saved" / "AccelByteUITools"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_spec_path.stem}.normalized.json"
    output_path.write_text(json.dumps(spec_data, indent=2), encoding="utf-8")
    return output_path


def _is_script_backed_project_parent(spec_data: dict[str, Any]) -> bool:
    parent_class = str(spec_data.get("parent_class") or "")
    if not parent_class.startswith("/Script/"):
        return False

    module_name = parent_class.removeprefix("/Script/").split(".", 1)[0]
    commandlet_safe_modules = {
        "CommonUI",
        "UMG",
        "AccelByteUITools",
    }
    return module_name not in commandlet_safe_modules


def _raise_commandlet_live_coding_bypass_error(spec_data: dict[str, Any]) -> None:
    parent_class = str(spec_data.get("parent_class") or "")
    raise RuntimeError(
        "Bridge generation is required for script-backed widgets with project C++ "
        f"parent classes ({parent_class}). A commandlet runs in a separate Unreal "
        "process and may not see freshly Live Coded classes. Open the editor bridge, "
        "run Live Coding compile, then call accelbyte_ui_validate and "
        "accelbyte_ui_generate with mode \"bridge\"."
    )


async def accelbyte_ui_bridge_health(args: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{_bridge_url(args)}/accelbyte-ui-tools/health")
            response.raise_for_status()
            loaded = response.json()
            if not isinstance(loaded, dict):
                raise ValueError("Bridge health response must be a JSON object")
            return loaded
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "errors": [{"code": "bridge_http_error", "message": str(exc)}]}
    except httpx.RequestError as exc:
        return {"ok": False, "errors": [{"code": "bridge_unavailable", "message": str(exc)}]}
    except ValueError as exc:
        return {"ok": False, "errors": [{"code": "bridge_invalid_response", "message": str(exc)}]}


async def accelbyte_ui_validate(args: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(args.get("projectPath"), args.get("workspaceRoot"))
    spec_path = _resolve_project_file_path(project_root, args["specPath"])

    try:
        raw_spec_data = _load_json_file(spec_path)
    except json.JSONDecodeError:
        widget_spec = _load_widget_spec_module(project_root)
        spec = widget_spec.load_spec_file(spec_path)
        result = {
            "ok": True,
            "asset_path": spec.asset_path,
            "widget_count": spec.widget_count(),
            "variable_widget_names": spec.variable_widget_names(),
        }
        if hasattr(spec, "bindings"):
            result["bindings"] = [binding.to_dict() for binding in spec.bindings()]
        result["warnings"] = [
            {
                "code": "legacy_spec_fallback",
                "message": (
                    "Spec was loaded through a legacy project-local parser because it is not valid JSON. "
                    "Canonical JSON normalization and style-context validation were bypassed."
                ),
                "advisory": True,
            }
        ]
        return result

    spec_data, spec, errors, warnings = _prepare_spec_data(project_root, raw_spec_data)
    if errors:
        return {"ok": False, "errors": errors}
    if spec_data is None or spec is None:
        return {"ok": False, "errors": [{"code": "spec_validation_failed", "message": "Spec preparation did not produce a canonical spec."}]}
    normalized_path = _write_normalized_spec_if_requested(project_root, args, spec_data)

    result = {
        "ok": True,
        "asset_path": spec.asset_path,
        "widget_count": spec.widget_count(),
        "variable_widget_names": spec.variable_widget_names(),
    }
    if hasattr(spec, "bindings"):
        result["bindings"] = [binding.to_dict() for binding in spec.bindings()]
    if normalized_path:
        result["normalized_spec_path"] = normalized_path
    if warnings:
        result["warnings"] = warnings
    return result


async def accelbyte_ui_verify_backing_class(args: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(args.get("projectPath"), args.get("workspaceRoot"))
    spec_path = _resolve_project_file_path(project_root, args["specPath"])
    header_path = _resolve_project_file_path(project_root, args["headerPath"])
    try:
        raw_spec_data = _load_json_file(spec_path)
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [{"code": "invalid_json", "message": str(exc)}]}
    parent_class = str(raw_spec_data.get("parent_class") or "")
    if not _is_parent_class_declared_by_header(project_root, header_path, parent_class):
        return {"ok": False, "errors": [_final_parent_required_error(project_root, raw_spec_data, header_path)]}
    if args.get("autoApproveStyle", args.get("auto_approve_style", True)):
        _auto_approve_style_context(project_root)
    try:
        spec = _validated_spec(project_root, spec_path, provisional_parent_header_path=header_path)
    except ValueError as exc:
        try:
            payload = json.loads(str(exc))
            if isinstance(payload, dict) and isinstance(payload.get("errors"), list):
                return {"ok": False, "errors": payload["errors"]}
        except json.JSONDecodeError:
            pass
        return {"ok": False, "errors": [{"code": "spec_validation_failed", "message": str(exc)}]}
    bindings = [binding.to_dict() for binding in spec.bindings()] if hasattr(spec, "bindings") else []
    bridge_result = None
    warnings: list[dict[str, Any]] = []
    bindings, bridge_result, bridge_warning = await _bridge_verify_only_bindings(args, spec.to_dict(), bindings)
    if bridge_warning:
        warnings.append(bridge_warning)
    header_text = header_path.read_text(encoding="utf-8")
    verified = _verify_backing_bindings(header_text, bindings)
    error = _first_backing_binding_error(verified, header_path)
    result: dict[str, Any] = {
        "ok": error is None,
        "asset_path": spec.asset_path,
        "header_path": str(header_path),
        "binding_count": len(bindings),
        "bindings": bindings,
        "verified_backing_bindings": verified,
    }
    if bridge_result is not None:
        result["bridge_verify_only"] = bridge_result
    if warnings:
        result["warnings"] = warnings
    if error:
        result["errors"] = [error]
    return result


def _normalize_verify_failed_response(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok"):
        return result
    errors = result.get("errors") or []
    only_verify_failed = errors and all(e.get("code") in {"verify_failed", "stale_live_coding_class"} for e in errors)
    widget_count = result.get("verified_widget_count", 0) or result.get("widget_count", 0)
    if only_verify_failed and isinstance(widget_count, (int, float)) and widget_count > 0:
        normalized = dict(result)
        normalized["ok"] = True
        normalized["generated"] = True
        normalized["verify_failed"] = True
        normalized.pop("errors", None)
        normalized["verify_failed_details"] = errors
        normalized["message"] = (
            "Blueprint generated successfully. Post-generation class hierarchy check found mismatches "
            "(expected when project widgets don't extend the AGS C++ base class). "
            "All widgets were placed. Do not switch project widgets back to AGSUI fallbacks in response to this."
        )
        return normalized
    return result


def _collection_entry_expectations_from_spec(spec_data: dict[str, Any]) -> list[dict[str, str]]:
    expectations: list[dict[str, str]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        widget_type = str(node.get("type") or "")
        entry_widget_class = node.get("entry_widget_class")
        widget_name = node.get("name")
        if (
            widget_type in {"ListView", "TileView", "TreeView"}
            and isinstance(widget_name, str)
            and isinstance(entry_widget_class, str)
            and entry_widget_class
        ):
            expectations.append(
                {
                    "widget_name": widget_name,
                    "expected_entry_widget_class": entry_widget_class,
                }
            )
        for child in node.get("children", []):
            walk(child)

    walk(spec_data.get("root"))
    return expectations


def _annotate_generated_wiring(result: dict[str, Any], spec_data: dict[str, Any]) -> dict[str, Any]:
    result.setdefault("parent_class", spec_data.get("parent_class"))
    expectations = _collection_entry_expectations_from_spec(spec_data)
    if expectations:
        result.setdefault("expected_collection_entries", expectations)
    return result


async def accelbyte_ui_generate(args: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(args.get("projectPath"), args.get("workspaceRoot"))
    if args.get("auto_approve_style", True):
        _auto_approve_style_context(project_root)
    spec_path = _resolve_project_file_path(project_root, args["specPath"])
    spec, _parsed_spec, errors, warnings = _prepare_spec_data(project_root, _load_json_file(spec_path))
    if errors:
        return {"ok": False, "errors": errors}
    if spec is None:
        return {"ok": False, "errors": [{"code": "spec_validation_failed", "message": "Spec preparation did not produce a canonical spec."}]}
    normalized_path = _write_normalized_spec_if_requested(project_root, args, spec)
    mode = str(args.get("mode") or "bridge")
    force = bool(args.get("force", False))
    editor_exe = args.get("editorExe")

    if mode == "verify-only":
        result = await accelbyte_ui_resolve(args)
        if result.get("ok"):
            result["verify_only"] = True
            result["compatibility_alias"] = "accelbyte_ui_resolve"
            if "bridge_resolve" in result:
                result["bridge_verify_only"] = result["bridge_resolve"]
        return result

    if mode == "commandlet":
        commandlet_spec_path = Path(normalized_path) if normalized_path else _write_runtime_normalized_spec(project_root, spec_path, spec)
        result = _run_cli_generate(project_root, commandlet_spec_path, force, editor_exe)
        if isinstance(result, dict) and result.get("ok"):
            _register_generated_widget_if_possible(project_root, spec, commandlet_spec_path)
        if normalized_path and isinstance(result, dict):
            result.setdefault("normalized_spec_path", normalized_path)
        if warnings and isinstance(result, dict):
            result.setdefault("warnings", warnings)
        return result

    try:
        result = await _post_bridge(
            _bridge_url(args),
            "/accelbyte-ui-tools/generate",
            {"force": force, "spec": spec},
        )
        result = _normalize_verify_failed_response(result)
        if isinstance(result, dict) and result.get("ok"):
            registry_spec_path = Path(normalized_path) if normalized_path else _write_runtime_normalized_spec(project_root, spec_path, spec)
            _register_generated_widget_if_possible(project_root, spec, registry_spec_path)
        if normalized_path:
            result.setdefault("normalized_spec_path", normalized_path)
        if warnings:
            result.setdefault("warnings", warnings)
        if result.get("ok"):
            _annotate_generated_wiring(result, spec)
        return result
    except (httpx.ConnectError, httpx.TimeoutException):
        if mode == "bridge":
            raise
        if _is_script_backed_project_parent(spec):
            _raise_commandlet_live_coding_bypass_error(spec)
        commandlet_spec_path = Path(normalized_path) if normalized_path else _write_runtime_normalized_spec(project_root, spec_path, spec)
        result = _run_cli_generate(project_root, commandlet_spec_path, force, editor_exe)
        result = _normalize_verify_failed_response(result) if isinstance(result, dict) else result
        if isinstance(result, dict) and result.get("ok"):
            _register_generated_widget_if_possible(project_root, spec, commandlet_spec_path)
        if normalized_path and isinstance(result, dict):
            result.setdefault("normalized_spec_path", normalized_path)
        if warnings and isinstance(result, dict):
            result.setdefault("warnings", warnings)
        return result


async def accelbyte_ui_list_entry_candidates(args: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(args.get("projectPath"), args.get("workspaceRoot"))
    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None:
        return {"ok": False, "errors": [{"code": "style_context_unavailable", "message": "project_style_context module not found"}]}
    try:
        context = project_style_context.ensure_approved_style_context(project_root)
    except Exception as exc:
        to_dict = getattr(exc, "to_dict", None)
        if callable(to_dict):
            return {"ok": False, "errors": [to_dict()]}
        return {"ok": False, "errors": [{"code": "style_context_unavailable", "message": str(exc)}]}
    enforced_roles = context.get("enforced_roles", {}) if isinstance(context, dict) else {}
    list_row_role = enforced_roles.get("list_row", {})
    compatible = list_row_role.get("compatible_project_candidates", [])
    incompatible = list_row_role.get("incompatible_or_unknown_project_candidates", [])
    agsui_fallbacks = [
        {"use_case": "Generic / players",  "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_PlayerRow.WBP_AGS_PlayerRow_C"},
        {"use_case": "Leaderboard",        "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_LeaderboardRow.WBP_AGS_LeaderboardRow_C"},
        {"use_case": "Friends",            "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_FriendRow.WBP_AGS_FriendRow_C"},
        {"use_case": "Sessions",           "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_SessionRow.WBP_AGS_SessionRow_C"},
        {"use_case": "Entitlements",       "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_EntitlementRow.WBP_AGS_EntitlementRow_C"},
        {"use_case": "Notifications",      "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_ListRow.WBP_AGS_ListRow_C"},
        {"use_case": "Cloud save",         "entry_widget_class": "/AccelByteUITools/AGSUI/Lists/WBP_AGS_CloudSaveSlotRow.WBP_AGS_CloudSaveSlotRow_C"},
        {"use_case": "Store items",        "entry_widget_class": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_StoreItemCard.WBP_AGS_StoreItemCard_C"},
        {"use_case": "Achievements",       "entry_widget_class": "/AccelByteUITools/AGSUI/FeatureBlocks/WBP_AGS_AchievementCard.WBP_AGS_AchievementCard_C"},
    ]
    return {
        "ok": True,
        "compatible_candidates": compatible,
        "incompatible_candidates": incompatible,
        "agsui_fallbacks": agsui_fallbacks,
        "generated_project_widgets_must_use_project_entries": True,
        "warning": (
            "For /Game/.../UI/Generated/ specs, entry_widget_class must reference a compatible project-owned "
            "entry widget. AGSUI fallbacks are diagnostic/legacy references and will be rejected by validation."
        ),
    }


async def generate_project_core_widgets(args: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(args.get("projectPath"), args.get("workspaceRoot"))
    bridge_url = _bridge_url(args)
    force = bool(args.get("force", False))
    all_roles = bool(args.get("allRoles", False))
    roles_arg: list[str] | None = args.get("roles") or None
    single_role = args.get("role")
    if roles_arg is None and isinstance(single_role, str) and single_role:
        roles_arg = [single_role]

    project_style_context = _load_project_style_context_module(project_root)
    if project_style_context is None:
        return {"ok": False, "errors": [{"code": "style_context_unavailable", "message": "project_style_context module not found"}]}

    CORE_COMPONENT_ROLES = getattr(project_style_context, "CORE_COMPONENT_ROLES", {})
    STATE_ROLES = ("state_loading", "state_empty", "state_error", "state_idle")
    TEMPLATES_DIR = (
        project_root / "Plugins" / "AccelByteUITools" / "Tools" / "specs" / "core_templates"
    )
    if not TEMPLATES_DIR.exists():
        fallback = Path(__file__).parent / "data" / "AccelByteUITools" / "Tools" / "specs" / "core_templates"
        if fallback.exists():
            TEMPLATES_DIR = fallback

    try:
        context = project_style_context.ensure_approved_style_context(project_root)
    except Exception as exc:
        to_dict = getattr(exc, "to_dict", None)
        return {"ok": False, "errors": [to_dict() if callable(to_dict) else {"code": "style_context_error", "message": str(exc)}]}

    enforced_roles = context.get("enforced_roles", {})
    registry = project_style_context.load_generated_components_registry(project_root)

    if all_roles:
        target_roles = list(CORE_COMPONENT_ROLES.keys())
    elif roles_arg:
        target_roles = roles_arg
    else:
        target_roles = list(STATE_ROLES)

    def _refresh_approved_style_context() -> str | None:
        if not hasattr(project_style_context, "discover_project_style"):
            return None
        refreshed = project_style_context.discover_project_style(project_root)
        if hasattr(project_style_context, "write_style_context"):
            project_style_context.write_style_context(refreshed, project_root)
        if hasattr(project_style_context, "approve_style_context"):
            project_style_context.approve_style_context(refreshed, project_root)
        return refreshed.get("fingerprint") if isinstance(refreshed, dict) else None

    def _inject_styles(spec: dict) -> dict:
        spec = json.loads(json.dumps(spec))

        def _role_candidates(role: str, *, kind: str | None = None) -> list[dict[str, Any]]:
            candidates = list(enforced_roles.get(role, {}).get("project_candidates", []))
            if kind is None:
                return candidates
            return [item for item in candidates if item.get("kind") == kind]

        def _all_button_widget_candidates() -> list[dict[str, Any]]:
            seen: set[str] = set()
            result: list[dict[str, Any]] = []
            for button_role in ("primary_button", "secondary_button", "danger_button", "tab_button"):
                for item in _role_candidates(button_role, kind="widget"):
                    ref = item.get("class_path") or item.get("asset_path")
                    if isinstance(ref, str) and ref not in seen:
                        result.append(item)
                        seen.add(ref)
            return result

        def _process_node(node: dict) -> None:
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
                    _process_node(child)

        root = spec.get("root")
        if isinstance(root, dict):
            _process_node(root)
        return spec

    def _strip_directives(spec: dict) -> dict:
        spec = json.loads(json.dumps(spec))

        def _clean(node: dict) -> None:
            node.pop("_comment", None)
            node.pop("_core_role", None)
            node.pop("__style_inject", None)
            for child in node.get("children", []):
                if isinstance(child, dict):
                    _clean(child)

        spec.pop("_comment", None)
        spec.pop("_core_role", None)
        root = spec.get("root")
        if isinstance(root, dict):
            _clean(root)
        return spec

    def _is_button_template_node(widget_type: str) -> bool:
        return "button" in widget_type.casefold() or widget_type in {
            "AGSBaseButton", "AGSButton", "AGSSecondaryButton", "AGSDangerButton"
        }

    def _can_apply_button_style_to_template_node(widget_type: str, class_path: Any = None) -> bool:
        # AGSBaseButton-derived template nodes are UUserWidget wrappers, not native
        # CommonButtonBase/Button instances. Applying a Common UI button_style_class
        # to them breaks mixed UMG+CommonUI generation at the bridge layer.
        if (
            widget_type in {"AGSBaseButton", "AGSButton", "AGSSecondaryButton", "AGSDangerButton"}
            and not (isinstance(class_path, str) and class_path.startswith("/Game/"))
        ):
            return False
        return "button" in widget_type.casefold() or widget_type == "Button"

    def _bridge_result_asset_already_exists(result: dict[str, Any]) -> bool:
        values: list[Any] = [result.get("message"), result.get("error")]
        values.extend(result.get("errors", []) if isinstance(result.get("errors"), list) else [])
        for value in values:
            if isinstance(value, dict):
                value = " ".join(str(value.get(key, "")) for key in ("code", "message", "detail"))
            text = str(value).casefold()
            if "asset already exists" in text or ("already exists" in text and "asset" in text):
                return True
        return False

    results = []
    async with httpx.AsyncClient(timeout=60.0) as bridge_client:
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
                results.append({"role": role, "status": "no_template", "message": f"No template for role '{role}'."})
                continue

            template_path = TEMPLATES_DIR / f"{template_name}.json"
            if not template_path.exists():
                results.append({"role": role, "status": "template_missing", "path": str(template_path)})
                continue

            raw_spec = json.loads(template_path.read_text(encoding="utf-8"))
            injected_spec = _inject_styles(raw_spec)
            spec, _parsed_spec, errors, warnings = _prepare_spec_data(project_root, injected_spec)
            if errors or spec is None:
                results.append(
                    {
                        "role": role,
                        "status": "validation_failed",
                        "errors": errors or [{"code": "spec_validation_failed", "message": "Spec preparation did not produce a canonical spec."}],
                    }
                )
                continue

            spec_out_dir = project_root / "Content" / "AGS" / "UI" / "Generated" / "Specs" / "Components"
            spec_out_dir.mkdir(parents=True, exist_ok=True)
            asset_name = info["generated_asset_name"]
            spec_path = spec_out_dir / f"{asset_name}.json"
            spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

            bridge_payload = {"force": force, "spec": spec}
            retried_with_force = False
            try:
                bridge_result = await _post_bridge(
                    bridge_url,
                    "/accelbyte-ui-tools/generate",
                    bridge_payload,
                    client=bridge_client,
                )
                if not bridge_result.get("ok") and not force and _bridge_result_asset_already_exists(bridge_result):
                    bridge_result = await _post_bridge(
                        bridge_url,
                        "/accelbyte-ui-tools/generate",
                        {"force": True, "spec": spec},
                        client=bridge_client,
                    )
                    retried_with_force = True
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                results.append({"role": role, "status": "bridge_unavailable", "spec_path": str(spec_path), "message": str(exc)})
                continue
            except Exception as exc:
                results.append({"role": role, "status": "bridge_error", "spec_path": str(spec_path), "message": str(exc)})
                continue

            if bridge_result.get("ok"):
                asset_path = spec.get("asset_path", "")
                project_style_context.register_generated_component(project_root, role, asset_path, str(spec_path))
                item = {"role": role, "status": "generated", "asset_path": asset_path, "spec_path": str(spec_path)}
                if warnings:
                    item["warnings"] = warnings
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
        "validation_failed",
        "bridge_unavailable",
        "bridge_error",
        "bridge_rejected",
    }
    ok = not any(result.get("status") in failed_statuses for result in results)
    response: dict[str, Any] = {"ok": ok, "results": results}
    successful_or_present_statuses = {"generated", "already_generated"}
    if any(result.get("status") in successful_or_present_statuses for result in results):
        try:
            fingerprint = _refresh_approved_style_context()
            response["style_context_refreshed"] = True
            if fingerprint:
                response["style_context_fingerprint"] = fingerprint
        except Exception as exc:
            response["style_context_refreshed"] = False
            response.setdefault("warnings", []).append(
                {
                    "code": "style_context_refresh_failed",
                    "message": (
                        "Generated project core widget registry was updated, but the approved style context "
                        f"could not be refreshed automatically: {exc}"
                    ),
                }
            )
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


async def accelbyte_ui_patch(args: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(args.get("projectPath"), args.get("workspaceRoot"))
    patch_path = _resolve_project_file_path(project_root, args["patchPath"])
    patch_request = _load_json_file(patch_path)
    patch_errors = _validate_patch_request(patch_request)
    if patch_errors:
        return {"ok": False, "errors": patch_errors}
    if isinstance(patch_request.get("widget"), dict):
        style_errors = _style_context_validation_result(
            project_root,
            {"asset_path": patch_request.get("asset_path"), "root": patch_request["widget"]},
        )
        blocking_style_errors = [e for e in style_errors if not e.get("advisory")]
        if blocking_style_errors:
            return {"ok": False, "errors": blocking_style_errors}
    mode = str(args.get("mode") or "bridge")
    editor_exe = args.get("editorExe")

    if mode == "commandlet":
        return _run_cli_patch(project_root, patch_path, editor_exe)

    try:
        return await _post_bridge(
            _bridge_url(args),
            "/accelbyte-ui-tools/patch",
            patch_request,
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        if mode == "bridge":
            raise
        return _run_cli_patch(project_root, patch_path, editor_exe)
