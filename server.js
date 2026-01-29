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
import fs from "fs";
import { loadSymbols } from "./parser.js";
import { indexSnippets, searchSnippets, indexExampleComponents } from "./sourceIndexer.js";

// Get the directory of this script file (not cwd)
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourcesDir = join(__dirname, "data");

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

// Index example components (synchronously, no cache; folder is small)
let exampleComponentsIndex = {
  components: {},
  byService: {},
};
try {
  console.error(`Indexing example components...`);
  exampleComponentsIndex = indexExampleComponents(__dirname) || exampleComponentsIndex;
  const componentCount = Object.keys(exampleComponentsIndex.components || {}).length;
  console.error(`Example components indexed: ${componentCount} components`);
} catch (error) {
  console.error(`ERROR: Failed to index example components: ${error.message}`);
  // Continue without example components
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

  // Add example component resources
  if (exampleComponentsIndex && exampleComponentsIndex.components) {
    Object.values(exampleComponentsIndex.components).forEach((component) => {
      const service = component.service || "unknown-service";
      const description = component.description || "";
      resources.push({
        uri: `example://${component.id}`,
        name: component.id,
        description: `Example component (${service}): ${description}`,
        mimeType: "application/json",
      });
      
      // Add source file resources for each component file
      if (component.files && Array.isArray(component.files)) {
        component.files.forEach((file) => {
          const fileName = basename(file);
          resources.push({
            uri: `example-file://${file}`,
            name: fileName,
            description: `Example component source: ${component.id} - ${fileName}`,
            mimeType: file.endsWith(".h") || file.endsWith(".cpp") ? "text/x-c++" : "text/plain",
          });
        });
      }
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

  // Handle example component resources (example://)
  if (uri.startsWith("example://")) {
    if (!exampleComponentsIndex || !exampleComponentsIndex.components) {
      throw new Error("Example components index is not available");
    }

    const componentId = uri.replace("example://", "");
    const component = exampleComponentsIndex.components[componentId];

    if (!component) {
      throw new Error(`Example component not found: ${uri}`);
    }

    return {
      contents: [
        {
          uri,
          mimeType: "application/json",
          text: JSON.stringify(component, null, 2),
        },
      ],
    };
  }

  // Handle example component source files (example-file://)
  if (uri.startsWith("example-file://")) {
    if (!exampleComponentsIndex || !exampleComponentsIndex.components) {
      throw new Error("Example components index is not available");
    }
    
    const relativePath = uri.replace("example-file://", "");
    
    // Find which component owns this file
    let fileContent = null;
    let fullPath = null;
    
    for (const component of Object.values(exampleComponentsIndex.components)) {
      const fileIndex = component.files.indexOf(relativePath);
      if (fileIndex !== -1) {
        fullPath = component.filePaths[fileIndex];
        break;
      }
    }
    
    if (!fullPath || !fs.existsSync(fullPath)) {
      throw new Error(`Example component source file not found: ${uri}`);
    }
    
    fileContent = fs.readFileSync(fullPath, "utf8");
    const mimeType = relativePath.endsWith(".h") || relativePath.endsWith(".cpp") 
      ? "text/x-c++" 
      : "text/plain";
    
    return {
      contents: [{
        uri,
        mimeType,
        text: fileContent,
      }],
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
            source: {
              type: "string",
              description: "Filter by SDK source (oss-sdk or unreal-sdk)",
              enum: ["oss-sdk", "unreal-sdk"],
            },
            type: {
              type: "string",
              description: "Filter by symbol type (class, struct, function, enum, namespace, variable)",
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
        name: "search_example_components",
        description: "Search for ready-made, drop-in example components (full Unreal C++/Slate panels and controllers) that implement common AccelByte flows such as showing player achievements, stats, friends, login queue, etc. Returns component metadata including class names, public interfaces, and a fileResourceUris array. IMPORTANT: Use the standard MCP resources/read handler with the fileResourceUris (e.g., 'example-file://ComponentName.h') to fetch the actual source code files (.h and .cpp). The fileResourceUris are MCP resource URIs, not tool calls.",
        inputSchema: {
          type: "object",
          properties: {
            intent: {
              type: "string",
              description: "Natural language description of what the component should do (e.g. 'show my player achievements', 'display login queue status', 'show my player stats on a panel').",
            },
            service: {
              type: "string",
              description: "Optional filter by AccelByte service (e.g. 'achievements', 'statistics', 'friends', 'auth', 'store').",
            },
            language: {
              type: "string",
              description: "Optional filter by implementation language (e.g. 'unreal-cpp').",
            },
            limit: {
              type: "number",
              description: "Maximum number of components to return (default: 5).",
              default: 5,
            },
          },
          required: ["intent"],
        },
      },
      {
        name: "describe_example_components",
        description: "Fetch the actual source code content of example component files. Use this tool with fileResourceUris from search_example_components results (e.g., 'example-file://AccelByteAchievementsPanel.h') to get the complete .h or .cpp file content.",
        inputSchema: {
          type: "object",
          properties: {
            fileResourceUris: {
              type: "array",
              items: {
                type: "string",
              },
              description: "Array of fileResourceUris from search_example_components results (e.g., ['example-file://AccelByteAchievementsPanel.h', 'example-file://AccelByteAchievementsPanel.cpp'])",
            },
          },
          required: ["fileResourceUris"],
        },
      },
      {
        name: "describe_symbols",
        description: "Get full descriptions of symbols by their IDs, including fields, methods, and links to relevant code snippets that use them.",
        inputSchema: {
          type: "object",
          properties: {
            symbolIds: {
              type: "array",
              items: {
                type: "string",
              },
              description: "List of symbol IDs to describe (e.g., ['AccelByte::FAccelByteMessagingSystem@cpp', 'AccelByte::FOnlineIdentityAccelByte@cpp'])",
            },
            includeSnippets: {
              type: "boolean",
              description: "Whether to include relevant snippet links (default: true)",
              default: true,
            },
            snippetLimit: {
              type: "number",
              description: "Maximum number of relevant snippets to return per symbol (default: 5)",
              default: 5,
            },
          },
          required: ["symbolIds"],
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
        const { query, source, type, limit = 20 } = args || {};
        const scoredResults = [];

        const searchLower = query?.toLowerCase() || "";
        
        // Select which symbol sets to search based on source filter
        let symbolsToSearch = {};
        if (source === "unreal-sdk") {
          symbolsToSearch = unrealsdk_symbols;
        } else if (source === "oss-sdk") {
          symbolsToSearch = osssdk_symbols;
        } else {
          // No source filter - combine both
          symbolsToSearch = { ...unrealsdk_symbols, ...osssdk_symbols };
        }
        
        for (const [id, symbol] of Object.entries(symbolsToSearch)) {
          // Filter by type if specified
          if (type && symbol.type?.toLowerCase() !== type.toLowerCase()) {
            continue;
          }

          // Search in name, type, and description
          const nameMatch = symbol.name?.toLowerCase().includes(searchLower);
          const typeMatch = symbol.type?.toLowerCase().includes(searchLower);
          const descMatch = symbol.description?.toLowerCase().includes(searchLower);

          if (nameMatch || typeMatch || descMatch) {
            // Determine which SDK this symbol belongs to
            const isOssSdk = !unrealsdk_symbols[id];
            const uri = isOssSdk 
              ? `oss-sdk/cpp://${id}` 
              : `unreal-sdk/cpp://${id}`;
            
            // Determine source for result
            const symbolSource = isOssSdk ? "oss-sdk" : "unreal-sdk";
            
            // Calculate score - prioritize OSS SDK results
            let score = 0;
            
            // Base score boost for OSS SDK (higher priority)
            if (isOssSdk) {
              score += 100;
            }
            
            // Match quality scoring
            if (nameMatch) {
              // Exact name match gets highest score
              if (symbol.name?.toLowerCase() === searchLower) {
                score += 50;
              } else {
                score += 30;
              }
            }
            if (typeMatch) {
              score += 10;
            }
            if (descMatch) {
              score += 5;
            }
            
            scoredResults.push({
              id,
              type: symbol.type,
              description: symbol.description || "",
              score: score,
            });
          }
        }

        // Sort by score (descending) and apply limit
        scoredResults.sort((a, b) => b.score - a.score);
        const results = scoredResults.slice(0, limit).map(({ score, ...result }) => result);

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ 
                results, 
                count: results.length,
                filters: {
                  source: source || null,
                  type: type || null,
                },
              }, null, 2),
            },
          ],
        };
      }

      case "search_example_components": {
        const { intent = "", service = null, language = null, limit = 5 } = args || {};

        if (!exampleComponentsIndex || !exampleComponentsIndex.components) {
          throw new Error("Example components index is not available");
        }

        const intentLower = (intent || "").toLowerCase();
        const tokens = intentLower.split(/\s+/).filter(Boolean);

        const scoredComponents = [];

        const buildIntegrationHint = (component) => {
          const controller = component.controllerClass || "your controller class";
          const uiWidget = component.uiWidgetClass || null;
          const hasInitialise = component.publicInterface && component.publicInterface.initialise;
          const hasBuildWidget = component.publicInterface && component.publicInterface.buildWidget;
          const hasShow = component.publicInterface && component.publicInterface.show;

          const parts = [];

          // High-level one-liner
          parts.push(
            `Use ${controller}` +
              (uiWidget ? ` and ${uiWidget}` : "") +
              ` as a drop-in component after AccelByte login.`
          );

          if (hasInitialise) {
            parts.push(
              `After obtaining an AccelByte::FApiClientPtr on login, call 'initialise' (${component.publicInterface.initialise}) once to bind the SDK client.`
            );
          }

          if (hasBuildWidget) {
            parts.push(
              `Call 'buildWidget' (${component.publicInterface.buildWidget}) to get an SWidget and add it to your HUD or viewport.`
            );
          } else if (hasShow) {
            parts.push(
              `Call 'show' (${component.publicInterface.show}) from your UI flow to display the panel.`
            );
          }

          if (component.service === "achievements") {
            parts.push(
              `This component already handles querying achievement definitions and user progress; you usually don't need to call the achievements API directly.`
            );
          }

          return parts.join(" ");
        };

        for (const component of Object.values(exampleComponentsIndex.components)) {
          // Filter by service if specified
          if (service && component.service && component.service !== service) {
            continue;
          }

          // Filter by language if specified
          if (language && component.language && component.language !== language) {
            continue;
          }

          let score = 0;
          let matched = false;
          const matchedTokens = new Set();

          const haystack =
            [
              component.description || "",
              component.id || "",
              component.service || "",
              component.controllerClass || "",
              component.uiWidgetClass || "",
              component.rowWidgetClass || "",
            ]
              .join(" ")
              .toLowerCase();

          if (tokens.length > 0) {
            for (const token of tokens) {
              if (!token) continue;
              const occurrences =
                haystack.split(token).length - 1;
              if (occurrences > 0) {
                score += occurrences * 10;
                matched = true;
                matchedTokens.add(token);
              }
            }
          } else {
            // No intent tokens provided, treat as a generic query
            matched = true;
          }

          // Boost score if service matches exactly
          if (service && component.service === service) {
            score += 50;
          }

          if (!matched) {
            continue;
          }

          // Determine match type and recommendation strength
          let matchType = "reference_example";
          let isRecommended = component.recommended;

          if (tokens.length > 0 && matchedTokens.size > 0) {
            const coverage = matchedTokens.size / tokens.length;
            if (coverage >= 0.6 && score >= 40) {
              matchType = "exact_solution";
            } else if (coverage > 0) {
              matchType = "partial_match";
            }
          }

          if (!isRecommended && matchType === "exact_solution") {
            isRecommended = true;
          }

          scoredComponents.push({
            component,
            score,
            matchType,
            recommended: isRecommended,
          });
        }

        scoredComponents.sort((a, b) => b.score - a.score);

        const limitedResults = scoredComponents.slice(0, limit).map(({ component, matchType, recommended }) => {
          // Build file resource URIs for fetching actual source code
          const fileResourceUris = (component.files || []).map(file => 
            `example-file://${file}`
          );
          
          // Do not expose internal filePaths unless needed; keep relative files
          return {
            id: component.id,
            service: component.service,
            provider: component.provider,
            language: component.language,
            description: component.description,
            controllerClass: component.controllerClass,
            entryStruct: component.entryStruct,
            uiWidgetClass: component.uiWidgetClass,
            rowWidgetClass: component.rowWidgetClass,
            publicInterface: component.publicInterface,
            asyncState: component.asyncState,
            dataModel: component.dataModel,
            files: component.files,
            fileResourceUris: fileResourceUris,
            drop_in_ready: component.dropInReady !== false,
            recommended: !!recommended,
            match_type: matchType,
            integration_hint: buildIntegrationHint(component),
            // Resource URI for fetching full metadata/code if needed
            resourceUri: `example://${component.id}`,
          };
        });

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  results: limitedResults,
                  count: limitedResults.length,
                  intent: intent || null,
                  filters: {
                    service: service || null,
                    language: language || null,
                  },
                },
                null,
                2
              ),
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

      case "describe_symbols": {
        const { symbolIds, includeSnippets = true, snippetLimit = 5 } = args || {};
        
        if (!Array.isArray(symbolIds) || symbolIds.length === 0) {
          throw new Error("symbolIds must be a non-empty array");
        }

        const results = [];

        for (const symbolId of symbolIds) {
          // Find symbol in either SDK
          let symbol = unrealsdk_symbols[symbolId] || osssdk_symbols[symbolId];
          
          if (!symbol) {
            results.push({
              id: symbolId,
              error: "Symbol not found",
            });
            continue;
          }

          // Determine which SDK this symbol belongs to
          const source = unrealsdk_symbols[symbolId] ? "unreal-sdk" : "oss-sdk";
          const uri = `${source}/cpp://${symbolId}`;

          // Extract symbol name without @cpp suffix for matching
          const symbolName = symbol.name;
          const symbolNameParts = symbolName.split("::");
          const baseName = symbolNameParts[symbolNameParts.length - 1];
          const namespace = symbolNameParts.length > 1 ? symbolNameParts.slice(0, -1).join("::") : "";

          // Find relevant snippets
          let relevantSnippets = [];
          if (includeSnippets && snippetIndex) {
            for (const [snippetId, snippet] of Object.entries(snippetIndex.snippets)) {
              let matches = false;
              
              // Check if symbol name appears in snippet content
              if (snippet.content && snippet.content.includes(symbolName)) {
                matches = true;
              } else if (snippet.content && snippet.content.includes(baseName)) {
                matches = true;
              }
              
              // Check if symbol is in snippet's symbols metadata
              if (snippet.symbols) {
                const allSymbols = [
                  ...(snippet.symbols.classes || []),
                  ...(snippet.symbols.methods || []),
                  ...(snippet.symbols.functions || []),
                ];
                
                if (allSymbols.some(s => 
                  s === symbolName || 
                  s === baseName || 
                  s.includes(symbolName) ||
                  symbolName.includes(s)
                )) {
                  matches = true;
                }
              }

              if (matches) {
                relevantSnippets.push({
                  id: snippet.id,
                  uri: snippet.uri,
                  name: snippet.name,
                  area: snippet.area,
                  function: snippet.function,
                  file: snippet.file,
                  description: `${snippet.area}/${snippet.function} - ${snippet.name}`,
                });
              }
            }

            // Limit snippets and sort by relevance (exact name matches first)
            relevantSnippets = relevantSnippets
              .sort((a, b) => {
                const aExact = a.name.includes(symbolName) || a.name.includes(baseName);
                const bExact = b.name.includes(symbolName) || b.name.includes(baseName);
                if (aExact && !bExact) return -1;
                if (!aExact && bExact) return 1;
                return 0;
              })
              .slice(0, snippetLimit);
          }

          results.push({
            id: symbolId,
            name: symbol.name,
            type: symbol.type,
            source: source,
            uri: uri,
            fields: symbol.fields || {},
            methods: symbol.methods || {},
            snippets: relevantSnippets,
            snippetCount: relevantSnippets.length,
          });
        }

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ 
                symbols: results,
                count: results.length,
              }, null, 2),
            },
          ],
        };
      }

      case "describe_example_components": {
        const { fileResourceUris } = args || {};
        
        if (!Array.isArray(fileResourceUris) || fileResourceUris.length === 0) {
          throw new Error("fileResourceUris must be a non-empty array");
        }
        
        if (!exampleComponentsIndex || !exampleComponentsIndex.components) {
          throw new Error("Example components index is not available");
        }
        
        const results = [];
        
        for (const fileResourceUri of fileResourceUris) {
          if (!fileResourceUri.startsWith("example-file://")) {
            results.push({
              fileResourceUri: fileResourceUri,
              error: `Invalid fileResourceUri format. Expected 'example-file://...', got: ${fileResourceUri}`,
            });
            continue;
          }
          
          const relativePath = fileResourceUri.replace("example-file://", "");
          
          // Find which component owns this file
          let fileContent = null;
          let fullPath = null;
          let componentId = null;
          
          for (const component of Object.values(exampleComponentsIndex.components)) {
            const fileIndex = component.files.indexOf(relativePath);
            if (fileIndex !== -1) {
              fullPath = component.filePaths[fileIndex];
              componentId = component.id;
              break;
            }
          }
          
          if (!fullPath || !fs.existsSync(fullPath)) {
            results.push({
              fileResourceUri: fileResourceUri,
              relativePath: relativePath,
              error: `Example component source file not found`,
            });
            continue;
          }
          
          fileContent = fs.readFileSync(fullPath, "utf8");
          const mimeType = relativePath.endsWith(".h") || relativePath.endsWith(".cpp") 
            ? "text/x-c++" 
            : "text/plain";
          
          results.push({
            fileResourceUri: fileResourceUri,
            componentId: componentId,
            relativePath: relativePath,
            mimeType: mimeType,
            content: fileContent,
            lineCount: fileContent.split("\n").length,
          });
        }
        
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                files: results,
                count: results.length,
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
