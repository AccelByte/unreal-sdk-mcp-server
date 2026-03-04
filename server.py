#!/usr/bin/env python3
"""
AccelByte Unreal SDK MCP Server.
Provides AI assistants with access to AccelByte SDK documentation, symbols,
code snippets, and example components via the Model Context Protocol.
Python translation of server.js.
"""

import asyncio
import json
import sys
from pathlib import Path

import mcp.types as types
import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route

from parser import load_symbols
from sdk_installer import install_unreal_sdk
from source_indexer import (
    index_example_components,
    index_snippets,
    index_source_files,
    search_snippets,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
SOURCES_DIR = BASE_DIR / "data"
UNREAL_SDK_XML_DIR = SOURCES_DIR / "unreal-sdk"
OSS_SDK_DIR = SOURCES_DIR / "oss-sdk"

# Source index cache is one level up from the server (matches JS: join(__dirname, "..", ".cache"))
CACHE_DIR = BASE_DIR.parent / ".cache"

SDK_REQUIREMENT_NOTE = (
    "The AccelByte Unreal SDK (and OSS / NetworkUtilities if used) must be installed in your "
    "Unreal project for this code or API to work. If not already installed, use the "
    "install_unreal_sdk tool to download and set up the SDK(s)."
)

# ---------------------------------------------------------------------------
# Load data at startup (synchronous — same as JS top-level code)
# ---------------------------------------------------------------------------

unrealsdk_symbols: dict = {}
osssdk_symbols: dict = {}

try:
    print("Loading symbols from cache...", file=sys.stderr)
    unrealsdk_symbols = load_symbols(UNREAL_SDK_XML_DIR, "unreal-sdk", BASE_DIR, True, True) or {}
    osssdk_symbols = load_symbols(OSS_SDK_DIR, "oss-sdk", BASE_DIR, True, True) or {}

    unreal_count = len(unrealsdk_symbols)
    oss_count = len(osssdk_symbols)
    print(
        f"Loaded {unreal_count} unreal-sdk symbols, {oss_count} oss-sdk symbols from cache",
        file=sys.stderr,
    )

    if unreal_count == 0 and oss_count == 0:
        print(
            "WARNING: No symbols loaded from cache. "
            "Run 'python generate_cache.py' to generate cache files.",
            file=sys.stderr,
        )
except Exception as e:
    print(f"ERROR: Failed to load symbols from cache: {e}", file=sys.stderr)
    print("Run 'python generate_cache.py' to generate cache files.", file=sys.stderr)

source_index: dict | None = None
try:
    print("Loading source index from cache...", file=sys.stderr)
    source_index = index_source_files(CACHE_DIR, True, True)
    file_count = len(source_index.get("files", {}))
    class_count = len(source_index.get("classes", {}))
    method_count = len(source_index.get("methods", {}))
    print(
        f"Source index loaded: {file_count} files, {class_count} classes, {method_count} methods",
        file=sys.stderr,
    )
    if file_count == 0:
        print(
            "WARNING: Source index is empty. "
            "Run 'python generate_cache.py' to generate cache files.",
            file=sys.stderr,
        )
except Exception as e:
    print(f"ERROR: Failed to load source index from cache: {e}", file=sys.stderr)
    print("Run 'python generate_cache.py' to generate cache files.", file=sys.stderr)

snippet_index: dict | None = None
try:
    print("Loading snippet index from cache...", file=sys.stderr)
    snippet_index = index_snippets(BASE_DIR, True, True)
    snippet_count = len(snippet_index.get("snippets", {}))
    print(f"Snippet index loaded: {snippet_count} snippets", file=sys.stderr)
    if snippet_count == 0:
        print(
            "WARNING: Snippet index is empty. "
            "Run 'python generate_cache.py' to generate cache files.",
            file=sys.stderr,
        )
except Exception as e:
    print(f"ERROR: Failed to load snippet index from cache: {e}", file=sys.stderr)
    print("Run 'python generate_cache.py' to generate cache files.", file=sys.stderr)

example_components_index: dict = {"components": {}, "byService": {}}
try:
    print("Indexing example components...", file=sys.stderr)
    example_components_index = index_example_components(BASE_DIR) or example_components_index
    component_count = len(example_components_index.get("components") or {})
    print(f"Example components indexed: {component_count} components", file=sys.stderr)
except Exception as e:
    print(f"ERROR: Failed to index example components: {e}", file=sys.stderr)

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

server = Server("sdk-mcp-server")


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@server.list_resources()
async def list_resources() -> list[types.Resource]:
    resources: list[types.Resource] = []

    if source_index:
        for file_path, file_data in source_index.get("files", {}).items():
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"source://{file_path}"),
                    name=Path(file_path).name,
                    description=f"{file_data.get('type', '')}: {file_path} ({file_data.get('lines', 0)} lines)",
                    mimeType="text/x-c++",
                )
            )

        for class_name, file_paths in source_index.get("classes", {}).items():
            for file_path in file_paths:
                resources.append(
                    types.Resource(
                        uri=AnyUrl(f"source://class/{class_name}"),
                        name=f"{class_name} implementation",
                        description=f"Implementation of {class_name} in {file_path}",
                        mimeType="text/x-c++",
                    )
                )

    if snippet_index:
        for snippet_id, snippet in snippet_index.get("snippets", {}).items():
            tags_str = ", ".join(snippet.get("tags") or [])
            uses = snippet.get("uses") or []
            uses_str = f" | Uses: {', '.join(uses)}" if uses else ""
            resources.append(
                types.Resource(
                    uri=AnyUrl(snippet["uri"]),
                    name=snippet["name"],
                    description=(
                        f"Snippet: {snippet['area']}/{snippet['function']} "
                        f"| Tags: {tags_str}{uses_str} | {snippet['file']}"
                    ),
                    mimeType="application/json",
                )
            )

    if example_components_index and example_components_index.get("components"):
        for component in example_components_index["components"].values():
            service = component.get("service") or "unknown-service"
            description = component.get("description") or ""
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"example://{component['id']}"),
                    name=component["id"],
                    description=f"Example component ({service}): {description}",
                    mimeType="application/json",
                )
            )

            for file in component.get("files") or []:
                file_name = Path(file).name
                mime = "text/x-c++" if file.endswith((".h", ".cpp")) else "text/plain"
                resources.append(
                    types.Resource(
                        uri=AnyUrl(f"example-file://{file}"),
                        name=file_name,
                        description=f"Example component source: {component['id']} - {file_name}",
                        mimeType=mime,
                    )
                )

    return resources


