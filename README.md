# AccelByte Unreal SDK MCP Server

An MCP (Model Context Protocol) server that provides access to AccelByte's Unreal SDK documentation, symbols, and code snippets. This server enables AI assistants and development tools to search and retrieve information about SDK classes, functions, and code examples.

## Overview

This MCP server indexes and provides access to:
- **Symbols**: Classes, structs, functions, enums, and other symbols from both the Unreal SDK and OSS SDK documentation
- **Source Code**: Indexed source files from the AccelByte Unreal SDK repository
- **Code Snippets**: Tutorial code snippets extracted from the SDK repository

The server uses a cache-based approach for fast startup times. Cache files must be generated before running the server.

## Prerequisites

- **Node.js** (v18 or later)
- **npm** or **yarn**
- **Git** (for cloning the SDK repository during cache generation)
- **XML Documentation Files**: Doxygen XML files for both Unreal SDK and OSS SDK should be placed in:
  - `data/unreal-sdk/` - Unreal SDK XML files
  - `data/oss-sdk/` - OSS SDK XML files

## Installation

1. Clone or download this repository
2. Install dependencies:

```bash
npm install
```

## Cache Generation

Before running the server, you must generate the cache files. This is a one-time (or periodic) process that indexes all symbols, source files, and snippets.

### Generate All Caches

Run the cache generation script:

```bash
npm run generate-cache
```

Or directly:

```bash
node generateCache.js
```

This script will:
1. **Parse XML Documentation**: Extract symbols from Doxygen XML files for both Unreal SDK and OSS SDK
2. **Index Source Files**: Clone the AccelByte Unreal SDK repository (if needed) and index source code files
3. **Index Code Snippets**: Extract and index code snippets from tutorial modules

### Cache Files Generated

The following cache files are created in the `.cache/` directory:

- `unreal-sdk-symbols.json` - Parsed symbols from Unreal SDK XML
- `oss-sdk-symbols.json` - Parsed symbols from OSS SDK XML
- `source-index.json` - Index of source code files, classes, and methods
- `bytewars-snippets.json` - Index of code snippets from tutorial modules

### Cache Generation Notes

- Cache generation may take several minutes depending on the size of your XML files and repository
- The source repository is cloned to `.cache/accelbyte-unreal-sdk-plugin/` if it doesn't exist
- If cache generation fails, check that:
  - XML files are present in `data/unreal-sdk/` and `data/oss-sdk/`
  - You have network access to clone the GitHub repository
  - You have sufficient disk space

## Running the Server

Once cache files are generated, start the MCP server:

```bash
npm start
```

Or directly:

```bash
node server.js
```

The server runs using stdio transport, which is required for MCP clients like Cursor. The server will:
- Load all cache files on startup
- Display warnings if cache files are missing or empty
- Accept MCP protocol requests via stdin/stdout

### Server Startup

On startup, the server will log:
- Number of symbols loaded from each SDK
- Source index statistics (files, classes, methods)
- Snippet count

If any cache is missing, you'll see warnings instructing you to run `generateCache.js`.

## Tools

The server provides tools for searching and retrieving SDK information and for installing the Unreal SDK. Tools that return or suggest AccelByte code (search_symbols, search_snippets, search_example_components, describe_symbols, describe_example_components) include a top-level `sdkRequirement` field in their response stating that the AccelByte Unreal SDK (and OSS/NetworkUtilities if used) must be installed for the code to work and that `install_unreal_sdk` can be used if needed.

### 1. `search_symbols`

Search for symbols (classes, structs, functions, etc.) in the SDK documentation.

**Parameters:**
- `query` (required, string): Search query that matches symbol names, types, or descriptions
- `source` (optional, enum): Filter by SDK source - `"oss-sdk"` or `"unreal-sdk"`
- `type` (optional, enum): Filter by symbol type - `"class"`, `"struct"`, `"function"`, `"enum"`, `"namespace"`, `"variable"`
- `limit` (optional, number): Maximum results to return (default: 20)

**Returns:**
- Array of symbol results with:
  - `id`: Symbol identifier (e.g., `"FOnlineIdentityAccelByte@cpp"`)
  - `type`: Symbol type (e.g., `"class"`, `"struct"`)
  - `description`: Brief description extracted from XML documentation

**Example:**
```json
{
  "query": "login",
  "source": "oss-sdk",
  "type": "class",
  "limit": 10
}
```

**Scoring:**
- OSS SDK symbols are prioritized (receive +100 base score)
- Exact name matches score higher than partial matches
- Results are sorted by relevance score

