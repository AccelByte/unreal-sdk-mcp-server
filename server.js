import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { fileURLToPath } from "url";
import { dirname, join, basename } from "path";
import { loadSymbols } from "./parser.js";
import { indexSourceFiles, searchSourceFiles, getMethodImplementation, indexSnippets, searchSnippets } from "./sourceIndexer.js";

// Get the directory of this script file (not cwd)
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourcesDir = join(__dirname, "source");

// Resolve Documentation/xml relative to this script's location
const unrealSDKXmlDir = join(sourcesDir, "unreal-sdk");
const ossSDKDir = join(sourcesDir, "oss-sdk");

// Resolve SDK repository root - will clone from GitHub if needed
// Store in a cache directory relative to this script
const cacheDir = join(__dirname, "..", ".cache");
const repoRoot = cacheDir; // indexSourceFiles will handle cloning into .cache/accelbyte-unreal-sdk-plugin

// Load symbols from cache only (do not generate)
let unrealsdk_symbols = {};
let osssdk_symbols = {};

try {
  console.error("Loading symbols from cache...");
  unrealsdk_symbols = loadSymbols(unrealSDKXmlDir, "unreal-sdk", __dirname, true, true) || {};
  osssdk_symbols = loadSymbols(ossSDKDir, "oss-sdk", __dirname, true, true) || {};
  
  const unrealCount = Object.keys(unrealsdk_symbols).length;
  const ossCount = Object.keys(osssdk_symbols).length;
  console.error(`Loaded ${unrealCount} unreal-sdk symbols, ${ossCount} oss-sdk symbols from cache`);
  
  if (unrealCount === 0 && ossCount === 0) {
    console.error("WARNING: No symbols loaded from cache. Run 'node generateCache.js' to generate cache files.");
  }
} catch (error) {
  console.error(`ERROR: Failed to load symbols from cache: ${error.message}`);
  console.error(`Run 'node generateCache.js' to generate cache files.`);
  // Continue with empty symbols - server will still run but symbol features won't work
}

// Load source index from cache only (do not generate)
let sourceIndex = null;
try {
  console.error(`Loading source index from cache...`);
  sourceIndex = indexSourceFiles(cacheDir, true, true);
  const fileCount = Object.keys(sourceIndex.files).length;
  const classCount = Object.keys(sourceIndex.classes).length;
  const methodCount = Object.keys(sourceIndex.methods).length;
  console.error(`Source index loaded: ${fileCount} files, ${classCount} classes, ${methodCount} methods`);
  
  if (fileCount === 0) {
    console.error("WARNING: Source index is empty. Run 'node generateCache.js' to generate cache files.");
  }
} catch (error) {
  console.error(`ERROR: Failed to load source index from cache: ${error.message}`);
  console.error(`Run 'node generateCache.js' to generate cache files.`);
  // Continue without source index - server will still run but source code features won't be available
}

// Load snippet index from cache only (do not generate)
let snippetIndex = null;
try {
  console.error(`Loading snippet index from cache...`);
  snippetIndex = indexSnippets(__dirname, true, true);
  const snippetCount = Object.keys(snippetIndex.snippets).length;
  console.error(`Snippet index loaded: ${snippetCount} snippets`);
  
  if (snippetCount === 0) {
    console.error("WARNING: Snippet index is empty. Run 'node generateCache.js' to generate cache files.");
  }
} catch (error) {
  console.error(`ERROR: Failed to load snippet index from cache: ${error.message}`);
  console.error(`Run 'node generateCache.js' to generate cache files.`);
  // Continue without snippets
}

