"""
Download from GitHub and install the AccelByte Unreal SDK plugin into an Unreal project.
Supports release ZIP (GitHub API) or git clone; optionally patches .uproject and Build files.
Can optionally regenerate IDE project files (.sln / .vcxproj) after setup.
Python translation of sdkInstaller.js.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

REGENERATE_TIMEOUT_MS = 120000
GITHUB_API_BASE = "https://api.github.com/repos"

SDK_COMPONENTS = {
    "sdk": {
        "repo": "AccelByte/accelbyte-unreal-sdk-plugin",
        "addDefaultConfig": True,
    },
    "oss": {
        "repo": "AccelByte/accelbyte-unreal-oss",
        "addDefaultConfig": False,
    },
    "networkUtilities": {
        "repo": "AccelByte/accelbyte-unreal-network-utilities",
        "addDefaultConfig": False,
    },
}

INSTALL_ORDER = ["networkUtilities", "sdk", "oss"]
PLUGINS_SUBFOLDER = "Accelbyte"


# ---------------------------------------------------------------------------
# Project path validation
# ---------------------------------------------------------------------------

def _validate_project_path(
    project_path: str, workspace_root: str | None
) -> tuple[Path, Path, str]:
    """Resolve project path, verify it exists and contains exactly one .uproject."""
    p = Path(project_path)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        base = Path(workspace_root) if workspace_root else Path.cwd()
        resolved = (base / project_path).resolve()

    if not resolved.exists():
        raise RuntimeError(
            f"Project path does not exist: {resolved}. "
            "Provide an absolute path or a path relative to the workspace."
        )

    if not resolved.is_dir():
        raise RuntimeError(f"Project path is not a directory: {resolved}")

    uproject_files = [e for e in resolved.iterdir() if e.suffix == ".uproject"]
    if not uproject_files:
        raise RuntimeError(
            f"No .uproject file found in {resolved}. "
            "The path must be the Unreal project root (directory containing the .uproject file)."
        )
    if len(uproject_files) > 1:
        raise RuntimeError(
            f"Multiple .uproject files found in {resolved}. "
            "Specify a directory that contains exactly one Unreal project."
        )

    uproject_path = uproject_files[0]
    return resolved, uproject_path, uproject_path.name


# ---------------------------------------------------------------------------
# Plugin folder helpers
# ---------------------------------------------------------------------------

def _get_plugin_module_name(plugin_dir: Path) -> str:
    """Read the plugin module name from the .uplugin file."""
    uplugin_files = [e for e in plugin_dir.iterdir() if e.suffix == ".uplugin"]
    if not uplugin_files:
        raise RuntimeError(
            f"No .uplugin file found in {plugin_dir}. "
            "The installed folder may not be a valid Unreal plugin."
        )
    uplugin_path = uplugin_files[0]
    try:
        data = json.loads(uplugin_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse .uplugin file: {uplugin_path}. {e}")

    modules = data.get("Modules")
    if isinstance(modules, list) and modules and modules[0].get("Name"):
        return modules[0]["Name"]
    friendly = data.get("FriendlyName")
    if friendly:
        return re.sub(r"\s+", "", friendly)
    raise RuntimeError(
        f"Could not determine plugin module name from {uplugin_path}. "
        "Ensure the .uplugin has Modules[0].Name or FriendlyName."
    )


def _find_plugin_folder_in_dir(dir_path: Path) -> Path:
    """Find the plugin folder (containing .uplugin) inside a directory."""
    top_entries = list(dir_path.iterdir())
    if not top_entries:
        raise RuntimeError("Directory is empty.")

    if len(top_entries) == 1 and top_entries[0].is_dir():
        return top_entries[0]

    if any(e.suffix == ".uplugin" for e in top_entries):
        return dir_path

    for entry in top_entries:
        if entry.is_dir():
            sub_entries = list(entry.iterdir())
            if any(e.suffix == ".uplugin" for e in sub_entries):
                return entry

    raise RuntimeError(
        "Directory does not contain a recognizable plugin folder "
        "(expected a .uplugin file)."
    )


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

async def _download_release_zip(repo: str, version: str | None) -> Path:
    """Download release ZIP from GitHub (latest or specific tag) and extract to a temp dir."""
    url = (
        f"{GITHUB_API_BASE}/{repo}/releases/tags/{httpx.utils.quote(version, safe='')}"
        if version
        else f"{GITHUB_API_BASE}/{repo}/releases/latest"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "AccelByte-Unreal-SDK-MCP",
            },
        )
        if res.status_code != 200:
            raise RuntimeError(
                f"GitHub API failed ({res.status_code}): {url}. "
                f"{res.text[:200]}. Check network and that the release/tag exists."
            )
        release = res.json()

        assets = release.get("assets") or []
        zip_asset = next(
            (a for a in assets if a.get("name", "").lower().endswith(".zip")),
            None,
        )
        if not zip_asset or not zip_asset.get("browser_download_url"):
            tag = release.get("tag_name") or release.get("name", "")
            raise RuntimeError(
                f'No ZIP asset found in release "{tag}". Check {repo}/releases.'
            )

        zip_res = await client.get(
            zip_asset["browser_download_url"],
            headers={"User-Agent": "AccelByte-Unreal-SDK-MCP"},
            follow_redirects=True,
        )
        if zip_res.status_code != 200:
            raise RuntimeError(
                f"Failed to download ZIP ({zip_res.status_code}): "
                f"{zip_asset['browser_download_url']}. Check network."
            )

    temp_dir = Path(tempfile.mkdtemp(prefix="accelbyte-sdk-install-"))
    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        zf.extractall(temp_dir)

    return _find_plugin_folder_in_dir(temp_dir)


def _clone_git(repo: str, version: str | None) -> Path:
    """Clone repo via git into a temp directory and return path to plugin folder."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError(
            "Git is not available. Use source: 'release' to download a ZIP, or install Git."
        )

    repo_url = f"https://github.com/{repo}.git"
    temp_dir = Path(tempfile.mkdtemp(prefix="accelbyte-sdk-git-"))

    cmd = ["git", "clone", "--depth", "1"]
    if version:
        cmd += ["--branch", version]
    cmd += [repo_url, "plugin"]

    try:
        subprocess.run(
            cmd,
            cwd=str(temp_dir),
            capture_output=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Git clone failed: {e}. "
            f'Check repository URL and branch/tag "{version or "default"}".'
        )

    plugin_path = temp_dir / "plugin"
    if not plugin_path.exists():
        raise RuntimeError("Git clone did not create expected 'plugin' directory.")

    return _find_plugin_folder_in_dir(plugin_path)