@server.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    uri_str = str(uri)

    if uri_str.startswith("unreal-sdk/cpp://"):
        symbol_id = uri_str[len("unreal-sdk/cpp://"):]
        symbol = unrealsdk_symbols.get(symbol_id)
        if not symbol:
            raise ValueError(f"Resource not found: {uri_str}")
        return json.dumps(symbol, indent=2)

    if uri_str.startswith("oss-sdk/cpp://"):
        symbol_id = uri_str[len("oss-sdk/cpp://"):]
        symbol = osssdk_symbols.get(symbol_id)
        if not symbol:
            raise ValueError(f"Resource not found: {uri_str}")
        return json.dumps(symbol, indent=2)

    if uri_str.startswith("snippet://"):
        if not snippet_index:
            raise ValueError("Snippet indexing is not available")
        snippet_id = uri_str[len("snippet://"):]
        snippet = snippet_index["snippets"].get(snippet_id)
        if not snippet:
            raise ValueError(f"Snippet not found: {uri_str}")
        snippet_data = {
            "id": snippet["id"],
            "uri": snippet["uri"],
            "name": snippet["name"],
            "area": snippet["area"],
            "function": snippet["function"],
            "file": snippet["file"],
            "filePath": snippet["filePath"],
            "startLine": snippet["startLine"],
            "endLine": snippet["endLine"],
            "language": snippet["language"],
            "tags": snippet["tags"],
            "uses": snippet["uses"],
            "symbols": snippet["symbols"],
            "content": snippet["content"],
        }
        return json.dumps(snippet_data, indent=2)

    if uri_str.startswith("example://"):
        if not example_components_index or not example_components_index.get("components"):
            raise ValueError("Example components index is not available")
        component_id = uri_str[len("example://"):]
        component = example_components_index["components"].get(component_id)
        if not component:
            raise ValueError(f"Example component not found: {uri_str}")
        return json.dumps(component, indent=2)

    if uri_str.startswith("example-file://"):
        if not example_components_index or not example_components_index.get("components"):
            raise ValueError("Example components index is not available")
        relative_path = uri_str[len("example-file://"):]
        full_path: str | None = None
        for component in example_components_index["components"].values():
            try:
                idx = component["files"].index(relative_path)
                full_path = component["filePaths"][idx]
                break
            except ValueError:
                continue
        if not full_path or not Path(full_path).exists():
            raise ValueError(f"Example component source file not found: {uri_str}")
        return Path(full_path).read_text(encoding="utf-8")

    if uri_str.startswith("source://"):
        if not source_index:
            raise ValueError("Source code indexing is not available")

        if uri_str.startswith("source://class/"):
            class_name = uri_str[len("source://class/"):]
            files = source_index.get("classes", {}).get(class_name) or []
            if not files:
                raise ValueError(f"No source files found for class: {class_name}")
            impl_file = next((f for f in files if f.endswith(".cpp")), files[0])
            file_data = source_index["files"].get(impl_file)
            if not file_data:
                raise ValueError(f"Source file not found: {impl_file}")
            return (
                f"// Source file: {file_data['path']}\n"
                f"\n"
                f"{file_data['content']}"
            )

        file_path = uri_str[len("source://"):]
        file_data = source_index["files"].get(file_path)
        if not file_data:
            raise ValueError(f"Source file not found: {file_path}")
        return file_data["content"]

    raise ValueError(f"Unknown resource URI format: {uri_str}")