// Create the MCP server instance
const server = new Server(
  {
    name: "sdk-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  }
);

// Handler for resources/list - lists all available symbols and source files
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  const resources = [];

  Object.keys(osssdk_symbols).forEach((id) => {
    resources.push({
      uri: `oss-sdk/cpp://${id}`,
      name: osssdk_symbols[id].name,
      description: `${osssdk_symbols[id].type}: ${osssdk_symbols[id].name}`,
      mimeType: "application/json",
    });
  });
  // Add symbol resources (from XML documentation)
  Object.keys(unrealsdk_symbols).forEach((id) => {
    resources.push({
      uri: `unreal-sdk/cpp://${id}`,
      name: unrealsdk_symbols[id].name,
      description: `${unrealsdk_symbols[id].type}: ${unrealsdk_symbols[id].name}`,
      mimeType: "application/json",
    });
  });



  // Add source file resources
  if (sourceIndex) {
    Object.keys(sourceIndex.files).forEach((filePath) => {
      const file = sourceIndex.files[filePath];
      resources.push({
        uri: `source://${filePath}`,
        name: basename(filePath),
        description: `${file.type}: ${filePath} (${file.lines} lines)`,
        mimeType: "text/x-c++",
      });
    });

    // Add class implementation resources
    Object.keys(sourceIndex.classes).forEach((className) => {
      sourceIndex.classes[className].forEach((filePath) => {
        resources.push({
          uri: `source://class/${className}`,
          name: `${className} implementation`,
          description: `Implementation of ${className} in ${filePath}`,
          mimeType: "text/x-c++",
        });
      });
    });
  }

  // Add snippet resources
  if (snippetIndex) {
    Object.keys(snippetIndex.snippets).forEach((snippetId) => {
      const snippet = snippetIndex.snippets[snippetId];
      const tagsStr = snippet.tags.join(", ");
      const usesStr = snippet.uses.length > 0 ? ` | Uses: ${snippet.uses.join(", ")}` : "";
      resources.push({
        uri: snippet.uri,
        name: snippet.name,
        description: `Snippet: ${snippet.area}/${snippet.function} | Tags: ${tagsStr}${usesStr} | ${snippet.file}`,
        mimeType: "application/json",
      });
    });
  }

  return { resources };
});

// Handler for resources/read - returns symbol data or source code
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  // Handle symbol resources (unreal-sdk/cpp:// or oss-sdk/cpp://)
  if (uri.startsWith("unreal-sdk/cpp://")) {
    const id = uri.replace("unreal-sdk/cpp://", "");
    const symbol = unrealsdk_symbols[id];

    if (!symbol) {
      throw new Error(`Resource not found: ${uri}`);
    }

    return {
      contents: [
        {
          uri,
          mimeType: "application/json",
          text: JSON.stringify(symbol, null, 2),
        },
      ],
    };
  }

  if (uri.startsWith("oss-sdk/cpp://")) {
    const id = uri.replace("oss-sdk/cpp://", "");
    const symbol = osssdk_symbols[id];

    if (!symbol) {
      throw new Error(`Resource not found: ${uri}`);
    }

    return {
      contents: [
        {
          uri,
          mimeType: "application/json",
          text: JSON.stringify(symbol, null, 2),
        },
      ],
    };
  }

  // Handle snippet resources (snippet://)
  if (uri.startsWith("snippet://")) {
    if (!snippetIndex) {
      throw new Error("Snippet indexing is not available");
    }

    const snippetId = uri.replace("snippet://", "");
    const snippet = snippetIndex.snippets[snippetId];

    if (!snippet) {
      throw new Error(`Snippet not found: ${uri}`);
    }

    // Return snippet with metadata
    const snippetData = {
      id: snippet.id,
      uri: snippet.uri,
      name: snippet.name,
      area: snippet.area,
      function: snippet.function,
      file: snippet.file,
      filePath: snippet.filePath,
      startLine: snippet.startLine,
      endLine: snippet.endLine,
      language: snippet.language,
      tags: snippet.tags,
      uses: snippet.uses,
      symbols: snippet.symbols,
      content: snippet.content,
    };

    return {
      contents: [
        {
          uri,
          mimeType: "application/json",
          text: JSON.stringify(snippetData, null, 2),
        },
      ],
    };
  }

  // Handle source file resources (source://)
  if (uri.startsWith("source://")) {
    if (!sourceIndex) {
      throw new Error("Source code indexing is not available");
    }

    // Handle class lookup: source://class/ClassName
    if (uri.startsWith("source://class/")) {
      const className = uri.replace("source://class/", "");
      const files = sourceIndex.classes[className] || [];

      if (files.length === 0) {
        throw new Error(`No source files found for class: ${className}`);
      }

      // Return the first implementation file (usually the .cpp file)
      const implFile = files.find(f => f.endsWith(".cpp")) || files[0];
      const file = sourceIndex.files[implFile];

      if (!file) {
        throw new Error(`Source file not found: ${implFile}`);
      }

      return {
        contents: [
          {
            uri,
            mimeType: "text/x-c++",
            text: `// Source file: ${file.path}\n// Full path: ${file.fullPath}\n\n${file.content}`,
          },
        ],
      };
    }

    // Handle direct file path: source://path/to/file.cpp
    const filePath = uri.replace("source://", "");
    const file = sourceIndex.files[filePath];

    if (!file) {
      throw new Error(`Source file not found: ${filePath}`);
    }

    return {
      contents: [
        {
          uri,
          mimeType: "text/x-c++",
          text: file.content,
        },
      ],
    };
  }

  throw new Error(`Unknown resource URI format: ${uri}`);
});