# ---------------------------------------------------------------------------
# Plugin installation
# ---------------------------------------------------------------------------

def _install_plugin(
    source_plugin_dir: Path, project_root: Path, plugin_folder_name: str | None
) -> tuple[Path, str]:
    """Copy plugin folder to project's Plugins/Accelbyte directory."""
    folder_name = plugin_folder_name or source_plugin_dir.name
    plugins_dir = project_root / "Plugins" / PLUGINS_SUBFOLDER
    dest_path = plugins_dir / folder_name

    if dest_path.exists():
        raise RuntimeError(
            f"Plugin already installed at {dest_path}. "
            "Remove the existing folder or use a different version."
        )

    plugins_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(source_plugin_dir), str(dest_path))
    return dest_path, folder_name


# ---------------------------------------------------------------------------
# Project file patching
# ---------------------------------------------------------------------------

def _ensure_online_subsystem_config(project_root: Path, changes: list) -> None:
    """Ensure [OnlineSubsystem] and DefaultPlatformService=AccelByte in DefaultEngine.ini."""
    config_dir = project_root / "Config"
    config_path = config_dir / "DefaultEngine.ini"
    online_subsystem_section = "[OnlineSubsystem]"
    default_platform_line = "DefaultPlatformService=AccelByte"

    if not config_path.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            f"{online_subsystem_section}\n"
            "; Use AccelByte as the default online platform\n"
            f"{default_platform_line}\n",
            encoding="utf-8",
        )
        changes.append(
            "Created Config/DefaultEngine.ini with [OnlineSubsystem] DefaultPlatformService=AccelByte."
        )
        return

    content = config_path.read_text(encoding="utf-8")
    if default_platform_line in content:
        return

    if online_subsystem_section in content:
        insert_idx = content.index(online_subsystem_section) + len(online_subsystem_section)
        new_content = content[:insert_idx] + "\n" + default_platform_line + content[insert_idx:]
        config_path.write_text(new_content, encoding="utf-8")
        changes.append(
            "Added DefaultPlatformService=AccelByte to [OnlineSubsystem] in Config/DefaultEngine.ini."
        )
    else:
        trimmed = content.rstrip()
        config_path.write_text(
            trimmed + f"\n\n{online_subsystem_section}\n{default_platform_line}\n",
            encoding="utf-8",
        )
        changes.append(
            "Added [OnlineSubsystem] and DefaultPlatformService=AccelByte to Config/DefaultEngine.ini."
        )