# ---------------------------------------------------------------------------
# Tools — list
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_symbols",
            description=(
                "Search for symbols in the SDK documentation by name, type, or description. "
                "Returned code and APIs require the AccelByte Unreal SDK (and OSS/NetworkUtilities "
                "if used) to be installed; use install_unreal_sdk if needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (searches in symbol name, type, and description)",
                    },
                    "source": {
                        "type": "string",
                        "description": "Filter by SDK source (oss-sdk or unreal-sdk)",
                        "enum": ["oss-sdk", "unreal-sdk"],
                    },
                    "type": {
                        "type": "string",
                        "description": "Filter by symbol type (class, struct, function, enum, namespace, variable)",
                        "enum": ["class", "struct", "function", "enum", "namespace", "variable"],
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results to return (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search_snippets",
            description=(
                "Search for code snippets by query, area, tags, or content. "
                "Helps find relevant code examples from the tutorial modules. "
                "Returned code and APIs require the AccelByte Unreal SDK (and OSS/NetworkUtilities "
                "if used) to be installed; use install_unreal_sdk if needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query - searches in snippet name, function name, tags, area, "
                            "content, and symbols. Leave empty to search by filters only."
                        ),
                    },
                    "area": {
                        "type": "string",
                        "description": (
                            "Filter by area (e.g., 'auth', 'party', 'chat', 'session', 'store', "
                            "'cloudsave', 'statistics', 'friends', 'presence', 'matchmaking', etc.)"
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filter by tags (all specified tags must match). "
                            "Examples: 'authentication', 'login', 'multiplayer', 'messaging', etc."
                        ),
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results to return (default: 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="search_example_components",
            description=(
                "Search for ready-made, drop-in example components (full Unreal C++/Slate panels "
                "and controllers) that implement common AccelByte flows such as showing player "
                "achievements, stats, friends, login queue, etc. Returns component metadata "
                "including class names, public interfaces, and a fileResourceUris array. "
                "IMPORTANT: Use the standard MCP resources/read handler with the fileResourceUris "
                "(e.g., 'example-file://ComponentName.h') to fetch the actual source code files "
                "(.h and .cpp). The fileResourceUris are MCP resource URIs, not tool calls. "
                "Returned code and APIs require the AccelByte Unreal SDK (and OSS/NetworkUtilities "
                "if used) to be installed; use install_unreal_sdk if needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": (
                            "Natural language description of what the component should do "
                            "(e.g. 'show my player achievements', 'display login queue status')."
                        ),
                    },
                    "service": {
                        "type": "string",
                        "description": (
                            "Optional filter by AccelByte service "
                            "(e.g. 'achievements', 'statistics', 'friends', 'auth', 'store')."
                        ),
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional filter by implementation language (e.g. 'unreal-cpp').",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of components to return (default: 5).",
                        "default": 5,
                    },
                },
                "required": ["intent"],
            },
        ),
        types.Tool(
            name="describe_example_components",
            description=(
                "Fetch the actual source code content of example component files. "
                "Use this tool with fileResourceUris from search_example_components results "
                "(e.g., 'example-file://AccelByteAchievementsPanel.h') to get the complete "
                ".h or .cpp file content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "fileResourceUris": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Array of fileResourceUris from search_example_components results "
                            "(e.g., ['example-file://AccelByteAchievementsPanel.h', "
                            "'example-file://AccelByteAchievementsPanel.cpp'])"
                        ),
                    },
                },
                "required": ["fileResourceUris"],
            },
        ),
        types.Tool(
            name="install_unreal_sdk",
            description=(
                "Generate an install_accelbyte_sdk.bat script in the Unreal project root. "
                "The script clones the requested AccelByte SDK components from GitHub and places "
                "them under Plugins/Accelbyte/. The user runs the script themselves."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "projectPath": {
                        "type": "string",
                        "description": (
                            "Path to the Unreal project root (directory containing the .uproject file). "
                            "Absolute path or relative to workspaceRoot."
                        ),
                    },
                    "components": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["sdk", "oss", "networkUtilities"]},
                        "description": (
                            "Components to include: 'sdk' (AccelByte Game SDK), 'oss' (Online Subsystem), "
                            "'networkUtilities' (AccelByteNetworkUtilities). Default ['sdk']. "
                            "Install order: networkUtilities, sdk, oss."
                        ),
                    },
                    "workspaceRoot": {
                        "type": "string",
                        "description": (
                            "Optional. Workspace root used to resolve a relative projectPath. "
                            "Defaults to current working directory."
                        ),
                    },
                    "version": {
                        "type": "string",
                        "description": "Branch or tag to clone (e.g. 'v28.0.0'). Omit for latest.",
                    },
                    "setupProjectFiles": {
                        "type": "boolean",
                        "description": (
                            "If true, include steps in the script to patch .uproject, Build.cs, "
                            "and Target.cs. Default false."
                        ),
                    },
                },
                "required": ["projectPath"],
            },
        ),
        types.Tool(
            name="describe_symbols",
            description=(
                "Get full descriptions of symbols by their IDs, including fields, methods, and links "
                "to relevant code snippets that use them. Returned code and APIs require the AccelByte "
                "Unreal SDK (and OSS/NetworkUtilities if used) to be installed; use install_unreal_sdk "
                "if needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbolIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of symbol IDs to describe "
                            "(e.g., ['AccelByte::FAccelByteMessagingSystem@cpp'])"
                        ),
                    },
                    "includeSnippets": {
                        "type": "boolean",
                        "description": "Whether to include relevant snippet links (default: true)",
                        "default": True,
                    },
                    "snippetLimit": {
                        "type": "number",
                        "description": "Maximum number of relevant snippets to return per symbol (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["symbolIds"],
            },
        ),
        types.Tool(
            name="get_accelbyte_how_to",
            description=(
                "Get implementation best practices and how-to guides for common AccelByte tasks. "
                "Provides step-by-step instructions, code templates, and links to related snippets "
                "and example components."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": (
                            "The topic or question you need guidance on "
                            "(e.g., 'get api client', 'add api call', 'authentication', 'matchmaking'). "
                            "Supports partial matches and keywords."
                        ),
                    },
                    "include_code_examples": {
                        "type": "boolean",
                        "description": "Whether to include related code snippets (default: true)",
                        "default": True,
                    },
                    "include_components": {
                        "type": "boolean",
                        "description": "Whether to include related example components (default: true)",
                        "default": True,
                    },
                },
                "required": ["topic"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tools — call
# ---------------------------------------------------------------------------

def _handle_search_symbols(args: dict) -> dict:
    query: str = args.get("query", "") or ""
    source_filter: str | None = args.get("source")
    type_filter: str | None = args.get("type")
    limit: int = int(args.get("limit") or 20)

    search_lower = query.lower()

    if source_filter == "unreal-sdk":
        symbols_to_search = unrealsdk_symbols
    elif source_filter == "oss-sdk":
        symbols_to_search = osssdk_symbols
    else:
        symbols_to_search = {**unrealsdk_symbols, **osssdk_symbols}

    scored_results = []
    for symbol_id, symbol in symbols_to_search.items():
        if type_filter and (symbol.get("type") or "").lower() != type_filter.lower():
            continue

        name_match = search_lower in (symbol.get("name") or "").lower()
        type_match = search_lower in (symbol.get("type") or "").lower()
        desc_match = search_lower in (symbol.get("description") or "").lower()

        if not (name_match or type_match or desc_match):
            continue

        is_oss_sdk = symbol_id not in unrealsdk_symbols
        score = 0
        if is_oss_sdk:
            score += 100
        if name_match:
            score += 50 if (symbol.get("name") or "").lower() == search_lower else 30
        if type_match:
            score += 10
        if desc_match:
            score += 5

        scored_results.append({
            "id": symbol_id,
            "type": symbol.get("type"),
            "description": symbol.get("description") or "",
            "score": score,
        })

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    results = [{k: v for k, v in r.items() if k != "score"} for r in scored_results[:limit]]

    return {
        "results": results,
        "count": len(results),
        "filters": {"source": source_filter or None, "type": type_filter or None},
        "sdkRequirement": SDK_REQUIREMENT_NOTE,
    }


def _handle_search_snippets(args: dict) -> dict:
    if not snippet_index:
        raise RuntimeError("Snippet indexing is not available")

    query: str = args.get("query") or ""
    area: str | None = args.get("area")
    tags = args.get("tags") or []
    limit: int = int(args.get("limit") or 20)

    results = search_snippets(
        snippet_index,
        query=query,
        area=area,
        tags=tags if isinstance(tags, list) else [],
        limit=limit,
    )

    return {
        "results": results,
        "count": len(results),
        "query": query or None,
        "filters": {"area": area or None, "tags": tags if tags else None},
        "sdkRequirement": SDK_REQUIREMENT_NOTE,
    }


def _handle_search_example_components(args: dict) -> dict:
    intent: str = args.get("intent") or ""
    service: str | None = args.get("service")
    language: str | None = args.get("language")
    limit: int = int(args.get("limit") or 5)

    if not example_components_index or not example_components_index.get("components"):
        raise RuntimeError("Example components index is not available")

    intent_lower = intent.lower()
    tokens = [t for t in intent_lower.split() if t]

    def build_integration_hint(component: dict) -> str:
        controller = component.get("controllerClass") or "your controller class"
        ui_widget = component.get("uiWidgetClass")
        pub = component.get("publicInterface") or {}
        has_init = bool(pub.get("initialise"))
        has_build = bool(pub.get("buildWidget"))
        has_show = bool(pub.get("show"))

        parts = []
        parts.append(
            f"Use {controller}"
            + (f" and {ui_widget}" if ui_widget else "")
            + " as a drop-in component after AccelByte login."
        )

        if has_init:
            parts.append(
                f"After obtaining an AccelByte::FApiClientPtr on login, call 'initialise' "
                f"({pub['initialise']}) once to bind the SDK client."
            )

        if has_build:
            parts.append(
                f"Call 'buildWidget' ({pub['buildWidget']}) to get an SWidget and add it to your HUD or viewport."
            )
        elif has_show:
            parts.append(
                f"Call 'show' ({pub['show']}) from your UI flow to display the panel."
            )

        if component.get("service") == "achievements":
            parts.append(
                "This component already handles querying achievement definitions and user progress; "
                "you usually don't need to call the achievements API directly."
            )

        mod_deps = component.get("moduleDependencies") or []
        if mod_deps:
            parts.append(
                "First ensure the AccelByte Unreal SDK (and OSS/NetworkUtilities if used) is installed "
                "in your project (use the install_unreal_sdk tool). "
                f"Then add these to your module's Build.cs PublicDependencyModuleNames: {', '.join(mod_deps)}."
            )

        int_hints = component.get("integrationHints") or []
        if int_hints:
            parts.append(" ".join(int_hints))

        return " ".join(parts)

    scored: list = []
    for component in example_components_index["components"].values():
        if service and component.get("service") and component["service"] != service:
            continue
        if language and component.get("language") and component["language"] != language:
            continue

        score = 0
        matched = False
        matched_tokens: set = set()

        haystack = " ".join([
            component.get("description") or "",
            component.get("id") or "",
            component.get("service") or "",
            component.get("controllerClass") or "",
            component.get("uiWidgetClass") or "",
            component.get("rowWidgetClass") or "",
        ]).lower()

        if tokens:
            for token in tokens:
                if not token:
                    continue
                occurrences = haystack.count(token)
                if occurrences > 0:
                    score += occurrences * 10
                    matched = True
                    matched_tokens.add(token)
        else:
            matched = True

        if service and component.get("service") == service:
            score += 50

        if not matched:
            continue

        match_type = "reference_example"
        is_recommended = component.get("recommended", True)

        if tokens and matched_tokens:
            coverage = len(matched_tokens) / len(tokens)
            if coverage >= 0.6 and score >= 40:
                match_type = "exact_solution"
            elif coverage > 0:
                match_type = "partial_match"

        if not is_recommended and match_type == "exact_solution":
            is_recommended = True

        scored.append({
            "component": component,
            "score": score,
            "matchType": match_type,
            "recommended": is_recommended,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    limited = []
    for item in scored[:limit]:
        c = item["component"]
        file_resource_uris = [f"example-file://{f}" for f in (c.get("files") or [])]
        limited.append({
            "id": c["id"],
            "service": c.get("service"),
            "provider": c.get("provider"),
            "language": c.get("language"),
            "description": c.get("description"),
            "controllerClass": c.get("controllerClass"),
            "entryStruct": c.get("entryStruct"),
            "uiWidgetClass": c.get("uiWidgetClass"),
            "rowWidgetClass": c.get("rowWidgetClass"),
            "publicInterface": c.get("publicInterface"),
            "asyncState": c.get("asyncState"),
            "dataModel": c.get("dataModel"),
            "engineConfiguration": c.get("engineConfiguration") or {},
            "backendRequirements": c.get("backendRequirements") or {},
            "files": c.get("files"),
            "fileResourceUris": file_resource_uris,
            "drop_in_ready": c.get("dropInReady", True) is not False,
            "recommended": bool(item["recommended"]),
            "match_type": item["matchType"],
            "integration_hint": build_integration_hint(c),
            "moduleDependencies": c.get("moduleDependencies") or [],
            "integrationHints": c.get("integrationHints") or [],
            "resourceUri": f"example://{c['id']}",
        })

    return {
        "results": limited,
        "count": len(limited),
        "intent": intent or None,
        "filters": {"service": service or None, "language": language or None},
        "sdkRequirement": SDK_REQUIREMENT_NOTE,
    }


def _handle_describe_symbols(args: dict) -> dict:
    symbol_ids = args.get("symbolIds") or []
    include_snippets: bool = bool(args.get("includeSnippets", True))
    snippet_limit: int = int(args.get("snippetLimit") or 5)

    if not isinstance(symbol_ids, list) or not symbol_ids:
        raise RuntimeError("symbolIds must be a non-empty array")

    results = []
    for symbol_id in symbol_ids:
        symbol = unrealsdk_symbols.get(symbol_id) or osssdk_symbols.get(symbol_id)

        if not symbol:
            results.append({"id": symbol_id, "error": "Symbol not found"})
            continue

        source = "unreal-sdk" if symbol_id in unrealsdk_symbols else "oss-sdk"
        uri = f"{source}/cpp://{symbol_id}"

        symbol_name = symbol.get("name", "")
        name_parts = symbol_name.split("::")
        base_name = name_parts[-1]

        relevant_snippets = []
        if include_snippets and snippet_index:
            for snip_id, snippet in snippet_index["snippets"].items():
                matches = False

                content = snippet.get("content") or ""
                if symbol_name in content or base_name in content:
                    matches = True

                if not matches and snippet.get("symbols"):
                    all_syms = (
                        list(snippet["symbols"].get("classes") or [])
                        + list(snippet["symbols"].get("methods") or [])
                        + list(snippet["symbols"].get("functions") or [])
                    )
                    if any(
                        s == symbol_name or s == base_name
                        or symbol_name in s or s in symbol_name
                        for s in all_syms
                    ):
                        matches = True

                if matches:
                    relevant_snippets.append({
                        "id": snippet["id"],
                        "uri": snippet["uri"],
                        "name": snippet["name"],
                        "area": snippet["area"],
                        "function": snippet["function"],
                        "file": snippet["file"],
                        "description": f"{snippet['area']}/{snippet['function']} - {snippet['name']}",
                    })

            relevant_snippets.sort(
                key=lambda x: (
                    not (symbol_name in x["name"] or base_name in x["name"])
                )
            )
            relevant_snippets = relevant_snippets[:snippet_limit]

        results.append({
            "id": symbol_id,
            "name": symbol.get("name"),
            "type": symbol.get("type"),
            "source": source,
            "uri": uri,
            "fields": symbol.get("fields") or {},
            "methods": symbol.get("methods") or {},
            "snippets": relevant_snippets,
            "snippetCount": len(relevant_snippets),
        })

    return {
        "symbols": results,
        "count": len(results),
        "sdkRequirement": SDK_REQUIREMENT_NOTE,
    }


def _handle_describe_example_components(args: dict) -> dict:
    file_resource_uris = args.get("fileResourceUris") or []

    if not isinstance(file_resource_uris, list) or not file_resource_uris:
        raise RuntimeError("fileResourceUris must be a non-empty array")

    if not example_components_index or not example_components_index.get("components"):
        raise RuntimeError("Example components index is not available")

    results = []
    for file_resource_uri in file_resource_uris:
        if not file_resource_uri.startswith("example-file://"):
            results.append({
                "fileResourceUri": file_resource_uri,
                "error": (
                    f"Invalid fileResourceUri format. "
                    f"Expected 'example-file://...', got: {file_resource_uri}"
                ),
            })
            continue

        relative_path = file_resource_uri[len("example-file://"):]
        full_path: str | None = None
        component_id: str | None = None

        for comp in example_components_index["components"].values():
            try:
                idx = comp["files"].index(relative_path)
                full_path = comp["filePaths"][idx]
                component_id = comp["id"]
                break
            except ValueError:
                continue

        if not full_path or not Path(full_path).exists():
            results.append({
                "fileResourceUri": file_resource_uri,
                "relativePath": relative_path,
                "error": "Example component source file not found",
            })
            continue

        file_content = Path(full_path).read_text(encoding="utf-8")
        mime = "text/x-c++" if relative_path.endswith((".h", ".cpp")) else "text/plain"

        results.append({
            "fileResourceUri": file_resource_uri,
            "componentId": component_id,
            "relativePath": relative_path,
            "mimeType": mime,
            "content": file_content,
            "lineCount": file_content.count("\n") + 1,
        })

    return {
        "files": results,
        "count": len(results),
        "sdkRequirement": SDK_REQUIREMENT_NOTE,
    }


def _handle_get_accelbyte_how_to(args: dict) -> dict:
    topic: str = args.get("topic") or ""
    include_code_examples: bool = bool(args.get("include_code_examples", True))
    include_components_flag: bool = bool(args.get("include_components", True))

    if not topic or not isinstance(topic, str):
        raise RuntimeError("topic is required and must be a string")

    best_practices_path = BASE_DIR / "data" / "best-practices.json"
    if not best_practices_path.exists():
        raise RuntimeError(
            "Best practices data not found. Please ensure data/best-practices.json exists."
        )

    best_practices = json.loads(best_practices_path.read_text(encoding="utf-8"))

    if not isinstance(best_practices.get("guides"), list):
        raise RuntimeError("Invalid best practices data structure")

    topic_lower = topic.lower()
    scored_guides = []

    for guide in best_practices["guides"]:
        score = 0
        matched = False

        keywords = guide.get("keywords") or []
        for keyword in keywords:
            if keyword.lower() in topic_lower or topic_lower in keyword.lower():
                score += 10
                matched = True

        if guide.get("title") and topic_lower in guide["title"].lower():
            score += 20
            matched = True

        if guide.get("id") and topic_lower in guide["id"].lower():
            score += 15
            matched = True

        if matched:
            scored_guides.append({"guide": guide, "score": score})

    scored_guides.sort(key=lambda x: x["score"], reverse=True)

    if not scored_guides:
        return {
            "error": f'No best practice guide found for topic: "{topic}"',
            "availableTopics": [
                {"id": g["id"], "title": g.get("title"), "keywords": g.get("keywords")}
                for g in best_practices["guides"]
            ],
        }

    selected = scored_guides[0]["guide"]
    result: dict = {
        "id": selected.get("id"),
        "title": selected.get("title"),
        "source_url": selected.get("source_url"),
        "overview": selected.get("overview"),
        "methods": selected.get("methods"),
        "steps": selected.get("steps"),
        "directories": selected.get("directories"),
        "file_naming": selected.get("file_naming"),
        "best_practices": selected.get("best_practices"),
        "common_pitfalls": selected.get("common_pitfalls"),
        "related_content": {},
    }

    if include_code_examples and snippet_index and selected.get("related_snippets"):
        related_snippets: list = []
        rs = selected["related_snippets"]

        areas = rs.get("areas") or []
        for snip_id, snippet in snippet_index["snippets"].items():
            if snippet.get("area") in areas:
                related_snippets.append({
                    "id": snippet["id"],
                    "uri": snippet["uri"],
                    "name": snippet["name"],
                    "function": snippet["function"],
                    "area": snippet["area"],
                    "file": snippet["file"],
                })

        tags_filter = rs.get("tags") or []
        if isinstance(tags_filter, list):
            seen_ids = {s["id"] for s in related_snippets}
            for snip_id, snippet in snippet_index["snippets"].items():
                if snip_id in seen_ids:
                    continue
                snip_tags = snippet.get("tags") or []
                if all(
                    any(st.lower() in tag.lower() for st in snip_tags)
                    for tag in tags_filter
                ):
                    related_snippets.append({
                        "id": snippet["id"],
                        "uri": snippet["uri"],
                        "name": snippet["name"],
                        "function": snippet["function"],
                        "area": snippet["area"],
                        "file": snippet["file"],
                    })

        query_str = rs.get("query")
        if query_str:
            query_lower = query_str.lower()
            seen_ids = {s["id"] for s in related_snippets}
            for snip_id, snippet in snippet_index["snippets"].items():
                if snip_id in seen_ids:
                    continue
                if (
                    query_lower in (snippet.get("name") or "").lower()
                    or query_lower in (snippet.get("function") or "").lower()
                    or query_lower in (snippet.get("content") or "").lower()
                ):
                    related_snippets.append({
                        "id": snippet["id"],
                        "uri": snippet["uri"],
                        "name": snippet["name"],
                        "function": snippet["function"],
                        "area": snippet["area"],
                        "file": snippet["file"],
                    })

        result["related_content"]["snippets"] = related_snippets[:10]

    if include_components_flag and example_components_index and selected.get("related_components"):
        related_comps: list = []
        for component_name in selected["related_components"]:
            for comp_id, comp in example_components_index["components"].items():
                if (
                    component_name in (comp.get("controllerClass") or "")
                    or component_name in (comp.get("uiWidgetClass") or "")
                    or component_name.lower() in comp_id
                ):
                    related_comps.append({
                        "id": comp["id"],
                        "service": comp.get("service"),
                        "description": comp.get("description"),
                        "controllerClass": comp.get("controllerClass"),
                        "uiWidgetClass": comp.get("uiWidgetClass"),
                        "fileResourceUris": comp.get("fileResourceUris"),
                    })
                    break
        result["related_content"]["components"] = related_comps

    return {"guide": result, "sdkRequirement": SDK_REQUIREMENT_NOTE}


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        match name:
            case "search_symbols":
                result = _handle_search_symbols(arguments or {})
            case "search_snippets":
                result = _handle_search_snippets(arguments or {})
            case "search_example_components":
                result = _handle_search_example_components(arguments or {})
            case "describe_example_components":
                result = _handle_describe_example_components(arguments or {})
            case "describe_symbols":
                result = _handle_describe_symbols(arguments or {})
            case "install_unreal_sdk":
                result = await install_unreal_sdk(arguments or {})
            case "get_accelbyte_how_to":
                result = _handle_get_accelbyte_how_to(arguments or {})
            case _:
                raise ValueError(f"Unknown tool: {name}")

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

async def _start_stdio_server() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
    print("MCP server running on stdio transport", file=sys.stderr)


async def _start_sse_server(port: int) -> None:
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )
    app = CORSMiddleware(
        starlette_app,
        allow_origins=["http://localhost:*"],
        allow_headers=["Content-Type"],
        expose_headers=["Content-Type"],
    )

    print(
        f"MCP server running on SSE transport at http://localhost:{port}",
        file=sys.stderr,
    )
    print(f"SSE endpoint: http://localhost:{port}/sse", file=sys.stderr)
    print(f"Message endpoint: http://localhost:{port}/messages/", file=sys.stderr)

    config = uvicorn.Config(app, host="127.0.0.1", port=port,  log_level="warning")
    uv_server = uvicorn.Server(config)
    await uv_server.serve()


def _parse_args() -> tuple[str, int]:
    transport = "stdio"
    port = 3000
    for arg in sys.argv[1:]:
        if arg.startswith("--transport="):
            transport = arg.split("=", 1)[1]
        elif arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])
    return transport, port


async def main() -> None:
    transport, port = _parse_args()
    print(f"Starting MCP server with {transport} transport...", file=sys.stderr)

    match transport:
        case "stdio":
            await _start_stdio_server()
        case "http" | "sse":
            await _start_sse_server(port)
        case _:
            print(f"Unknown transport: {transport}", file=sys.stderr)
            print("Valid options: stdio, http, sse", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)