### 2. `search_snippets`

Search for code snippets from tutorial modules by query, area, or tags.

**Parameters:**
- `query` (optional, string): Search query that matches snippet content, name, or function
- `area` (optional, string): Filter by area (e.g., `"auth"`, `"party"`, `"chat"`, `"session"`, `"store"`, `"cloudsave"`, `"statistics"`, `"friends"`, `"presence"`, `"matchmaking"`)
- `tags` (optional, array of strings): Filter by tags (all specified tags must match). Examples: `"authentication"`, `"login"`, `"multiplayer"`, `"messaging"`, `"storage"`, `"monetization"`
- `limit` (optional, number): Maximum results to return (default: 20)

**Returns:**
- Array of snippet results with:
  - `id`: Snippet identifier
  - `uri`: Resource URI for fetching the snippet
  - `name`: Snippet name
  - `area`: Functional area (e.g., `"access"`, `"monetization"`)
  - `function`: Function name
  - `file`: Source file name
  - `description`: Human-readable description

**Example:**
```json
{
  "query": "device id login",
  "area": "access",
  "tags": ["authentication"],
  "limit": 5
}
```

### 3. `describe_symbols`

Get detailed information about specific symbols, including their fields, methods, and related code snippets.

**Parameters:**
- `symbolIds` (required, array of strings): List of symbol IDs to describe (e.g., `["FOnlineIdentityAccelByte@cpp", "FOnlineSubsystemAccelByte@cpp"]`)
- `includeSnippets` (optional, boolean): Whether to include relevant snippet links (default: `true`)
- `snippetLimit` (optional, number): Maximum number of relevant snippets per symbol (default: 5)

**Returns:**
- Array of symbol descriptions with:
  - `id`: Symbol identifier
  - `name`: Full symbol name
  - `type`: Symbol type
  - `source`: SDK source (`"oss-sdk"` or `"unreal-sdk"`)
  - `uri`: Resource URI
  - `fields`: Object containing field definitions with types and descriptions
  - `methods`: Object containing method definitions with parameters, return types, and descriptions
  - `snippets`: Array of relevant code snippets that use this symbol
  - `snippetCount`: Number of snippets found

**Example:**
```json
{
  "symbolIds": ["FOnlineIdentityAccelByte@cpp"],
  "includeSnippets": true,
  "snippetLimit": 5
}
```

### 4. `install_unreal_sdk`

Download from GitHub and install AccelByte Unreal components into an Unreal project; optionally update `.uproject`, Build files, and DefaultEngine.ini. Supports the **AccelByte Game SDK**, **AccelByte OSS** (Online Subsystem), and **AccelByteNetworkUtilities**. All plugins are installed under `Plugins/Accelbyte/` with full integration (plugin entries, Build.cs, Target.cs, and default config where applicable).

**Parameters:**
- `projectPath` (required, string): Path to the Unreal project root (directory containing the `.uproject` file). Use an absolute path or a path relative to `workspaceRoot`.
- `components` (optional, array of strings): Components to install: `"sdk"` (AccelByte Game SDK), `"oss"` (Online Subsystem), `"networkUtilities"` (AccelByteNetworkUtilities). Default `["sdk"]`. Install order: networkUtilities, sdk, oss. Use `["sdk", "oss", "networkUtilities"]` for full integration.
- `workspaceRoot` (optional, string): Workspace root used to resolve a relative `projectPath`. Defaults to current working directory.
- `source` (optional, enum): How to get each component - `"release"` (default) = download latest release ZIP from GitHub; `"git"` = clone the repository via Git.
- `version` (optional, string): For `source: "release"`: tag name (e.g. `"v1.2.0"`). Omit for latest release. For `source: "git"`: branch or tag to clone. Applies to all components.
- `setupProjectFiles` (optional, boolean): If `true`, add plugins to `.uproject`, `Build.cs`, and `Target.cs`, and add default AccelByte config (and [OnlineSubsystem] when using OSS) to `DefaultEngine.ini`. Default `false`.
- `regenerateProjectFiles` (optional, boolean): If `true`, run UnrealVersionSelector (Windows) or GenerateProjectFiles (Mac) to regenerate the IDE project files (`.sln` / `.vcxproj`) after setup. Default `false`.