def _get_default_accelbyte_config_block(module_name: str) -> str:
    section = f"[/Script/{module_name}.AccelByteSettings]"
    return f"""
{section}
; Client ID from AGS Admin Portal (IAM > OAuth Clients)
ClientId=
; Client secret (leave blank for public clients)
ClientSecret=
; Game namespace from AGS Admin Portal
Namespace=
; Publisher namespace (leave blank unless required)
PublisherNamespace=
; Redirect URI for OAuth (example: http://127.0.0.1)
RedirectURI="http://127.0.0.1"
; Base URL - Example: https://<StudioID>-<GameTitleID>.prod.gamingservices.accelbyte.io
BaseUrl=
; App ID - Required for Steam; leave blank otherwise
AppId=
"""


def _write_default_accelbyte_config(project_root: Path, module_name: str, changes: list) -> None:
    """Add default AccelByte config keys to Config/DefaultEngine.ini."""
    config_dir = project_root / "Config"
    config_path = config_dir / "DefaultEngine.ini"
    section = f"[/Script/{module_name}.AccelByteSettings]"
    accelbyte_block = _get_default_accelbyte_config_block(module_name)

    if not config_path.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        online_subsystem = (
            "[OnlineSubsystem]\n"
            "; Use AccelByte as the default online platform\n"
            "DefaultPlatformService=AccelByte\n"
        )
        config_path.write_text(online_subsystem.rstrip() + accelbyte_block, encoding="utf-8")
        changes.append(
            "Created Config/DefaultEngine.ini with [OnlineSubsystem] and default AccelByte "
            "config keys (blank values; fill in your AGS credentials)."
        )
        return

    content = config_path.read_text(encoding="utf-8")
    if section in content:
        changes.append(
            "Config/DefaultEngine.ini already contained AccelByte config section; "
            "skipped adding default keys."
        )
        return

    online_subsystem_section = "[OnlineSubsystem]"
    default_platform_line = "DefaultPlatformService=AccelByte"
    new_content = content
    if online_subsystem_section in content and default_platform_line not in content:
        insert_idx = content.index(online_subsystem_section) + len(online_subsystem_section)
        new_content = content[:insert_idx] + "\nDefaultPlatformService=AccelByte" + content[insert_idx:]
    elif online_subsystem_section not in content:
        new_content = content.rstrip() + "\n\n[OnlineSubsystem]\nDefaultPlatformService=AccelByte\n"

    trimmed = new_content.rstrip()
    config_path.write_text(trimmed + accelbyte_block, encoding="utf-8")
    changes.append(
        "Added default AccelByte config keys to Config/DefaultEngine.ini "
        "(blank values; fill in ClientId, Namespace, BaseUrl, etc.)."
    )