// Handler for tools/list - lists all available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search_symbols",
        description: "Search for symbols in the SDK documentation by name, type, or description",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Search query (searches in symbol name, type, and description)",
            },
            type: {
              type: "string",
              description: "Filter by symbol type (class, struct, function, enum, etc.)",
              enum: ["class", "struct", "function", "enum", "namespace", "variable"],
            },
            limit: {
              type: "number",
              description: "Maximum number of results to return (default: 20)",
              default: 20,
            },
          },
          required: ["query"],
        },
      },
      {
        name: "search_source_code",
        description: "Search for classes, methods, or files in the source code repository",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Search query (class name, method name, or file path pattern)",
            },
            searchType: {
              type: "string",
              description: "Type of search to perform",
              enum: ["class", "method", "file", "all"],
              default: "all",
            },
          },
          required: ["query"],
        },
      },
      {
        name: "get_method_implementation",
        description: "Get the full implementation code for a specific method",
        inputSchema: {
          type: "object",
          properties: {
            className: {
              type: "string",
              description: "Name of the class containing the method",
            },
            methodName: {
              type: "string",
              description: "Name of the method to get implementation for",
            },
          },
          required: ["methodName"],
        },
      },
      {
        name: "search_snippets",
        description: "Search for code snippets by query, area, tags, or content. Helps find relevant code examples from the tutorial modules.",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Search query - searches in snippet name, function name, tags, area, content, and symbols. Leave empty to search by filters only.",
            },
            area: {
              type: "string",
              description: "Filter by area (e.g., 'auth', 'party', 'chat', 'session', 'store', 'cloudsave', 'statistics', 'friends', 'presence', 'matchmaking', etc.)",
            },
            tags: {
              type: "array",
              items: {
                type: "string",
              },
              description: "Filter by tags (all specified tags must match). Examples: 'authentication', 'login', 'multiplayer', 'messaging', 'storage', 'monetization', etc.",
            },
            limit: {
              type: "number",
              description: "Maximum number of results to return (default: 20)",
              default: 20,
            },
          },
          required: [],
        },
      },
      {
        name: "find_class",
        description: "Find all files related to a specific class (headers and implementations)",
        inputSchema: {
          type: "object",
          properties: {
            className: {
              type: "string",
              description: "Name of the class to find",
            },
          },
          required: ["className"],
        },
      },
    ],
  };
});

