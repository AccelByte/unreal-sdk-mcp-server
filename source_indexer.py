"""
Source code indexer for AccelByte Unreal ByteWars tutorial modules.
Indexes C++ files, extracts code snippets, and indexes example components.
Python translation of sourceIndexer.js.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

GITHUB_REPO_URL = "https://github.com/AccelByte/accelbyte-unreal-bytewars-game.git"
REPO_NAME = "accelbyte-unreal-bytewars-game"
REPO_BRANCH = "tutorialmodules"

# ---------------------------------------------------------------------------
# Repository cloning
# ---------------------------------------------------------------------------

def ensure_repository_cloned(base_dir: Path, repo_url: str = GITHUB_REPO_URL) -> Path:
    """Ensure the GitHub repository is cloned and up-to-date. Returns the repo root path."""
    print(f"Ensuring cache directory exists: {base_dir}", file=sys.stderr)
    base_dir.mkdir(parents=True, exist_ok=True)

    repo_path = base_dir / REPO_NAME
    print(f"Repository path: {repo_path}", file=sys.stderr)

    if not repo_path.exists():
        print(f"Repository not found. Cloning from {repo_url}...", file=sys.stderr)
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "Git is not available. Please install Git to enable source code indexing."
            )

        try:
            subprocess.run(
                [
                    "git", "clone", "--depth", "1",
                    "--branch", REPO_BRANCH,
                    repo_url, str(repo_path),
                ],
                cwd=str(base_dir),
                timeout=60,
                check=True,
            )
            print(f"Repository cloned successfully to {repo_path}", file=sys.stderr)
        except subprocess.CalledProcessError as e:
            msg = (
                f"Failed to clone repository: {e}. "
                "Make sure Git is installed and the repository URL is accessible."
            )
            print(f"ERROR: {msg}", file=sys.stderr)
            raise RuntimeError(msg)
    else:
        print(f"Repository already exists at {repo_path}", file=sys.stderr)
        git_dir = repo_path / ".git"
        if git_dir.exists():
            try:
                print(f"Updating repository at {repo_path}...", file=sys.stderr)
                subprocess.run(
                    ["git", "fetch", "origin", REPO_BRANCH],
                    cwd=str(repo_path), capture_output=True, timeout=30, check=True,
                )
                subprocess.run(
                    ["git", "reset", "--hard", f"origin/{REPO_BRANCH}"],
                    cwd=str(repo_path), capture_output=True, check=True,
                )
                print("Repository updated successfully", file=sys.stderr)
            except Exception as e:
                print(
                    f"Warning: Could not update repository: {e}. Using existing files.",
                    file=sys.stderr,
                )
        else:
            print(
                f"Warning: {repo_path} exists but is not a git repository. Using existing files.",
                file=sys.stderr,
            )

    source_dir = repo_path / "Source" / "AccelByteWars" / "TutorialModules"
    if not source_dir.exists():
        raise RuntimeError(
            f"Repository structure is incorrect. Expected Source/AccelByteWars/TutorialModules "
            f"directory not found at: {source_dir}"
        )

    return repo_path


# ---------------------------------------------------------------------------
# Source index cache helpers
# ---------------------------------------------------------------------------

def _get_source_index_cache_file(base_dir: Path) -> Path:
    return base_dir / ".cache" / "source-index.json"


def _save_source_index_cache(base_dir: Path, source_index: dict) -> None:
    try:
        cache_file = _get_source_index_cache_file(base_dir)
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "version": "1.0",
            "indexedAt": datetime.now(timezone.utc).isoformat(),
            "fileCount": len(source_index.get("files", {})),
            "classCount": len(source_index.get("classes", {})),
            "methodCount": len(source_index.get("methods", {})),
            "index": source_index,
        }

        cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        print(f"Source index cache saved to: {cache_file}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to save source index cache: {e}", file=sys.stderr)


def _load_source_index_cache(base_dir: Path) -> dict | None:
    try:
        cache_file = _get_source_index_cache_file(base_dir)
        if not cache_file.exists():
            return None

        cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        print(
            f"Source index cache loaded from: {cache_file} "
            f"({cache_data.get('fileCount', 0)} files, "
            f"{cache_data.get('classCount', 0)} classes, "
            f"{cache_data.get('methodCount', 0)} methods)",
            file=sys.stderr,
        )
        return cache_data.get("index")
    except Exception as e:
        print(f"Failed to load source index cache: {e}", file=sys.stderr)
        return None


def _is_source_index_cache_valid(base_dir: Path) -> bool:
    try:
        cache_file = _get_source_index_cache_file(base_dir)
        repo_path = base_dir.parent / ".cache" / REPO_NAME
        tutorial_modules_dir = repo_path / "Source" / "AccelByteWars" / "TutorialModules"

        if not cache_file.exists() or not tutorial_modules_dir.exists():
            return False

        cache_time = cache_file.stat().st_mtime

        for src_file in tutorial_modules_dir.rglob("*"):
            if src_file.is_file() and src_file.suffix in (".h", ".cpp"):
                if src_file.stat().st_mtime > cache_time:
                    return False

        return True
    except Exception as e:
        print(f"Error checking source index cache validity: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# C++ metadata extraction helpers
# ---------------------------------------------------------------------------

_CLASS_REGEX = re.compile(r"(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_:]*)")
_METHOD_REGEX = re.compile(
    r"(?:^|\s)([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)(?:\s*const)?\s*\{", re.MULTILINE
)
_INCLUDE_REGEX = re.compile(r'#include\s+[<"]([^>"]+)[>"]')
_NAMESPACE_REGEX = re.compile(r"namespace\s+([A-Za-z_][A-Za-z0-9_]*)")

_KEYWORD_FILTER = {"if", "for", "while", "switch", "return", "const", "virtual", "static"}


def _extract_code_metadata(content: str, filename: str) -> dict:
    metadata = {"classes": [], "methods": [], "includes": [], "namespaces": []}

    seen_classes: set = set()
    for m in _CLASS_REGEX.finditer(content):
        cls = m.group(1)
        if cls and cls not in seen_classes:
            metadata["classes"].append(cls)
            seen_classes.add(cls)

    seen_methods: set = set()
    for m in _METHOD_REGEX.finditer(content):
        method = m.group(1)
        if method and method not in _KEYWORD_FILTER and method not in seen_methods:
            metadata["methods"].append(method)
            seen_methods.add(method)

    for m in _INCLUDE_REGEX.finditer(content):
        metadata["includes"].append(m.group(1))

    for m in _NAMESPACE_REGEX.finditer(content):
        metadata["namespaces"].append(m.group(1))

    return metadata


def _extract_relevant_snippets(content: str, filename: str) -> dict:
    snippets: dict = {"classDefinition": "", "keyMethods": []}

    class_def_match = re.search(r"(?:class|struct)[^{]+\{[^}]*\{", content, re.DOTALL)
    if class_def_match:
        snippets["classDefinition"] = class_def_match.group(0)[:500]

    key_method_names = [
        "LoginWithDeviceId",
        "GetUserRecord",
        "CreateAccelByteInstance",
        "GetUserApi",
        "GetCloudSaveApi",
    ]

    for method_name in key_method_names:
        pattern = re.compile(
            rf"({re.escape(method_name)}\s*[^{{]*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}})",
            re.DOTALL,
        )
        method_match = pattern.search(content)
        if method_match:
            snippets["keyMethods"].append({
                "name": method_name,
                "snippet": method_match.group(0)[:1000],
            })

    return snippets


# ---------------------------------------------------------------------------
# Source index build / load
# ---------------------------------------------------------------------------

def _build_source_index(repo_root: Path, base_dir: Path) -> dict:
    source_index: dict = {"files": {}, "methods": {}, "classes": {}}
    tutorial_modules_dir = repo_root / "Source" / "AccelByteWars" / "TutorialModules"

    print(f"Looking for source directory:", file=sys.stderr)
    print(
        f"  TutorialModules: {tutorial_modules_dir} (exists: {tutorial_modules_dir.exists()})",
        file=sys.stderr,
    )

    def scan_directory(directory: Path, rel_prefix: str = "") -> None:
        if not directory.exists():
            print(f"Directory does not exist: {directory}", file=sys.stderr)
            return

        for entry in sorted(directory.iterdir()):
            rel_path = str(Path(rel_prefix) / entry.name) if rel_prefix else entry.name

            if entry.is_dir():
                scan_directory(entry, rel_path)
            elif entry.is_file() and entry.suffix in (".h", ".cpp"):
                file_content = entry.read_text(encoding="utf-8", errors="replace")
                file_type = "header" if entry.suffix == ".h" else "implementation"
                metadata = _extract_code_metadata(file_content, entry.name)

                source_index["files"][rel_path] = {
                    "path": rel_path,
                    "fullPath": str(entry),
                    "type": file_type,
                    "size": len(file_content),
                    "lines": file_content.count("\n") + 1,
                    "content": file_content,
                    "metadata": metadata,
                    "snippets": _extract_relevant_snippets(file_content, entry.name),
                }

                for class_name in metadata.get("classes", []):
                    if not class_name or not isinstance(class_name, str):
                        continue
                    if not isinstance(source_index["classes"].get(class_name), list):
                        source_index["classes"][class_name] = []
                    if rel_path not in source_index["classes"][class_name]:
                        source_index["classes"][class_name].append(rel_path)

                for method_name in metadata.get("methods", []):
                    if not method_name or not isinstance(method_name, str):
                        continue
                    if not isinstance(source_index["methods"].get(method_name), list):
                        source_index["methods"][method_name] = []
                    if rel_path not in source_index["methods"][method_name]:
                        source_index["methods"][method_name].append(rel_path)

    if tutorial_modules_dir.exists():
        print(f"Scanning TutorialModules directory: {tutorial_modules_dir}", file=sys.stderr)
        scan_directory(tutorial_modules_dir, "")
    else:
        error_msg = (
            f"TutorialModules directory not found: {tutorial_modules_dir}. "
            "Repository may not be cloned correctly."
        )
        print(f"ERROR: {error_msg}", file=sys.stderr)
        raise RuntimeError(error_msg)

    if not source_index["files"]:
        raise RuntimeError(
            "No source files were indexed. Check that the repository structure is correct."
        )

    _save_source_index_cache(base_dir, source_index)
    return source_index


def generate_source_index_cache(base_dir: Path) -> dict:
    """Generate source index cache (force regeneration, ignores existing cache)."""
    print("Generating source index cache...", file=sys.stderr)

    try:
        repo_root = ensure_repository_cloned(base_dir, GITHUB_REPO_URL)
        print(f"Repository root resolved to: {repo_root}", file=sys.stderr)
    except Exception as e:
        raise RuntimeError(f"Failed to ensure repository is cloned: {e}")

    if not repo_root.exists():
        raise RuntimeError(f"Repository root does not exist: {repo_root}")

    return _build_source_index(repo_root, base_dir)


def index_source_files(base_dir: Path, use_cache: bool = True, load_only: bool = False) -> dict:
    """Index C++ source files. Clones repo from GitHub if not present. Uses cache if available."""
    print(
        f"index_source_files called with base_dir: {base_dir}, "
        f"use_cache: {use_cache}, load_only: {load_only}",
        file=sys.stderr,
    )

    if use_cache and _is_source_index_cache_valid(base_dir):
        cached = _load_source_index_cache(base_dir)
        if cached:
            print("Using cached source index", file=sys.stderr)
            return cached

    if load_only:
        raise RuntimeError(
            "Source index cache not found. Run 'python generate_cache.py' to generate cache files."
        )

    if use_cache:
        print("Cache is invalid or missing, re-indexing source files...", file=sys.stderr)

    try:
        repo_root = ensure_repository_cloned(base_dir, GITHUB_REPO_URL)
        print(f"Repository root resolved to: {repo_root}", file=sys.stderr)
    except Exception as e:
        raise RuntimeError(f"Failed to ensure repository is cloned: {e}")

    if not repo_root.exists():
        raise RuntimeError(f"Repository root does not exist: {repo_root}")

    return _build_source_index(repo_root, base_dir)


def search_source_files(source_index: dict, query: str) -> list:
    """Find source files by class name, method name, or file path pattern."""
    results = []

    if query in source_index.get("classes", {}):
        for file_path in source_index["classes"][query]:
            file_data = source_index["files"].get(file_path, {})
            results.append({"type": "class", "match": query, "file": file_path, **file_data})

    if query in source_index.get("methods", {}):
        for file_path in source_index["methods"][query]:
            file_data = source_index["files"].get(file_path, {})
            results.append({"type": "method", "match": query, "file": file_path, **file_data})

    for file_path in source_index.get("files", {}):
        if query in file_path or file_path.endswith(query):
            file_data = source_index["files"][file_path]
            results.append({"type": "file", "match": query, "file": file_path, **file_data})

    return results


def _get_method_context(content: str, method_name: str) -> str:
    lines = content.split("\n")
    method_line_idx = next(
        (i for i, line in enumerate(lines) if method_name in line and "(" in line),
        -1,
    )
    if method_line_idx == -1:
        return ""
    start = max(0, method_line_idx - 20)
    end = min(len(lines), method_line_idx + 50)
    return "\n".join(lines[start:end])


def get_method_implementation(source_index: dict, class_name: str, method_name: str) -> dict | None:
    """Get implementation of a specific method from source code."""
    files = source_index.get("classes", {}).get(class_name, [])

    for file_path in files:
        file_data = source_index["files"].get(file_path)
        if not file_data:
            continue

        pattern = re.compile(
            rf"({re.escape(method_name)}\s*[^{{]*\{{[^}}]*\}})",
            re.DOTALL,
        )
        m = pattern.search(file_data["content"])
        if m:
            return {
                "file": file_path,
                "className": class_name,
                "methodName": method_name,
                "implementation": m.group(0),
                "context": _get_method_context(file_data["content"], method_name),
            }

    return None


# ---------------------------------------------------------------------------
# Snippet index cache helpers
# ---------------------------------------------------------------------------

def _get_snippet_cache_file(base_dir: Path) -> Path:
    return base_dir / ".cache" / "bytewars-snippets.json"


def _save_snippet_index(base_dir: Path, snippet_index: dict) -> None:
    try:
        cache_file = _get_snippet_cache_file(base_dir)
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "version": "1.0",
            "indexedAt": datetime.now(timezone.utc).isoformat(),
            "snippetCount": len(snippet_index.get("snippets", {})),
            "index": snippet_index,
        }

        cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        print(f"Snippet index saved to: {cache_file}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to save snippet index: {e}", file=sys.stderr)


def _load_snippet_index(base_dir: Path) -> dict | None:
    try:
        cache_file = _get_snippet_cache_file(base_dir)
        if not cache_file.exists():
            return None

        cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        print(
            f"Snippet index loaded from cache: {cache_data.get('snippetCount', 0)} snippets",
            file=sys.stderr,
        )
        return cache_data.get("index")
    except Exception as e:
        print(f"Failed to load snippet index from cache: {e}", file=sys.stderr)
        return None


def _is_snippet_cache_valid(base_dir: Path) -> bool:
    try:
        cache_file = _get_snippet_cache_file(base_dir)
        snippets_dir = base_dir / "data" / "bytewars-snippets"

        if not cache_file.exists() or not snippets_dir.exists():
            return False

        cache_time = cache_file.stat().st_mtime

        for src_file in snippets_dir.rglob("*"):
            if src_file.is_file() and src_file.suffix in (".h", ".cpp"):
                if src_file.stat().st_mtime > cache_time:
                    return False

        return True
    except Exception as e:
        print(f"Error checking cache validity: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Area / ID helpers
# ---------------------------------------------------------------------------

_AREA_MAP = {
    "Access": "access",
    "AuthEssentials": "auth",
    "Social": "social",
    "Play": "play",
    "PartyEssentials": "party",
    "SessionEssentials": "session",
    "MatchmakingEssentials": "matchmaking",
    "MatchmakingDS": "matchmaking",
    "MatchmakingP2P": "matchmaking",
    "MatchSessionDS": "matchmaking",
    "MatchSessionEssentials": "matchmaking",
    "MatchSessionP2P": "matchmaking",
    "FriendsEssentials": "friends",
    "ChatEssentials": "chat",
    "SessionChat": "chat",
    "PrivateChat": "chat",
    "PresenceEssentials": "presence",
    "RecentPlayers": "recent-players",
    "Storage": "storage",
    "CloudSaveEssentials": "cloudsave",
    "StatisticsEssentials": "statistics",
    "Monetization": "monetization",
    "EntitlementsEssentials": "entitlements",
    "InGameStoreEssentials": "store",
    "InGameStoreDisplays": "store",
    "StoreItemPurchase": "store",
    "WalletEssentials": "wallet",
    "Engagement": "engagement",
    "ChallengeEssentials": "challenge",
    "LeaderboardEssentials": "leaderboard",
    "PeriodicLeaderboard": "leaderboard",
    "GameTelemetry": "telemetry",
    "TutorialModuleUtilities": "utilities",
    "GameSessionEssentials": "session",
    "CustomMatch": "matchmaking",
    "MultiplayerDSEssentials": "multiplayer",
    "PlayingWithFriends": "social",
    "PlayingWithParty": "party",
    "OnlineSettings": "settings",
    "CrossplayPreference": "settings",
    "RegionPreferences": "settings",
    "RegionPreferencesEssentials": "settings",
    "NativePlatformPurchase": "monetization",
}


def _extract_area_from_path(relative_path: str, file_name: str) -> str:
    normalized = relative_path.replace("\\", "/")
    for part in normalized.split("/"):
        if part in _AREA_MAP:
            return _AREA_MAP[part]

    fn_lower = file_name.lower()
    if "auth" in fn_lower or "login" in fn_lower:
        return "auth"
    if "party" in fn_lower:
        return "party"
    if "session" in fn_lower:
        return "session"
    if "chat" in fn_lower:
        return "chat"
    if "friend" in fn_lower:
        return "friends"
    if "cloudsave" in fn_lower:
        return "cloudsave"
    if "stat" in fn_lower:
        return "statistics"
    if "store" in fn_lower:
        return "store"
    if "wallet" in fn_lower:
        return "wallet"
    if "leaderboard" in fn_lower:
        return "leaderboard"
    if "matchmaking" in fn_lower:
        return "matchmaking"
    if "presence" in fn_lower:
        return "presence"

    return "general"


def _generate_snippet_id(area: str, function_name: str, file_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "-", function_name.lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")

    if not normalized or normalized in ("public", "private", "protected"):
        file_base = re.sub(r"\.(cpp|h)$", "", file_name, flags=re.IGNORECASE).lower()
        return f"oss/{area}/{file_base}"

    return f"oss/{area}/{normalized}"


# ---------------------------------------------------------------------------
# Snippet metadata extraction
# ---------------------------------------------------------------------------

_FUNC_CALL_REGEX = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_FUNC_CALL_SKIP = {
    "if", "for", "while", "switch", "return", "ensure", "Cast", "StaticCast"
}


def _extract_snippet_metadata(content: str, file_path: str, area: str, function_name: str) -> dict:
    metadata: dict = {
        "tags": [],
        "uses": [],
        "symbols": {
            "classes": [],
            "methods": [],
            "functions": [],
            "includes": [],
        },
    }

    metadata["tags"].append(area)

    fn_lower = function_name.lower()
    content_lower = content.lower()

    if "login" in fn_lower or "login" in content_lower:
        metadata["tags"] += ["login", "authentication"]
    if "logout" in fn_lower or "logout" in content_lower:
        metadata["tags"] += ["logout", "authentication"]
    if "auth" in fn_lower or "identity" in content_lower:
        metadata["tags"].append("authentication")
    if "party" in fn_lower or "party" in content_lower:
        metadata["tags"] += ["party", "multiplayer"]
    if "session" in fn_lower or "gamesession" in content_lower:
        metadata["tags"] += ["session", "multiplayer"]
    if "chat" in fn_lower or "chat" in content_lower:
        metadata["tags"] += ["chat", "messaging"]
    if "friend" in fn_lower or "friend" in content_lower:
        metadata["tags"] += ["friends", "social"]
    if "presence" in fn_lower or "presence" in content_lower:
        metadata["tags"] += ["presence", "social"]
    if "cloudsave" in fn_lower or "cloudsave" in content_lower or "playerrecord" in content_lower:
        metadata["tags"] += ["cloudsave", "storage"]
    if "stat" in fn_lower or "statistic" in content_lower:
        metadata["tags"] += ["statistics", "storage"]
    if "store" in fn_lower or "store" in content_lower or "item" in content_lower:
        metadata["tags"] += ["store", "monetization"]
    if "wallet" in fn_lower or "wallet" in content_lower:
        metadata["tags"] += ["wallet", "monetization"]
    if "leaderboard" in fn_lower or "leaderboard" in content_lower:
        metadata["tags"] += ["leaderboard", "engagement"]
    if "matchmaking" in fn_lower or "matchmaking" in content_lower:
        metadata["tags"] += ["matchmaking", "multiplayer"]
    if "initialize" in fn_lower or "init" in fn_lower:
        metadata["tags"].append("initialization")
    if "deinitialize" in fn_lower or "deinit" in fn_lower:
        metadata["tags"].append("cleanup")
    if "query" in fn_lower or "query" in content_lower:
        metadata["tags"].append("query")
    if "update" in fn_lower or "update" in content_lower:
        metadata["tags"].append("update")
    if "get" in fn_lower or "retrieve" in fn_lower:
        metadata["tags"].append("getter")
    if "set" in fn_lower or "save" in fn_lower:
        metadata["tags"].append("setter")
    if "send" in fn_lower or "send" in content_lower:
        metadata["tags"].append("send")
    if "receive" in fn_lower or "receive" in content_lower or "on" in content_lower:
        metadata["tags"] += ["receive", "callback"]

    file_basename = Path(file_path).name
    code_meta = _extract_code_metadata(content, file_basename)
    metadata["symbols"]["classes"] = code_meta["classes"]
    metadata["symbols"]["methods"] = code_meta["methods"]
    metadata["symbols"]["includes"] = code_meta["includes"]
    metadata["symbols"]["namespaces"] = code_meta.get("namespaces", [])

    seen_calls: set = set()
    for m in _FUNC_CALL_REGEX.finditer(content):
        func = m.group(1)
        if func and func not in _FUNC_CALL_SKIP and func not in seen_calls:
            metadata["symbols"]["functions"].append(func)
            seen_calls.add(func)

    includes = metadata["symbols"]["includes"]
    if any("Identity" in inc for inc in includes):
        metadata["uses"].append("authentication")
    if any("Session" in inc for inc in includes):
        metadata["uses"].append("session-management")
    if any("Chat" in inc for inc in includes):
        metadata["uses"].append("chat")
    if any("Party" in inc for inc in includes):
        metadata["uses"].append("party")
    if any("CloudSave" in inc for inc in includes):
        metadata["uses"].append("cloud-save")
    if any("Statistic" in inc for inc in includes):
        metadata["uses"].append("statistics")

    # Deduplicate (preserving order)
    metadata["tags"] = list(dict.fromkeys(metadata["tags"]))
    metadata["uses"] = list(dict.fromkeys(metadata["uses"]))

    return metadata


# ---------------------------------------------------------------------------
# Snippet extraction
# ---------------------------------------------------------------------------

def _save_snippet(
    snippet_info: dict,
    content: str,
    file_path: str,
    relative_path: str,
    snippet_index: dict,
) -> None:
    if not content.strip():
        return

    name_parts = snippet_info["name"].split("-")
    file_part = name_parts[0]
    function_part = "-".join(name_parts[1:])

    area = _extract_area_from_path(relative_path, file_part)

    snippet_id = _generate_snippet_id(area, function_part, file_part)
    base_id = snippet_id
    counter = 1
    while snippet_id in snippet_index["snippets"]:
        snippet_id = f"{base_id}-{counter}"
        counter += 1

    uri = f"snippet://{snippet_id}"
    metadata = _extract_snippet_metadata(content, relative_path, area, function_part)

    snippet = {
        "id": snippet_id,
        "uri": uri,
        "name": snippet_info["name"],
        "area": area,
        "function": function_part,
        "file": relative_path,
        "filePath": file_path,
        "content": content,
        "startLine": snippet_info.get("startLine"),
        "endLine": snippet_info.get("endLine"),
        "language": "cpp",
        "metadata": metadata,
        "tags": metadata["tags"],
        "uses": metadata["uses"],
        "symbols": metadata["symbols"],
    }

    snippet_index["snippets"][snippet_id] = snippet

    for tag in metadata["tags"]:
        if tag not in snippet_index["byTag"]:
            snippet_index["byTag"][tag] = []
        if snippet_id not in snippet_index["byTag"][tag]:
            snippet_index["byTag"][tag].append(snippet_id)

    if area not in snippet_index["byArea"]:
        snippet_index["byArea"][area] = []
    if snippet_id not in snippet_index["byArea"][area]:
        snippet_index["byArea"][area].append(snippet_id)


def _extract_snippets_from_file(
    file_path: Path, relative_path: str, snippet_index: dict
) -> None:
    file_content = file_path.read_text(encoding="utf-8", errors="replace")
    lines = file_content.split("\n")

    current_snippet: dict | None = None
    snippet_lines: list = []
    in_snippet = False

    for i, line in enumerate(lines):
        snip_start = re.search(r"@@@SNIPSTART\s+(.+)", line)
        if snip_start:
            if current_snippet:
                _save_snippet(current_snippet, "\n".join(snippet_lines), str(file_path), relative_path, snippet_index)
            current_snippet = {"name": snip_start.group(1).strip(), "startLine": i + 1}
            snippet_lines = []
            in_snippet = True
            continue

        if "@@@SNIPEND" in line:
            if current_snippet and in_snippet:
                current_snippet["endLine"] = i + 1
                _save_snippet(current_snippet, "\n".join(snippet_lines), str(file_path), relative_path, snippet_index)
                current_snippet = None
                snippet_lines = []
                in_snippet = False
            continue

        if in_snippet and current_snippet:
            snippet_lines.append(line)

    if current_snippet and in_snippet:
        _save_snippet(current_snippet, "\n".join(snippet_lines), str(file_path), relative_path, snippet_index)


def _build_snippet_index(snippets_dir: Path, base_dir: Path) -> dict:
    snippet_index: dict = {"snippets": {}, "byTag": {}, "byArea": {}}

    def scan_directory(directory: Path, rel_prefix: str = "") -> None:
        if not directory.exists():
            print(f"Directory does not exist: {directory}", file=sys.stderr)
            return

        for entry in sorted(directory.iterdir()):
            rel_path = str(Path(rel_prefix) / entry.name) if rel_prefix else entry.name

            if entry.is_dir():
                scan_directory(entry, rel_path)
            elif entry.is_file() and entry.suffix in (".h", ".cpp"):
                _extract_snippets_from_file(entry, rel_path, snippet_index)

    print(f"Scanning snippets directory: {snippets_dir}", file=sys.stderr)
    scan_directory(snippets_dir, "")

    snippet_count = len(snippet_index["snippets"])
    print(f"Snippet indexing complete: {snippet_count} snippets indexed", file=sys.stderr)

    _save_snippet_index(base_dir, snippet_index)
    return snippet_index


def generate_snippet_cache(base_dir: Path) -> dict:
    """Generate snippet cache (force regeneration, ignores existing cache)."""
    print("Generating snippet cache...", file=sys.stderr)
    snippets_dir = base_dir / "data" / "bytewars-snippets"

    if not snippets_dir.exists():
        print(f"Snippets directory not found: {snippets_dir}", file=sys.stderr)
        return {"snippets": {}, "byTag": {}, "byArea": {}}

    return _build_snippet_index(snippets_dir, base_dir)


def index_snippets(base_dir: Path, use_cache: bool = True, load_only: bool = False) -> dict:
    """Index code snippets. Uses cache if available and valid."""
    print(
        f"index_snippets called with base_dir: {base_dir}, "
        f"use_cache: {use_cache}, load_only: {load_only}",
        file=sys.stderr,
    )

    snippets_dir = base_dir / "data" / "bytewars-snippets"
    if not snippets_dir.exists():
        print(f"Snippets directory not found: {snippets_dir}", file=sys.stderr)
        return {"snippets": {}, "byTag": {}, "byArea": {}}

    if use_cache and _is_snippet_cache_valid(base_dir):
        cached = _load_snippet_index(base_dir)
        if cached:
            print("Using cached snippet index", file=sys.stderr)
            return cached

    if load_only:
        print("Snippet cache not found and load_only=True, returning empty index", file=sys.stderr)
        return {"snippets": {}, "byTag": {}, "byArea": {}}

    if use_cache:
        print("Cache is invalid or missing, re-indexing snippets...", file=sys.stderr)

    return _build_snippet_index(snippets_dir, base_dir)


# ---------------------------------------------------------------------------
# Example components
# ---------------------------------------------------------------------------

def index_example_components(base_dir: Path) -> dict:
    """Index example components from data/example-components directory."""
    components_dir = base_dir / "data" / "example-components"

    example_index: dict = {"components": {}, "byService": {}}

    if not components_dir.exists():
        print(f"Example components directory not found: {components_dir}", file=sys.stderr)
        return example_index

    def ensure_component(
        component_id: str, meta: dict, relative_path: str, full_path: str
    ) -> None:
        component = example_index["components"].get(component_id)

        if component is None:
            mod_deps = meta.get("moduleDependencies", [])
            if isinstance(mod_deps, list):
                mod_deps = mod_deps
            elif mod_deps:
                mod_deps = [str(mod_deps)]
            else:
                mod_deps = []

            int_hints = meta.get("integrationHints", [])
            if isinstance(int_hints, list):
                int_hints = int_hints
            elif int_hints:
                int_hints = [str(int_hints)]
            else:
                int_hints = []

            component = {
                "id": component_id,
                "service": meta.get("service"),
                "provider": meta.get("provider"),
                "language": meta.get("language", "unreal-cpp"),
                "description": meta.get("description", ""),
                "controllerClass": meta.get("controllerClass"),
                "entryStruct": meta.get("entryStruct"),
                "uiWidgetClass": meta.get("uiWidgetClass"),
                "rowWidgetClass": meta.get("rowWidgetClass"),
                "publicInterface": meta.get("publicInterface", {}),
                "asyncState": meta.get("asyncState", {}),
                "dataModel": meta.get("dataModel", {}),
                "engineConfiguration": meta.get("engineConfiguration", {}),
                "backendRequirements": meta.get("backendRequirements", {}),
                "dropInReady": bool(meta.get("dropInReady", True)),
                "recommended": bool(meta.get("recommended", True)),
                "integrationHints": int_hints,
                "moduleDependencies": mod_deps,
                "files": [],
                "filePaths": [],
            }

            example_index["components"][component_id] = component

            svc = component.get("service")
            if svc:
                if not isinstance(example_index["byService"].get(svc), list):
                    example_index["byService"][svc] = []
                if component_id not in example_index["byService"][svc]:
                    example_index["byService"][svc].append(component_id)
        else:
            if meta.get("description") and not component.get("description"):
                component["description"] = meta["description"]
            mod_deps = meta.get("moduleDependencies", [])
            if isinstance(mod_deps, list) and mod_deps:
                component["moduleDependencies"] = mod_deps
            elif mod_deps:
                component["moduleDependencies"] = [str(mod_deps)]
            int_hints = meta.get("integrationHints", [])
            if isinstance(int_hints, list) and int_hints:
                component["integrationHints"] = int_hints
            elif int_hints:
                component["integrationHints"] = [str(int_hints)]

        if relative_path and relative_path not in component["files"]:
            component["files"].append(relative_path)
        if full_path and full_path not in component["filePaths"]:
            component["filePaths"].append(full_path)

    def extract_example_components_from_file(file_path: Path, relative_path: str) -> None:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")

        current_id: str | None = None
        collecting = False
        json_lines: list = []

        for line in lines:
            begin_match = re.search(r"AB_MCP_BEGIN:([^\s]+)", line)
            if begin_match:
                current_id = begin_match.group(1).strip()
                collecting = True
                json_lines = []
                continue

            end_match = re.search(r"AB_MCP_END:([^\s]+)", line)
            if end_match and collecting and current_id and end_match.group(1).strip() == current_id:
                json_text = "\n".join(
                    re.sub(r"^\s*//\s?", "", l) for l in json_lines
                ).strip()

                if json_text:
                    try:
                        meta = json.loads(json_text)
                        ensure_component(current_id, meta, relative_path, str(file_path))
                    except json.JSONDecodeError as e:
                        print(
                            f"Failed to parse example component metadata for '{current_id}' "
                            f"in {file_path}: {e}",
                            file=sys.stderr,
                        )

                current_id = None
                collecting = False
                json_lines = []
                continue

            if collecting and current_id and line.strip().startswith("//"):
                json_lines.append(line)

    def scan_components_directory(directory: Path, rel_prefix: str = "") -> None:
        if not directory.exists():
            return

        for entry in sorted(directory.iterdir()):
            rel_path = str(Path(rel_prefix) / entry.name) if rel_prefix else entry.name

            if entry.is_dir():
                scan_components_directory(entry, rel_path)
            elif entry.is_file() and entry.suffix in (".h", ".cpp"):
                extract_example_components_from_file(entry, rel_path)

    print(f"Indexing example components from: {components_dir}", file=sys.stderr)
    scan_components_directory(components_dir, "")

    # Post-processing: ensure paired .h/.cpp files are included
    for component_id, component in example_index["components"].items():
        files_set = set(component["files"])

        for file in list(component["files"]):
            p = Path(file)
            base_name = p.stem
            dir_part = str(p.parent) if str(p.parent) != "." else ""

            if p.suffix == ".h":
                cpp_path = str(Path(dir_part) / f"{base_name}.cpp") if dir_part else f"{base_name}.cpp"
                cpp_full = components_dir / cpp_path
                if cpp_full.exists() and cpp_path not in files_set:
                    component["files"].append(cpp_path)
                    component["filePaths"].append(str(cpp_full))
                    files_set.add(cpp_path)
            elif p.suffix == ".cpp":
                h_path = str(Path(dir_part) / f"{base_name}.h") if dir_part else f"{base_name}.h"
                h_full = components_dir / h_path
                if h_full.exists() and h_path not in files_set:
                    component["files"].append(h_path)
                    component["filePaths"].append(str(h_full))
                    files_set.add(h_path)

    component_count = len(example_index["components"])
    print(f"Example component indexing complete: {component_count} components indexed", file=sys.stderr)

    return example_index


# ---------------------------------------------------------------------------
# Snippet search
# ---------------------------------------------------------------------------

def search_snippets(
    snippet_index: dict,
    query: str = "",
    area: str | None = None,
    tags: list | None = None,
    limit: int = 20,
) -> list:
    """Search snippets by various criteria. Returns list of snippet summaries."""
    if tags is None:
        tags = []

    if not snippet_index or not snippet_index.get("snippets"):
        return []

    query_lower = query.lower()
    scored_results: list = []

    for snippet_id, snippet in snippet_index["snippets"].items():
        score = 0
        matches = False

        if area and snippet.get("area") != area:
            continue

        if tags:
            snippet_tags = snippet.get("tags") or []
            if not all(
                any(st.lower() == t.lower() for st in snippet_tags)
                for t in tags
            ):
                continue

        if query_lower:
            if snippet.get("name") and query_lower in snippet["name"].lower():
                score += 100
                matches = True

            if snippet.get("function") and query_lower in snippet["function"].lower():
                score += 80
                matches = True

            if snippet.get("tags"):
                tag_matches = sum(
                    1 for tag in snippet["tags"] if query_lower in tag.lower()
                )
                score += tag_matches * 60
                if tag_matches > 0:
                    matches = True

            if snippet.get("area") and query_lower in snippet["area"].lower():
                score += 50
                matches = True

            if snippet.get("content"):
                content_lower = snippet["content"].lower()
                if query_lower in content_lower:
                    occurrences = len(re.findall(re.escape(query_lower), content_lower))
                    score += min(occurrences * 10, 40)
                    matches = True

            if snippet.get("symbols"):
                all_syms = (
                    list(snippet["symbols"].get("classes") or [])
                    + list(snippet["symbols"].get("methods") or [])
                    + list(snippet["symbols"].get("functions") or [])
                )
                sym_matches = sum(1 for s in all_syms if query_lower in s.lower())
                score += sym_matches * 30
                if sym_matches > 0:
                    matches = True

            if snippet.get("file") and query_lower in snippet["file"].lower():
                score += 20
                matches = True

            if snippet.get("uses"):
                uses_matches = sum(1 for u in snippet["uses"] if query_lower in u.lower())
                score += uses_matches * 25
                if uses_matches > 0:
                    matches = True

            if not matches:
                continue
        else:
            matches = True

        if matches:
            scored_results.append({"snippet": snippet, "score": score})

    scored_results.sort(key=lambda x: x["score"], reverse=True)

    return [
        {
            "id": r["snippet"]["id"],
            "uri": r["snippet"]["uri"],
            "name": r["snippet"]["name"],
            "area": r["snippet"]["area"],
            "function": r["snippet"]["function"],
            "file": r["snippet"]["file"],
            "tags": r["snippet"]["tags"],
            "uses": r["snippet"]["uses"],
            "description": f"{r['snippet']['area']}/{r['snippet']['function']} - {r['snippet']['name']}",
            "startLine": r["snippet"]["startLine"],
            "endLine": r["snippet"]["endLine"],
        }
        for r in scored_results[:limit]
    ]