def _patch_one_module(
    project_root: Path, uproject_path: Path, module_name: str, changes: list
) -> None:
    """Add one module to .uproject Plugins array and to Build.cs and Target.cs."""
    try:
        uproject_content = uproject_path.read_text(encoding="utf-8")
        uproject = json.loads(uproject_content)
        if not isinstance(uproject.get("Plugins"), list):
            uproject["Plugins"] = []
        has_plugin = any(
            (p.get("Name") or p.get("name")) == module_name for p in uproject["Plugins"]
        )
        if not has_plugin:
            uproject["Plugins"].append({"Name": module_name, "Enabled": True})
            uproject_path.write_text(json.dumps(uproject, indent=2), encoding="utf-8")
            changes.append(f'Added "{module_name}" to .uproject Plugins array')
        else:
            changes.append(f'.uproject already contained "{module_name}"')
    except Exception as e:
        raise RuntimeError(
            f'Failed to update .uproject: {e}. '
            f'Add "{module_name}" to the Plugins array manually.'
        )

    source_dir = project_root / "Source"
    if not source_dir.exists():
        changes.append(
            "No Source/ directory; skip Build.cs and Target.cs (add module manually if needed)."
        )
        return

    project_name = uproject_path.stem
    build_cs_path = source_dir / project_name / f"{project_name}.Build.cs"
    if build_cs_path.exists():
        build_content = build_cs_path.read_text(encoding="utf-8")
        if f'"{module_name}"' not in build_content:
            new_content = re.sub(
                r"(PublicDependencyModuleNames\.AddRange\s*\(\s*new\s+string\[\]\s*\{)",
                lambda m: f'{m.group(0)} "{module_name}",',
                build_content,
            )
            if new_content != build_content:
                build_cs_path.write_text(new_content, encoding="utf-8")
                changes.append(
                    f'Added "{module_name}" to {project_name}.Build.cs PublicDependencyModuleNames'
                )
            else:
                idx = build_content.find("PublicDependencyModuleNames.AddRange")
                if idx != -1:
                    end = build_content.find("});", idx)
                    insert_idx = end if end != -1 else len(build_content)
                    patched = (
                        build_content[:insert_idx]
                        + f' "{module_name}",'
                        + build_content[insert_idx:]
                    )
                    build_cs_path.write_text(patched, encoding="utf-8")
                    changes.append(
                        f'Added "{module_name}" to {project_name}.Build.cs PublicDependencyModuleNames'
                    )
                else:
                    changes.append(
                        f'Could not patch Build.cs; add PublicDependencyModuleNames.Add("{module_name}") manually.'
                    )
        else:
            changes.append(f'Build.cs already contained "{module_name}"')
    else:
        changes.append(
            f"Build.cs not found at {build_cs_path}; "
            f'add PublicDependencyModuleNames.Add("{module_name}") manually.'
        )

    target_files = [e for e in source_dir.iterdir() if e.name.endswith(".Target.cs")]
    for target_file in target_files:
        target_content = target_file.read_text(encoding="utf-8")
        if f'"{module_name}"' in target_content:
            changes.append(f'{target_file.name} already contained "{module_name}"')
        else:
            add_range_regex = re.compile(
                r"(ExtraModuleNames\s*\.\s*AddRange\s*\(\s*new\s+string\[\]\s*\{)"
            )
            patched = add_range_regex.sub(
                lambda m: f'{m.group(0)} "{module_name}",', target_content
            )
            if patched != target_content:
                target_file.write_text(patched, encoding="utf-8")
                changes.append(f'Added "{module_name}" to {target_file.name} ExtraModuleNames')
            else:
                last_extra = target_content.rfind("ExtraModuleNames")
                if last_extra != -1:
                    line_end = target_content.find("\n", last_extra)
                    insert_at = (line_end + 1) if line_end != -1 else last_extra
                    patched = (
                        target_content[:insert_at]
                        + f'\t\tExtraModuleNames.Add("{module_name}");\n'
                        + target_content[insert_at:]
                    )
                    target_file.write_text(patched, encoding="utf-8")
                    changes.append(f'Added "{module_name}" to {target_file.name} ExtraModuleNames')
                else:
                    changes.append(
                        f'Could not patch {target_file.name}; '
                        f'add ExtraModuleNames.Add("{module_name}") manually.'
                    )


def _patch_project_files(
    project_root: Path,
    uproject_path: Path,
    module_names: list,
    add_default_config_module_name: str | None = None,
    ensure_online_subsystem: bool = False,
) -> list:
    """Add plugins to .uproject, Build.cs, Target.cs; optionally add default AccelByte config."""
    changes: list = []

    for module_name in module_names:
        _patch_one_module(project_root, uproject_path, module_name, changes)

    if ensure_online_subsystem:
        _ensure_online_subsystem_config(project_root, changes)

    if add_default_config_module_name:
        _write_default_accelbyte_config(project_root, add_default_config_module_name, changes)

    return changes


# ---------------------------------------------------------------------------
# Project file regeneration
# ---------------------------------------------------------------------------

def _read_engine_association(uproject_path: Path) -> str | None:
    try:
        data = json.loads(uproject_path.read_text(encoding="utf-8"))
        return data.get("EngineAssociation")
    except Exception:
        return None


def _engine_association_to_folder_name(engine_association: str | None) -> str | None:
    if not engine_association or not isinstance(engine_association, str):
        return None
    m = re.match(r"^(\d+)\.(\d+)", engine_association)
    if not m:
        return None
    return f"UE_{m.group(1)}.{m.group(2)}"