// Handler for tools/call - executes tool requests
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case "search_symbols": {
        const { query, type, limit = 20 } = args || {};
        const results = [];

        const searchLower = query?.toLowerCase() || "";
        
        for (const [id, symbol] of Object.entries(symbols)) {
          // Filter by type if specified
          if (type && symbol.type?.toLowerCase() !== type.toLowerCase()) {
            continue;
          }

          // Search in name, type, and description
          const nameMatch = symbol.name?.toLowerCase().includes(searchLower);
          const typeMatch = symbol.type?.toLowerCase().includes(searchLower);
          const descMatch = symbol.description?.toLowerCase().includes(searchLower);

          if (nameMatch || typeMatch || descMatch) {
            results.push({
              id,
              name: symbol.name,
              type: symbol.type,
              description: symbol.description || "",
              uri: `cpp://${id}`,
            });

            if (results.length >= limit) break;
          }
        }

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ results, count: results.length }, null, 2),
            },
          ],
        };
      }

      case "search_source_code": {
        if (!sourceIndex) {
          throw new Error("Source code indexing is not available");
        }

        const { query, searchType = "all" } = args || {};
        const results = [];

        if (searchType === "all" || searchType === "class") {
          const classMatches = Object.keys(sourceIndex.classes).filter((className) =>
            className.toLowerCase().includes(query.toLowerCase())
          );
          classMatches.forEach((className) => {
            sourceIndex.classes[className].forEach((filePath) => {
              results.push({
                type: "class",
                name: className,
                file: filePath,
                uri: `source://${filePath}`,
              });
            });
          });
        }

        if (searchType === "all" || searchType === "method") {
          const methodMatches = Object.keys(sourceIndex.methods).filter((methodName) =>
            methodName.toLowerCase().includes(query.toLowerCase())
          );
          methodMatches.forEach((methodName) => {
            sourceIndex.methods[methodName].forEach((filePath) => {
              results.push({
                type: "method",
                name: methodName,
                file: filePath,
                uri: `source://${filePath}`,
              });
            });
          });
        }

        if (searchType === "all" || searchType === "file") {
          const fileMatches = Object.keys(sourceIndex.files).filter((filePath) =>
            filePath.toLowerCase().includes(query.toLowerCase())
          );
          fileMatches.forEach((filePath) => {
            const file = sourceIndex.files[filePath];
            results.push({
              type: "file",
              name: basename(filePath),
              path: filePath,
              fileType: file.type,
              lines: file.lines,
              uri: `source://${filePath}`,
            });
          });
        }

        // Remove duplicates
        const uniqueResults = Array.from(
          new Map(results.map((r) => [`${r.type}:${r.name || r.path}`, r])).values()
        );

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ results: uniqueResults, count: uniqueResults.length }, null, 2),
            },
          ],
        };
      }

      case "get_method_implementation": {
        if (!sourceIndex) {
          throw new Error("Source code indexing is not available");
        }

        const { className, methodName } = args || {};

        if (className) {
          // Use the helper function if we have a class name
          const implementation = getMethodImplementation(sourceIndex, className, methodName);
          if (implementation) {
            return {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(implementation, null, 2),
                },
              ],
            };
          }
        }

        // Fallback: search in all files
        const methodFiles = sourceIndex.methods[methodName] || [];
        const implementations = [];

        for (const filePath of methodFiles) {
          const file = sourceIndex.files[filePath];
          if (!file) continue;

          // Try to extract the method implementation
          const methodRegex = new RegExp(
            `(${methodName}\\s*[^{]*\\{[^{}]*(?:\\{[^{}]*\\}[^{}]*)*\\})`,
            "gs"
          );
          const match = file.content.match(methodRegex);

          if (match) {
            implementations.push({
              file: filePath,
              methodName: methodName,
              implementation: match[0],
              className: className || "unknown",
            });
          }
        }

        if (implementations.length === 0) {
          throw new Error(`Method "${methodName}" not found${className ? ` in class "${className}"` : ""}`);
        }

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                implementations.length === 1 ? implementations[0] : { implementations },
                null,
                2
              ),
            },
          ],
        };
      }

      case "find_class": {
        if (!sourceIndex) {
          throw new Error("Source code indexing is not available");
        }

        const { className } = args || {};
        const files = sourceIndex.classes[className] || [];

        if (files.length === 0) {
          throw new Error(`Class "${className}" not found`);
        }

        const classFiles = files.map((filePath) => {
          const file = sourceIndex.files[filePath];
          return {
            path: filePath,
            type: file.type,
            lines: file.lines,
            uri: `source://${filePath}`,
            className: className,
          };
        });

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ className, files: classFiles }, null, 2),
            },
          ],
        };
      }

      case "search_snippets": {
        if (!snippetIndex) {
          throw new Error("Snippet indexing is not available");
        }

        const { query = "", area = null, tags = [], limit = 20 } = args || {};
        
        const results = searchSnippets(snippetIndex, {
          query,
          area,
          tags: Array.isArray(tags) ? tags : [],
          limit,
        });

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ 
                results, 
                count: results.length,
                query: query || null,
                filters: {
                  area: area || null,
                  tags: tags.length > 0 ? tags : null,
                },
              }, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ error: error.message }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

// Start the server with stdio transport (required for Cursor)
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Log to stderr (stdout is reserved for JSON-RPC messages in MCP)
  console.error("MCP server running (stdio transport)");
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