**Returns:**
- `success` (boolean): Whether the operation succeeded.
- `installedPaths` (array of strings, if success): Full paths to the installed plugin folders (e.g. `Project/Plugins/Accelbyte/AccelByteUe4Sdk`, `Project/Plugins/Accelbyte/OnlineSubsystemAccelByte`).
- `message` (string): Human-readable result or next steps.
- `setupDetails` (array, optional): When `setupProjectFiles` is true, list of changes made; when `regenerateProjectFiles` succeeds, includes the regeneration message.
- `regenerateResult` (object, optional): When `regenerateProjectFiles` is true, `{ success, message }` (and `stderr` on failure).

**Example (SDK only, default):**
```json
{
  "projectPath": "C:/MyGame",
  "source": "release",
  "setupProjectFiles": true
}
```

**Example (full integration: SDK + OSS + NetworkUtilities):**
```json
{
  "projectPath": "C:/MyGame",
  "components": ["sdk", "oss", "networkUtilities"],
  "source": "release",
  "setupProjectFiles": true,
  "regenerateProjectFiles": true
}
```

After installation, configure `DefaultEngine.ini` with your AGS credentials. See the [official AccelByte Unreal SDK install docs](https://docs.accelbyte.io/gaming-services/getting-started/setup-game-sdk/unreal-sdk) for manual steps and configuration.

## Resources

The server exposes several types of resources that can be listed and read:

### Symbol Resources

**URI Format:**
- `unreal-sdk/cpp://{symbolId}` - Unreal SDK symbols
- `oss-sdk/cpp://{symbolId}` - OSS SDK symbols

**Example:** `oss-sdk/cpp://FOnlineIdentityAccelByte@cpp`

**Content:** Full JSON representation of the symbol, including all fields, methods, and metadata.

### Source File Resources

**URI Format:**
- `source://{filePath}` - Direct file path (e.g., `source://Source/AccelByteWars/TutorialModules/Access/AuthEssentials/AuthEssentialsSubsystem.cpp`)
- `source://class/{ClassName}` - Class implementation lookup

**Content:** Full source code of the file in C++ format.

### Snippet Resources

**URI Format:**
- `snippet://{snippetId}` - Code snippet (e.g., `snippet://oss/access/login`)

**Content:** JSON object containing:
- Snippet metadata (id, name, area, function, file)
- File path and line numbers
- Tags and uses
- Associated symbols
- Full code content

## Usage Examples

### Example 1: Find Login Classes

```json
{
  "tool": "search_symbols",
  "arguments": {
    "query": "login",
    "source": "oss-sdk",
    "type": "class"
  }
}
```

### Example 2: Get Detailed Symbol Information

```json
{
  "tool": "describe_symbols",
  "arguments": {
    "symbolIds": ["FOnlineIdentityAccelByte@cpp"],
    "includeSnippets": true
  }
}
```

### Example 3: Find Authentication Snippets

```json
{
  "tool": "search_snippets",
  "arguments": {
    "area": "access",
    "tags": ["authentication", "login"],
    "limit": 10
  }
}
```

### Example 4: Read a Symbol Resource

```
Resource URI: oss-sdk/cpp://FOnlineIdentityAccelByte@cpp
```

Returns the full symbol definition as JSON.

### Example 5: Read a Code Snippet

```
Resource URI: snippet://oss/access/login
```

Returns the snippet with full code content and metadata.

## Troubleshooting

### Cache Files Missing

If you see warnings about missing cache files:
1. Ensure XML files are in `data/unreal-sdk/` and `data/oss-sdk/`
2. Run `npm run generate-cache` to regenerate all caches

### Empty Search Results

- Verify cache files were generated successfully
- Check that XML files contain the expected documentation
- Try broader search queries (fewer filters)

### Server Won't Start

- Check Node.js version: `node --version` (should be v18+)
- Verify dependencies are installed: `npm install`
- Check for syntax errors in cache files (may need to regenerate)

### Source Index Empty

- Ensure the GitHub repository can be cloned
- Check network connectivity
- Verify the repository path in `sourceIndexer.js` is correct

## Project Structure

```
.
├── server.js              # Main MCP server implementation
├── parser.js              # XML parser for symbol extraction
├── sourceIndexer.js       # Source code and snippet indexing
├── generateCache.js       # Cache generation script
├── package.json           # Node.js dependencies and scripts
├── data/                  # XML documentation files
│   ├── unreal-sdk/        # Unreal SDK XML files
│   └── oss-sdk/           # OSS SDK XML files
└── .cache/                # Generated cache files (gitignored)
    ├── unreal-sdk-symbols.json
    ├── oss-sdk-symbols.json
    ├── source-index.json
    └── bytewars-snippets.json
```

## License

ISC