def _find_unreal_version_selector(engine_association: str | None) -> Path | None:
    folder_name = _engine_association_to_folder_name(engine_association)
    platform = sys.platform

    if platform == "win32":
        epic_base = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Epic Games"
        if not epic_base.exists():
            return None
        candidates = [folder_name] if folder_name else []
        if not folder_name or not (epic_base / folder_name).exists():
            dirs = [
                d.name
                for d in epic_base.iterdir()
                if d.is_dir() and d.name.startswith("UE_")
            ]
            candidates += dirs
        for name in candidates:
            exe = epic_base / name / "Engine" / "Binaries" / "UnrealVersionSelector.exe"
            if exe.exists():
                return exe
        return None

    if platform == "darwin":
        epic_base = Path("/Users/Shared/Epic Games")
        if not epic_base.exists():
            return None
        candidates = [folder_name] if folder_name else []
        if not folder_name or not (epic_base / folder_name).exists():
            dirs = [
                d.name
                for d in epic_base.iterdir()
                if d.is_dir() and d.name.startswith("UE_")
            ]
            candidates += dirs
        for name in candidates:
            exe = epic_base / name / "Engine" / "Build" / "BatchFiles" / "Mac" / "GenerateProjectFiles.sh"
            if exe.exists():
                return exe
        return None

    return None


def _regenerate_project_files(uproject_path: Path) -> dict:
    """Run UnrealVersionSelector / GenerateProjectFiles to regenerate .sln/.vcxproj."""
    engine_association = _read_engine_association(uproject_path)
    selector_path = _find_unreal_version_selector(engine_association)
    platform = sys.platform

    if (
        platform == "win32"
        and selector_path
        and selector_path.name == "UnrealVersionSelector.exe"
    ):
        try:
            subprocess.run(
                [str(selector_path), "/projectfiles", str(uproject_path)],
                capture_output=True,
                timeout=REGENERATE_TIMEOUT_MS / 1000,
                check=True,
            )
            return {
                "success": True,
                "message": "Project files regenerated successfully (UnrealVersionSelector).",
            }
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr.decode(errors="replace") if e.stderr else str(e))[:500]
            return {
                "success": False,
                "message": f"Regenerate project files failed: {e}. Run UnrealVersionSelector /projectfiles manually.",
                "stderr": stderr,
            }

    if platform == "darwin" and selector_path:
        try:
            subprocess.run(
                [str(selector_path), f"-project={uproject_path}", "-game", "-engine"],
                capture_output=True,
                timeout=REGENERATE_TIMEOUT_MS / 1000,
                cwd=str(selector_path.parent),
                check=True,
            )
            return {
                "success": True,
                "message": "Project files regenerated successfully (GenerateProjectFiles).",
            }
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr.decode(errors="replace") if e.stderr else str(e))[:500]
            return {
                "success": False,
                "message": f"Regenerate project files failed: {e}. Run GenerateProjectFiles.sh from the Engine folder manually.",
                "stderr": stderr,
            }

    return {
        "success": False,
        "message": (
            "UnrealVersionSelector (or GenerateProjectFiles) not found. "
            f"EngineAssociation in .uproject: {engine_association or '(missing)'}. "
            "Regenerate project files from the .uproject context menu or from the Engine folder."
        ),
    }


# ---------------------------------------------------------------------------
# Download and install one component
# ---------------------------------------------------------------------------

async def _download_and_install_one(
    repo: str, source: str, version: str | None, project_root: Path
) -> dict:
    if source == "git":
        source_plugin_dir = _clone_git(repo, version)
    else:
        try:
            source_plugin_dir = await _download_release_zip(repo, version)
        except RuntimeError as e:
            is_no_zip = "No ZIP asset" in str(e) or "No ZIP" in str(e)
            if is_no_zip:
                source_plugin_dir = _clone_git(repo, version)
            else:
                raise

    module_name: str | None = None
    try:
        module_name = _get_plugin_module_name(source_plugin_dir)
    except RuntimeError:
        module_name = None

    installed_path, plugin_folder_name = _install_plugin(
        source_plugin_dir, project_root, module_name
    )

    if not module_name:
        module_name = _get_plugin_module_name(installed_path)

    return {
        "installedPath": str(installed_path),
        "pluginFolderName": plugin_folder_name,
        "moduleName": module_name,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def install_unreal_sdk(params: dict) -> dict:
    """
    Download (release or git), install, and optionally setup project files.

    params:
        projectPath: Required. Unreal project root.
        workspaceRoot: Optional. Workspace root for resolving relative projectPath.
        components: Optional. List of ["sdk", "oss", "networkUtilities"]. Default ["sdk"].
        source: "release" (default) or "git".
        version: Optional tag/branch.
        setupProjectFiles: If True, patch .uproject and Build/Target files.
        regenerateProjectFiles: If True, run UnrealVersionSelector to regenerate project files.
    """
    if not params:
        params = {}

    project_path = params.get("projectPath", "")
    workspace_root = params.get("workspaceRoot")
    requested_components = params.get("components") or ["sdk"]
    source = params.get("source", "release")
    version = params.get("version")
    setup_project_files = bool(params.get("setupProjectFiles", False))
    do_regenerate = bool(params.get("regenerateProjectFiles", False))

    components = requested_components if (isinstance(requested_components, list) and requested_components) else ["sdk"]
    to_install = [c for c in INSTALL_ORDER if c in components]

    if not to_install:
        return {
            "success": False,
            "message": (
                f"components must include at least one of: sdk, oss, networkUtilities. "
                f"Got: {json.dumps(components)}"
            ),
        }

    if not project_path or not isinstance(project_path, str):
        return {
            "success": False,
            "message": (
                "projectPath is required and must be a string "
                "(Unreal project root containing a .uproject file)."
            ),
        }

    try:
        project_root, uproject_path, _uproject_name = _validate_project_path(
            project_path, workspace_root
        )
    except RuntimeError as e:
        return {"success": False, "message": str(e)}

    installed = []
    for component_id in to_install:
        config = SDK_COMPONENTS.get(component_id)
        if not config:
            continue
        try:
            one = await _download_and_install_one(config["repo"], source, version, project_root)
            installed.append({**one, "addDefaultConfig": config["addDefaultConfig"], "componentId": component_id})
        except RuntimeError as e:
            return {"success": False, "message": f"Failed to install {component_id}: {e}"}

    installed_paths = [i["installedPath"] for i in installed]
    module_names = [i["moduleName"] for i in installed]
    sdk_item = next((i for i in installed if i.get("addDefaultConfig")), None)
    add_default_config_module_name = sdk_item["moduleName"] if sdk_item else None
    ensure_online_subsystem = "oss" in components and "sdk" not in components

    setup_details: list | None = None
    if setup_project_files:
        try:
            setup_details = _patch_project_files(
                project_root,
                uproject_path,
                module_names,
                add_default_config_module_name=add_default_config_module_name,
                ensure_online_subsystem=ensure_online_subsystem,
            )
        except RuntimeError as e:
            return {
                "success": True,
                "installedPaths": installed_paths,
                "message": (
                    f"Plugins installed at {', '.join(installed_paths)}. "
                    f"Setup failed: {e}. "
                    "Add plugins and modules manually (see AccelByte Unreal SDK install docs)."
                ),
                "setupDetails": [],
            }

    regenerate_result: dict | None = None
    if do_regenerate:
        regenerate_result = _regenerate_project_files(uproject_path)
        if setup_details is not None and regenerate_result["success"]:
            setup_details.append(regenerate_result["message"])

    next_steps = (
        "Configure DefaultEngine.ini with your AGS credentials "
        "(see https://docs.accelbyte.io/gaming-services/getting-started/setup-game-sdk/unreal-sdk)."
    )
    names = ", ".join(i["pluginFolderName"] for i in installed)
    if setup_project_files:
        message = f"Installed {names} and updated project files. {next_steps}"
    else:
        message = f"Installed {names}. Add the plugins to .uproject and Build.cs/Target.cs, then {next_steps}"

    if do_regenerate and regenerate_result:
        if regenerate_result["success"]:
            message += " Project files regenerated."
        else:
            message += f" Regenerate: {regenerate_result['message']}"

    result: dict = {
        "success": True,
        "installedPaths": installed_paths,
        "message": message,
    }
    if setup_details is not None:
        result["setupDetails"] = setup_details
    if regenerate_result is not None:
        result["regenerateResult"] = regenerate_result

    return result
