import fs from "fs";
import path from "path";
import { execSync } from "child_process";

const GITHUB_REPO_URL = "https://github.com/AccelByte/accelbyte-unreal-bytewars-game.git";
const REPO_NAME = "accelbyte-unreal-bytewars-game";
const REPO_BRANCH = "tutorialmodules";

/**
 * Ensures the GitHub repository is cloned and up-to-date
 * Returns the path to the repository root
 */
function ensureRepositoryCloned(baseDir, repoUrl = GITHUB_REPO_URL) {
  // Ensure cache directory exists
  console.error(`Ensuring cache directory exists: ${baseDir}`);
  if (!fs.existsSync(baseDir)) {
    console.error(`Creating cache directory: ${baseDir}`);
    fs.mkdirSync(baseDir, { recursive: true });
  }
  
  const repoPath = path.join(baseDir, REPO_NAME);
  console.error(`Repository path: ${repoPath}`);
  
  if (!fs.existsSync(repoPath)) {
    console.error(`Repository not found. Cloning from ${repoUrl}...`);
    try {
      // Check if git is available
      try {
        execSync("git --version", { stdio: 'pipe' });
      } catch (gitCheckError) {
        throw new Error("Git is not available. Please install Git to enable source code indexing.");
      }
      
      execSync(`git clone --depth 1 --branch ${REPO_BRANCH} ${repoUrl} "${repoPath}"`, {
        stdio: 'inherit',
        cwd: baseDir,
        timeout: 60000 // 60 second timeout
      });
      console.error(`Repository cloned successfully to ${repoPath}`);
    } catch (error) {
      const errorMsg = `Failed to clone repository: ${error.message}. ` +
                      `Make sure Git is installed and the repository URL is accessible.`;
      console.error(`ERROR: ${errorMsg}`);
      throw new Error(errorMsg);
    }
  } else {
    console.error(`Repository already exists at ${repoPath}`);
    // Check if it's a git repository and try to update
    const gitPath = path.join(repoPath, ".git");
    if (fs.existsSync(gitPath)) {
      try {
        console.error(`Updating repository at ${repoPath}...`);
        execSync(`git fetch origin ${REPO_BRANCH}`, { cwd: repoPath, stdio: 'pipe', timeout: 30000 });
        execSync(`git reset --hard origin/${REPO_BRANCH}`, { cwd: repoPath, stdio: 'pipe' });
        console.error("Repository updated successfully");
      } catch (error) {
        console.error(`Warning: Could not update repository: ${error.message}. Using existing files.`);
        // Continue anyway with existing files
      }
    } else {
      console.error(`Warning: ${repoPath} exists but is not a git repository. Using existing files.`);
    }
  }
  
  // Verify the repository has the expected structure
  const sourceDir = path.join(repoPath, "Source", "AccelByteWars", "TutorialModules");
  if (!fs.existsSync(sourceDir)) {
    throw new Error(`Repository structure is incorrect. Expected Source/AccelByteWars/TutorialModules directory not found at: ${sourceDir}`);
  }
  
  return repoPath;
}

/**
 * Get the cache file path for source index
 */
function getSourceIndexCacheFile(baseDir) {
  const cacheDir = path.join(baseDir, ".cache");
  return path.join(cacheDir, "source-index.json");
}

/**
 * Save source index to disk cache
 */
function saveSourceIndexCache(baseDir, sourceIndex) {
  try {
    const cacheFile = getSourceIndexCacheFile(baseDir);
    const cacheDir = path.dirname(cacheFile);
    
    // Ensure cache directory exists
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }
    
    const cacheData = {
      version: "1.0",
      indexedAt: new Date().toISOString(),
      fileCount: Object.keys(sourceIndex.files).length,
      classCount: Object.keys(sourceIndex.classes).length,
      methodCount: Object.keys(sourceIndex.methods).length,
      index: sourceIndex,
    };
    
    fs.writeFileSync(cacheFile, JSON.stringify(cacheData, null, 2), "utf8");
    console.error(`Source index cache saved to: ${cacheFile}`);
  } catch (error) {
    console.error(`Failed to save source index cache: ${error.message}`);
  }
}

/**
 * Load source index from disk cache
 */
function loadSourceIndexCache(baseDir) {
  try {
    const cacheFile = getSourceIndexCacheFile(baseDir);
    
    if (!fs.existsSync(cacheFile)) {
      return null;
    }
    
    const cacheData = JSON.parse(fs.readFileSync(cacheFile, "utf8"));
    console.error(`Source index cache loaded from: ${cacheFile} (${cacheData.fileCount} files, ${cacheData.classCount} classes, ${cacheData.methodCount} methods)`);
    return cacheData.index;
  } catch (error) {
    console.error(`Failed to load source index cache: ${error.message}`);
    return null;
  }
}

/**
 * Check if source index cache is still valid
 */
function isSourceIndexCacheValid(baseDir) {
  try {
    const cacheFile = getSourceIndexCacheFile(baseDir);
    const repoPath = path.join(baseDir, "..", ".cache", REPO_NAME);
    const tutorialModulesDir = path.join(repoPath, "Source", "AccelByteWars", "TutorialModules");
    
    if (!fs.existsSync(cacheFile) || !fs.existsSync(tutorialModulesDir)) {
      return false;
    }
    
    const cacheStats = fs.statSync(cacheFile);
    const cacheTime = cacheStats.mtime.getTime();
    
    // Check if any source file has been modified since cache was created
    function checkDirectory(dir) {
      if (!fs.existsSync(dir)) {
        return false;
      }
      
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory()) {
          if (!checkDirectory(fullPath)) {
            return false;
          }
        } else if (entry.isFile() && (entry.name.endsWith(".h") || entry.name.endsWith(".cpp"))) {
          const fileStats = fs.statSync(fullPath);
          if (fileStats.mtime.getTime() > cacheTime) {
            return false; // Source file is newer than cache
          }
        }
      }
      
      return true;
    }
    
    return checkDirectory(tutorialModulesDir);
  } catch (error) {
    console.error(`Error checking source index cache validity: ${error.message}`);
    return false;
  }
}

/**
 * Generate source index cache (force regeneration, ignores existing cache)
 */
export function generateSourceIndexCache(baseDir) {
  console.error(`Generating source index cache...`);
  
  // Ensure repository is cloned/updated from GitHub
  let repoRoot;
  try {
    repoRoot = ensureRepositoryCloned(baseDir, GITHUB_REPO_URL);
    console.error(`Repository root resolved to: ${repoRoot}`);
  } catch (error) {
    throw new Error(`Failed to ensure repository is cloned: ${error.message}`);
  }

  if (!fs.existsSync(repoRoot)) {
    throw new Error(`Repository root does not exist: ${repoRoot}`);
  }

  return buildSourceIndex(repoRoot, baseDir, false);
}

/**
 * Build source index from repository (internal function)
 */
function buildSourceIndex(repoRoot, baseDir) {
  const sourceIndex = {
    files: {},
    methods: {},  // Method name -> [file paths where it's implemented]
    classes: {},  // Class name -> file paths
  };

  // Directory to scan for source files
  const tutorialModulesDir = path.join(repoRoot, "Source", "AccelByteWars", "TutorialModules");
  
  console.error(`Looking for source directory:`);
  console.error(`  TutorialModules: ${tutorialModulesDir} (exists: ${fs.existsSync(tutorialModulesDir)})`);

  function scanDirectory(dir, relativePath = "") {
    if (!fs.existsSync(dir)) {
      console.error(`Directory does not exist: ${dir}`);
      return;
    }

    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      // Build relative path from Source/AccelByteWars/TutorialModules
      const relPath = relativePath 
        ? path.join(relativePath, entry.name)
        : entry.name;

      if (entry.isDirectory()) {
        scanDirectory(fullPath, relPath);
      } else if (entry.isFile() && (entry.name.endsWith(".h") || entry.name.endsWith(".cpp"))) {
        // Index the file
        const fileContent = fs.readFileSync(fullPath, "utf8");
        const fileType = entry.name.endsWith(".h") ? "header" : "implementation";
        
        // Extract class/method information
        const metadata = extractCodeMetadata(fileContent, entry.name);
        
        sourceIndex.files[relPath] = {
          path: relPath,
          fullPath: fullPath,
          type: fileType,
          size: fileContent.length,
          lines: fileContent.split("\n").length,
          content: fileContent,
          metadata: metadata,
          // Extract relevant snippets (class definitions, key methods)
          snippets: extractRelevantSnippets(fileContent, entry.name),
        };

        // Index methods and classes for easy lookup
        if (metadata.classes && Array.isArray(metadata.classes)) {
          metadata.classes.forEach(className => {
            if (!className || typeof className !== 'string') return;
            // Ensure it's always an array, even if it was previously set incorrectly
            if (!Array.isArray(sourceIndex.classes[className])) {
              sourceIndex.classes[className] = [];
            }
            // Avoid duplicates
            if (!sourceIndex.classes[className].includes(relPath)) {
              sourceIndex.classes[className].push(relPath);
            }
          });
        }

        if (metadata.methods && Array.isArray(metadata.methods)) {
          metadata.methods.forEach(methodName => {
            if (!methodName || typeof methodName !== 'string') return;
            // Ensure it's always an array, even if it was previously set incorrectly
            if (!Array.isArray(sourceIndex.methods[methodName])) {
              sourceIndex.methods[methodName] = [];
            }
            // Avoid duplicates
            if (!sourceIndex.methods[methodName].includes(relPath)) {
              sourceIndex.methods[methodName].push(relPath);
            }
          });
        }
      }
    }
  }

  // Scan TutorialModules directory
  if (fs.existsSync(tutorialModulesDir)) {
    console.error(`Scanning TutorialModules directory: ${tutorialModulesDir}`);
    scanDirectory(tutorialModulesDir, "");
  } else {
    const errorMsg = `TutorialModules directory not found: ${tutorialModulesDir}. Repository may not be cloned correctly.`;
    console.error(`ERROR: ${errorMsg}`);
    throw new Error(errorMsg);
  }

  if (Object.keys(sourceIndex.files).length === 0) {
    throw new Error(`No source files were indexed. Check that the repository structure is correct.`);
  }

  // Save to cache
  saveSourceIndexCache(baseDir, sourceIndex);

  return sourceIndex;
}

/**
 * Indexes C++ source files from the SDK repository
 * Clones from GitHub if not present, or updates existing clone
 * Uses cache if available and valid
 */
export function indexSourceFiles(baseDir, useCache = true, loadOnly = false) {
  console.error(`indexSourceFiles called with baseDir: ${baseDir}, useCache: ${useCache}, loadOnly: ${loadOnly}`);
  
  // Try to load from cache first
  if (useCache && isSourceIndexCacheValid(baseDir)) {
    const cachedIndex = loadSourceIndexCache(baseDir);
    if (cachedIndex) {
      console.error(`Using cached source index`);
      return cachedIndex;
    }
  }
  
  // If loadOnly is true, don't generate cache - throw error
  if (loadOnly) {
    throw new Error(`Source index cache not found. Run 'node generateCache.js' to generate cache files.`);
  }
  
  // Otherwise, generate cache
  if (useCache) {
    console.error(`Cache is invalid or missing, re-indexing source files...`);
  }
  
  // Ensure repository is cloned/updated from GitHub
  let repoRoot;
  try {
    repoRoot = ensureRepositoryCloned(baseDir, GITHUB_REPO_URL);
    console.error(`Repository root resolved to: ${repoRoot}`);
  } catch (error) {
    throw new Error(`Failed to ensure repository is cloned: ${error.message}`);
  }

  if (!fs.existsSync(repoRoot)) {
    throw new Error(`Repository root does not exist: ${repoRoot}`);
  }

  // Build index from repository
  return buildSourceIndex(repoRoot, baseDir);
}

/**
 * Extract metadata from C++ source code
 */
function extractCodeMetadata(content, filename) {
  const metadata = {
    classes: [],
    methods: [],
    includes: [],
    namespaces: [],
  };

  // Extract class/struct definitions
  const classRegex = /(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_:]*)/g;
  let match;
  const seenClasses = new Set(); // Avoid duplicates
  while ((match = classRegex.exec(content)) !== null) {
    const className = match[1];
    if (className && !seenClasses.has(className)) {
      metadata.classes.push(className);
      seenClasses.add(className);
    }
  }

  // Extract method/function definitions (simplified)
  const methodRegex = /(?:^|\s)([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)(?:\s*const)?\s*{/gm;
  const seenMethods = new Set(); // Avoid duplicates
  while ((match = methodRegex.exec(content)) !== null) {
    const methodName = match[1];
    // Filter out common keywords and types, and avoid duplicates
    if (methodName && 
        !["if", "for", "while", "switch", "return", "const", "virtual", "static"].includes(methodName) &&
        !seenMethods.has(methodName)) {
      metadata.methods.push(methodName);
      seenMethods.add(methodName);
    }
  }

  // Extract includes
  const includeRegex = /#include\s+[<"]([^>"]+)[>"]/g;
  while ((match = includeRegex.exec(content)) !== null) {
    metadata.includes.push(match[1]);
  }

  // Extract namespaces
  const namespaceRegex = /namespace\s+([A-Za-z_][A-Za-z0-9_]*)/g;
  while ((match = namespaceRegex.exec(content)) !== null) {
    metadata.namespaces.push(match[1]);
  }

  return metadata;
}

/**
 * Extract relevant code snippets for quick reference
 */
function extractRelevantSnippets(content, filename) {
  const snippets = {
    classDefinition: "",
    keyMethods: [],
  };

  // Extract class definition (first class in file)
  const classDefMatch = content.match(/(?:class|struct)[^{]+\{[^}]*\{/s);
  if (classDefMatch) {
    snippets.classDefinition = classDefMatch[0].substring(0, 500); // Limit size
  }

  // Extract method implementations for key methods
  const keyMethodNames = [
    "LoginWithDeviceId",
    "GetUserRecord",
    "CreateAccelByteInstance",
    "GetUserApi",
    "GetCloudSaveApi",
  ];

  keyMethodNames.forEach(methodName => {
    // Match method implementation (simplified regex)
    const methodRegex = new RegExp(
      `(${methodName}\\s*[^{]*\\{[^{}]*(?:\\{[^{}]*\\}[^{}]*)*\\})`,
      "gs"
    );
    const methodMatch = content.match(methodRegex);
    if (methodMatch) {
      snippets.keyMethods.push({
        name: methodName,
        snippet: methodMatch[0].substring(0, 1000), // Limit size
      });
    }
  });

  return snippets;
}

/**
 * Find source files by class name, method name, or file path pattern
 */
export function searchSourceFiles(sourceIndex, query) {
  const results = [];

  // Search by class name
  if (sourceIndex.classes[query]) {
    sourceIndex.classes[query].forEach(filePath => {
      results.push({
        type: "class",
        match: query,
        file: filePath,
        ...sourceIndex.files[filePath],
      });
    });
  }

  // Search by method name
  if (sourceIndex.methods[query]) {
    sourceIndex.methods[query].forEach(filePath => {
      results.push({
        type: "method",
        match: query,
        file: filePath,
        ...sourceIndex.files[filePath],
      });
    });
  }

  // Search by file path pattern
  Object.keys(sourceIndex.files).forEach(filePath => {
    if (filePath.includes(query) || filePath.endsWith(query)) {
      results.push({
        type: "file",
        match: query,
        file: filePath,
        ...sourceIndex.files[filePath],
      });
    }
  });

  return results;
}

/**
 * Get implementation of a specific method from source code
 */
export function getMethodImplementation(sourceIndex, className, methodName) {
  const files = sourceIndex.classes[className] || [];
  
  for (const filePath of files) {
    const file = sourceIndex.files[filePath];
    if (!file) continue;

    // Search for method implementation in file
    const methodRegex = new RegExp(
      `(${methodName}\\s*[^{]*\\{[^}]*\\})`,
      "gs"
    );
    const match = file.content.match(methodRegex);
    
    if (match) {
      return {
        file: filePath,
        className: className,
        methodName: methodName,
        implementation: match[0],
        context: getMethodContext(file.content, methodName),
      };
    }
  }

  return null;
}

/**
 * Get surrounding context around a method (includes, class definition, etc.)
 */
function getMethodContext(content, methodName) {
  const lines = content.split("\n");
  const methodLineIndex = lines.findIndex(line => 
    line.includes(methodName) && line.includes("(")
  );

  if (methodLineIndex === -1) return "";

  // Get 20 lines before and 50 lines after
  const start = Math.max(0, methodLineIndex - 20);
  const end = Math.min(lines.length, methodLineIndex + 50);
  
  return lines.slice(start, end).join("\n");
}

/**
 * Get the cache file path for snippets
 */
function getSnippetCacheFile(baseDir) {
  return path.join(baseDir, ".cache", "bytewars-snippets.json");
}

/**
 * Save snippet index to disk
 */
function saveSnippetIndex(baseDir, snippetIndex) {
  try {
    const cacheFile = getSnippetCacheFile(baseDir);
    const cacheDir = path.dirname(cacheFile);
    
    // Ensure cache directory exists
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }
    
    const cacheData = {
      version: "1.0",
      indexedAt: new Date().toISOString(),
      snippetCount: Object.keys(snippetIndex.snippets).length,
      index: snippetIndex,
    };
    
    fs.writeFileSync(cacheFile, JSON.stringify(cacheData, null, 2), "utf8");
    console.error(`Snippet index saved to: ${cacheFile}`);
  } catch (error) {
    console.error(`Failed to save snippet index: ${error.message}`);
  }
}

/**
 * Load snippet index from disk cache
 */
function loadSnippetIndex(baseDir) {
  try {
    const cacheFile = getSnippetCacheFile(baseDir);
    
    if (!fs.existsSync(cacheFile)) {
      return null;
    }
    
    const cacheData = JSON.parse(fs.readFileSync(cacheFile, "utf8"));
    console.error(`Snippet index loaded from cache: ${cacheData.snippetCount} snippets`);
    return cacheData.index;
  } catch (error) {
    console.error(`Failed to load snippet index from cache: ${error.message}`);
    return null;
  }
}

/**
 * Check if cache is still valid by comparing file modification times
 */
function isCacheValid(baseDir) {
  try {
    const cacheFile = getSnippetCacheFile(baseDir);
    const snippetsDir = path.join(baseDir, "data", "bytewars-snippets");
    
    if (!fs.existsSync(cacheFile) || !fs.existsSync(snippetsDir)) {
      return false;
    }
    
    const cacheStats = fs.statSync(cacheFile);
    const cacheTime = cacheStats.mtime.getTime();
    
    // Check if any source file has been modified since cache was created
    function checkDirectory(dir) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory()) {
          if (!checkDirectory(fullPath)) {
            return false;
          }
        } else if (entry.isFile() && (entry.name.endsWith(".h") || entry.name.endsWith(".cpp"))) {
          const fileStats = fs.statSync(fullPath);
          if (fileStats.mtime.getTime() > cacheTime) {
            return false; // Source file is newer than cache
          }
        }
      }
      
      return true;
    }
    
    return checkDirectory(snippetsDir);
  } catch (error) {
    console.error(`Error checking cache validity: ${error.message}`);
    return false;
  }
}

/**
 * Index example components from data/example-components.
 * Example components are full .h/.cpp classes annotated with AB_MCP_BEGIN/END
 * blocks that contain JSON metadata describing their capabilities.
 */
export function indexExampleComponents(baseDir) {
  const componentsDir = path.join(baseDir, "data", "example-components");

  const exampleIndex = {
    components: {}, // id -> metadata + file list
    byService: {},  // service -> [ids]
  };

  if (!fs.existsSync(componentsDir)) {
    console.error(`Example components directory not found: ${componentsDir}`);
    return exampleIndex;
  }

  function ensureComponent(id, meta, relativePath, fullPath) {
    let component = exampleIndex.components[id];

    if (!component) {
      component = {
        id,
        service: meta.service || null,
        provider: meta.provider || null,
        language: meta.language || "unreal-cpp",
        description: meta.description || "",
        controllerClass: meta.controllerClass || null,
        entryStruct: meta.entryStruct || null,
        uiWidgetClass: meta.uiWidgetClass || null,
        rowWidgetClass: meta.rowWidgetClass || null,
        publicInterface: meta.publicInterface || {},
        asyncState: meta.asyncState || {},
        dataModel: meta.dataModel || {},
        // Hint flags and extra metadata for ranking and UX
        dropInReady: meta.dropInReady !== undefined ? !!meta.dropInReady : true,
        recommended: meta.recommended !== undefined ? !!meta.recommended : true,
        integrationHints: Array.isArray(meta.integrationHints)
          ? meta.integrationHints
          : (meta.integrationHints ? [String(meta.integrationHints)] : []),
        files: [],
        filePaths: [],
      };

      exampleIndex.components[id] = component;

      if (component.service) {
        if (!Array.isArray(exampleIndex.byService[component.service])) {
          exampleIndex.byService[component.service] = [];
        }
        if (!exampleIndex.byService[component.service].includes(id)) {
          exampleIndex.byService[component.service].push(id);
        }
      }
    } else {
      // If this block has a more specific description, prefer it
      if (meta.description && !component.description) {
        component.description = meta.description;
      }
    }

    if (relativePath && !component.files.includes(relativePath)) {
      component.files.push(relativePath);
    }
    if (fullPath && !component.filePaths.includes(fullPath)) {
      component.filePaths.push(fullPath);
    }
  }

  function extractExampleComponentsFromFile(filePath, relativePath) {
    const content = fs.readFileSync(filePath, "utf8");
    const lines = content.split("\n");

    let currentId = null;
    let collecting = false;
    let jsonLines = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Look for AB_MCP_BEGIN:Some.Id
      const beginMatch = line.match(/AB_MCP_BEGIN:([^\s]+)/);
      if (beginMatch) {
        // If we were in the middle of one, discard it (malformed)
        currentId = beginMatch[1].trim();
        collecting = true;
        jsonLines = [];
        continue;
      }

      // Look for AB_MCP_END:Same.Id
      const endMatch = line.match(/AB_MCP_END:([^\s]+)/);
      if (endMatch && collecting && currentId && endMatch[1].trim() === currentId) {
        // We have a complete block, try to parse JSON
        const jsonText = jsonLines
          .map((l) => {
            // Strip leading comment markers like // or /// with optional space
            return l.replace(/^\s*\/\/\s?/, "");
          })
          .join("\n")
          .trim();

        if (jsonText) {
          try {
            const meta = JSON.parse(jsonText);
            ensureComponent(currentId, meta, relativePath, filePath);
          } catch (error) {
            console.error(
              `Failed to parse example component metadata for '${currentId}' in ${filePath}: ${error.message}`
            );
          }
        }

        // Reset state
        currentId = null;
        collecting = false;
        jsonLines = [];
        continue;
      }

      // Collect JSON comment lines between BEGIN/END
      if (collecting && currentId) {
        // Only collect comment lines to avoid pulling actual code
        if (line.trim().startsWith("//")) {
          jsonLines.push(line);
        }
      }
    }
  }

  function scanComponentsDirectory(dir, relativePath = "") {
    if (!fs.existsSync(dir)) {
      return;
    }

    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relPath = relativePath ? path.join(relativePath, entry.name) : entry.name;

      if (entry.isDirectory()) {
        scanComponentsDirectory(fullPath, relPath);
      } else if (entry.isFile() && (entry.name.endsWith(".h") || entry.name.endsWith(".cpp"))) {
        extractExampleComponentsFromFile(fullPath, relPath);
      }
    }
  }

  console.error(`Indexing example components from: ${componentsDir}`);
  scanComponentsDirectory(componentsDir, "");

  // Post-processing: ensure paired .h/.cpp files are included
  for (const [id, component] of Object.entries(exampleIndex.components)) {
    const filesSet = new Set(component.files);
    
    for (const file of component.files) {
      const ext = path.extname(file);
      const baseName = path.basename(file, ext);
      const dir = path.dirname(file);
      
      // If we have .h, look for .cpp
      if (ext === '.h') {
        const cppPath = dir ? path.join(dir, `${baseName}.cpp`) : `${baseName}.cpp`;
        const cppFullPath = path.join(componentsDir, cppPath);
        if (fs.existsSync(cppFullPath) && !filesSet.has(cppPath)) {
          component.files.push(cppPath);
          component.filePaths.push(cppFullPath);
          filesSet.add(cppPath);
        }
      }
      // If we have .cpp, look for .h
      else if (ext === '.cpp') {
        const hPath = dir ? path.join(dir, `${baseName}.h`) : `${baseName}.h`;
        const hFullPath = path.join(componentsDir, hPath);
        if (fs.existsSync(hFullPath) && !filesSet.has(hPath)) {
          component.files.push(hPath);
          component.filePaths.push(hFullPath);
          filesSet.add(hPath);
        }
      }
    }
  }

  const componentCount = Object.keys(exampleIndex.components).length;
  console.error(`Example component indexing complete: ${componentCount} components indexed`);

  return exampleIndex;
}

/**
 * Generate snippet cache (force regeneration, ignores existing cache)
 */
export function generateSnippetCache(baseDir) {
  console.error(`Generating snippet cache...`);
  const snippetsDir = path.join(baseDir, "data", "bytewars-snippets");
  
  if (!fs.existsSync(snippetsDir)) {
    console.error(`Snippets directory not found: ${snippetsDir}`);
    return { snippets: {}, byTag: {}, byArea: {} };
  }

  // Build index from source files (skip cache check)
  return buildSnippetIndex(snippetsDir, baseDir);
}

/**
 * Build snippet index from source files (internal function)
 */
function buildSnippetIndex(snippetsDir, baseDir) {

  const snippetIndex = {
    snippets: {},  // snippetId -> snippet data
    byTag: {},     // tag -> [snippetIds]
    byArea: {},    // area -> [snippetIds]
  };

  function scanDirectory(dir, relativePath = "") {
    if (!fs.existsSync(dir)) {
      console.error(`Directory does not exist: ${dir}`);
      return;
    }

    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relPath = relativePath 
        ? path.join(relativePath, entry.name)
        : entry.name;

      if (entry.isDirectory()) {
        scanDirectory(fullPath, relPath);
      } else if (entry.isFile() && (entry.name.endsWith(".h") || entry.name.endsWith(".cpp"))) {
        extractSnippetsFromFile(fullPath, relPath, snippetIndex);
      }
    }
  }

  console.error(`Scanning snippets directory: ${snippetsDir}`);
  scanDirectory(snippetsDir, "");

  const snippetCount = Object.keys(snippetIndex.snippets).length;
  console.error(`Snippet indexing complete: ${snippetCount} snippets indexed`);

  // Save to cache
  saveSnippetIndex(baseDir, snippetIndex);

  return snippetIndex;
}

/**
 * Index code snippets from bytewars-snippets directory
 * Extracts all @@@SNIPSTART to @@@SNIPEND blocks
 * Uses disk cache if available and valid
 */
export function indexSnippets(baseDir, useCache = true, loadOnly = false) {
  console.error(`indexSnippets called with baseDir: ${baseDir}, useCache: ${useCache}, loadOnly: ${loadOnly}`);
  
  const snippetsDir = path.join(baseDir, "data", "bytewars-snippets");
  
  if (!fs.existsSync(snippetsDir)) {
    console.error(`Snippets directory not found: ${snippetsDir}`);
    return { snippets: {}, byTag: {}, byArea: {} };
  }

  // Try to load from cache first
  if (useCache && isCacheValid(baseDir)) {
    const cachedIndex = loadSnippetIndex(baseDir);
    if (cachedIndex) {
      console.error(`Using cached snippet index`);
      return cachedIndex;
    }
  }
  
  // If loadOnly is true, don't generate cache - return empty index
  if (loadOnly) {
    console.error(`Snippet cache not found and loadOnly=true, returning empty index`);
    return { snippets: {}, byTag: {}, byArea: {} };
  }
  
  // Otherwise, generate cache
  if (useCache) {
    console.error(`Cache is invalid or missing, re-indexing snippets...`);
  }

  // Build index from source files
  return buildSnippetIndex(snippetsDir, baseDir);
}

/**
 * Extract all snippets from a single file
 */
function extractSnippetsFromFile(filePath, relativePath, snippetIndex) {
  const fileContent = fs.readFileSync(filePath, "utf8");
  const lines = fileContent.split("\n");
  
  let currentSnippet = null;
  let snippetLines = [];
  let inSnippet = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Check for SNIPSTART
    const snipStartMatch = line.match(/@@@SNIPSTART\s+(.+)/);
    if (snipStartMatch) {
      if (currentSnippet) {
        // Save previous snippet if any
        saveSnippet(currentSnippet, snippetLines.join("\n"), filePath, relativePath, snippetIndex);
      }
      
      const snippetName = snipStartMatch[1].trim();
      currentSnippet = {
        name: snippetName,
        startLine: i + 1,
      };
      snippetLines = [];
      inSnippet = true;
      continue;
    }
    
    // Check for SNIPEND
    if (line.includes("@@@SNIPEND")) {
      if (currentSnippet && inSnippet) {
        currentSnippet.endLine = i + 1;
        saveSnippet(currentSnippet, snippetLines.join("\n"), filePath, relativePath, snippetIndex);
        currentSnippet = null;
        snippetLines = [];
        inSnippet = false;
      }
      continue;
    }
    
    // Collect snippet content
    if (inSnippet && currentSnippet) {
      snippetLines.push(line);
    }
  }
  
  // Handle case where file ends without SNIPEND
  if (currentSnippet && inSnippet) {
    saveSnippet(currentSnippet, snippetLines.join("\n"), filePath, relativePath, snippetIndex);
  }
}

/**
 * Save a snippet to the index with metadata
 */
function saveSnippet(snippetInfo, content, filePath, relativePath, snippetIndex) {
  if (!content.trim()) {
    return; // Skip empty snippets
  }

  // Parse snippet name to extract area and function name
  // Format: "AuthEssentialsSubsystem.cpp-Login" or "AuthEssentialsSubsystem.h-public"
  const nameParts = snippetInfo.name.split("-");
  const filePart = nameParts[0]; // e.g., "AuthEssentialsSubsystem.cpp"
  const functionPart = nameParts.slice(1).join("-"); // e.g., "Login" or "public"
  
  // Extract area from directory structure and file name
  // e.g., "Access/AuthEssentials/AuthEssentialsSubsystem.cpp" -> area: "auth"
  const area = extractAreaFromPath(relativePath, filePart);
  
  // Generate snippet ID and URI (ensure uniqueness)
  let snippetId = generateSnippetId(area, functionPart, filePart);
  let counter = 1;
  const baseId = snippetId;
  
  // Ensure unique ID by appending counter if needed
  while (snippetIndex.snippets[snippetId]) {
    snippetId = `${baseId}-${counter}`;
    counter++;
  }
  
  const uri = `snippet://${snippetId}`;
  
  // Extract metadata
  const metadata = extractSnippetMetadata(content, relativePath, area, functionPart);
  
  const snippet = {
    id: snippetId,
    uri: uri,
    name: snippetInfo.name,
    area: area,
    function: functionPart,
    file: relativePath,
    filePath: filePath,
    content: content,
    startLine: snippetInfo.startLine,
    endLine: snippetInfo.endLine,
    language: "cpp",
    metadata: metadata,
    tags: metadata.tags,
    uses: metadata.uses,
    symbols: metadata.symbols,
  };
  
  snippetIndex.snippets[snippetId] = snippet;
  
  // Index by tags
  metadata.tags.forEach(tag => {
    if (!snippetIndex.byTag[tag]) {
      snippetIndex.byTag[tag] = [];
    }
    if (!snippetIndex.byTag[tag].includes(snippetId)) {
      snippetIndex.byTag[tag].push(snippetId);
    }
  });
  
  // Index by area
  if (!snippetIndex.byArea[area]) {
    snippetIndex.byArea[area] = [];
  }
  if (!snippetIndex.byArea[area].includes(snippetId)) {
    snippetIndex.byArea[area].push(snippetId);
  }
}

/**
 * Extract area/category from file path
 * e.g., "Access/AuthEssentials/AuthEssentialsSubsystem.cpp" -> "auth"
 */
function extractAreaFromPath(relativePath, fileName) {
  // Normalize path separators
  const normalizedPath = relativePath.replace(/\\/g, "/");
  const pathParts = normalizedPath.split("/");
  
  // Map common directory names to areas
  const areaMap = {
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
  };
  
  // Check each path part
  for (const part of pathParts) {
    if (areaMap[part]) {
      return areaMap[part];
    }
  }
  
  // Fallback: extract from file name
  const fileNameLower = fileName.toLowerCase();
  if (fileNameLower.includes("auth")) return "auth";
  if (fileNameLower.includes("login")) return "auth";
  if (fileNameLower.includes("party")) return "party";
  if (fileNameLower.includes("session")) return "session";
  if (fileNameLower.includes("chat")) return "chat";
  if (fileNameLower.includes("friend")) return "friends";
  if (fileNameLower.includes("cloudsave")) return "cloudsave";
  if (fileNameLower.includes("stat")) return "statistics";
  if (fileNameLower.includes("store")) return "store";
  if (fileNameLower.includes("wallet")) return "wallet";
  if (fileNameLower.includes("leaderboard")) return "leaderboard";
  if (fileNameLower.includes("matchmaking")) return "matchmaking";
  if (fileNameLower.includes("presence")) return "presence";
  
  return "general";
}

/**
 * Generate snippet ID for URI
 * Format: oss/{area}/{function-name}
 */
function generateSnippetId(area, functionName, fileName) {
  // Normalize function name
  const normalized = functionName
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  
  // If function name is empty or generic, use file name
  if (!normalized || normalized === "public" || normalized === "private" || normalized === "protected") {
    const fileBase = fileName.replace(/\.(cpp|h)$/, "").toLowerCase();
    return `oss/${area}/${fileBase}`;
  }
  
  return `oss/${area}/${normalized}`;
}

/**
 * Extract metadata from snippet content
 */
function extractSnippetMetadata(content, filePath, area, functionName) {
  const metadata = {
    tags: [],
    uses: [],
    symbols: {
      classes: [],
      methods: [],
      functions: [],
      includes: [],
    },
  };
  
  // Add area-based tags
  metadata.tags.push(area);
  
  // Add function-based tags
  const functionLower = functionName.toLowerCase();
  const contentLower = content.toLowerCase();
  
  if (functionLower.includes("login") || contentLower.includes("login")) {
    metadata.tags.push("login", "authentication");
  }
  if (functionLower.includes("logout") || contentLower.includes("logout")) {
    metadata.tags.push("logout", "authentication");
  }
  if (functionLower.includes("auth") || contentLower.includes("identity")) {
    metadata.tags.push("authentication");
  }
  if (functionLower.includes("party") || contentLower.includes("party")) {
    metadata.tags.push("party", "multiplayer");
  }
  if (functionLower.includes("session") || contentLower.includes("gamesession")) {
    metadata.tags.push("session", "multiplayer");
  }
  if (functionLower.includes("chat") || contentLower.includes("chat")) {
    metadata.tags.push("chat", "messaging");
  }
  if (functionLower.includes("friend") || contentLower.includes("friend")) {
    metadata.tags.push("friends", "social");
  }
  if (functionLower.includes("presence") || contentLower.includes("presence")) {
    metadata.tags.push("presence", "social");
  }
  if (functionLower.includes("cloudsave") || contentLower.includes("cloudsave") || contentLower.includes("playerrecord")) {
    metadata.tags.push("cloudsave", "storage");
  }
  if (functionLower.includes("stat") || contentLower.includes("statistic")) {
    metadata.tags.push("statistics", "storage");
  }
  if (functionLower.includes("store") || contentLower.includes("store") || contentLower.includes("item")) {
    metadata.tags.push("store", "monetization");
  }
  if (functionLower.includes("wallet") || contentLower.includes("wallet")) {
    metadata.tags.push("wallet", "monetization");
  }
  if (functionLower.includes("leaderboard") || contentLower.includes("leaderboard")) {
    metadata.tags.push("leaderboard", "engagement");
  }
  if (functionLower.includes("matchmaking") || contentLower.includes("matchmaking")) {
    metadata.tags.push("matchmaking", "multiplayer");
  }
  if (functionLower.includes("initialize") || functionLower.includes("init")) {
    metadata.tags.push("initialization");
  }
  if (functionLower.includes("deinitialize") || functionLower.includes("deinit")) {
    metadata.tags.push("cleanup");
  }
  if (functionLower.includes("query") || contentLower.includes("query")) {
    metadata.tags.push("query");
  }
  if (functionLower.includes("update") || contentLower.includes("update")) {
    metadata.tags.push("update");
  }
  if (functionLower.includes("get") || functionLower.includes("retrieve")) {
    metadata.tags.push("getter");
  }
  if (functionLower.includes("set") || functionLower.includes("save")) {
    metadata.tags.push("setter");
  }
  if (functionLower.includes("send") || contentLower.includes("send")) {
    metadata.tags.push("send");
  }
  if (functionLower.includes("receive") || contentLower.includes("receive") || contentLower.includes("on")) {
    metadata.tags.push("receive", "callback");
  }
  
  // Extract code symbols
  const codeMetadata = extractCodeMetadata(content, path.basename(filePath));
  metadata.symbols.classes = codeMetadata.classes;
  metadata.symbols.methods = codeMetadata.methods;
  metadata.symbols.includes = codeMetadata.includes;
  metadata.symbols.namespaces = codeMetadata.namespaces;
  
  // Extract function calls (methods being called)
  const functionCallRegex = /([A-Za-z_][A-Za-z0-9_]*)\s*\(/g;
  const seenCalls = new Set();
  let match;
  while ((match = functionCallRegex.exec(content)) !== null) {
    const funcName = match[1];
    if (funcName && 
        !["if", "for", "while", "switch", "return", "ensure", "Cast", "StaticCast"].includes(funcName) &&
        !seenCalls.has(funcName)) {
      metadata.symbols.functions.push(funcName);
      seenCalls.add(funcName);
    }
  }
  
  // Determine uses based on symbols and content
  if (metadata.symbols.includes.some(inc => inc.includes("Identity"))) {
    metadata.uses.push("authentication");
  }
  if (metadata.symbols.includes.some(inc => inc.includes("Session"))) {
    metadata.uses.push("session-management");
  }
  if (metadata.symbols.includes.some(inc => inc.includes("Chat"))) {
    metadata.uses.push("chat");
  }
  if (metadata.symbols.includes.some(inc => inc.includes("Party"))) {
    metadata.uses.push("party");
  }
  if (metadata.symbols.includes.some(inc => inc.includes("CloudSave"))) {
    metadata.uses.push("cloud-save");
  }
  if (metadata.symbols.includes.some(inc => inc.includes("Statistic"))) {
    metadata.uses.push("statistics");
  }
  
  // Remove duplicates
  metadata.tags = [...new Set(metadata.tags)];
  metadata.uses = [...new Set(metadata.uses)];
  
  return metadata;
}

/**
 * Search snippets by various criteria
 */
export function searchSnippets(snippetIndex, options = {}) {
  const {
    query = "",
    area = null,
    tags = [],
    limit = 20,
  } = options;

  if (!snippetIndex || !snippetIndex.snippets) {
    return [];
  }

  const queryLower = query.toLowerCase();
  const results = [];
  const scoredResults = [];

  // Score each snippet based on relevance
  for (const [snippetId, snippet] of Object.entries(snippetIndex.snippets)) {
    let score = 0;
    let matches = false;

    // Filter by area
    if (area && snippet.area !== area) {
      continue;
    }

    // Filter by tags (all specified tags must match)
    if (tags.length > 0) {
      const snippetTags = snippet.tags || [];
      const allTagsMatch = tags.every(tag => 
        snippetTags.some(st => st.toLowerCase() === tag.toLowerCase())
      );
      if (!allTagsMatch) {
        continue;
      }
    }

    // Search in query text
    if (queryLower) {
      // Exact name match (highest score)
      if (snippet.name && snippet.name.toLowerCase().includes(queryLower)) {
        score += 100;
        matches = true;
      }

      // Function name match
      if (snippet.function && snippet.function.toLowerCase().includes(queryLower)) {
        score += 80;
        matches = true;
      }

      // Tag match
      if (snippet.tags) {
        const tagMatches = snippet.tags.filter(tag => 
          tag.toLowerCase().includes(queryLower)
        ).length;
        score += tagMatches * 60;
        if (tagMatches > 0) matches = true;
      }

      // Area match
      if (snippet.area && snippet.area.toLowerCase().includes(queryLower)) {
        score += 50;
        matches = true;
      }

      // Content match (lower score, but still relevant)
      if (snippet.content) {
        const contentLower = snippet.content.toLowerCase();
        if (contentLower.includes(queryLower)) {
          // Count occurrences for better scoring
          const occurrences = (contentLower.match(new RegExp(queryLower.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length;
          score += Math.min(occurrences * 10, 40);
          matches = true;
        }
      }

      // Symbol match (classes, methods, functions)
      if (snippet.symbols) {
        const symbolMatches = [
          ...(snippet.symbols.classes || []),
          ...(snippet.symbols.methods || []),
          ...(snippet.symbols.functions || []),
        ].filter(symbol => 
          symbol.toLowerCase().includes(queryLower)
        ).length;
        score += symbolMatches * 30;
        if (symbolMatches > 0) matches = true;
      }

      // File path match
      if (snippet.file && snippet.file.toLowerCase().includes(queryLower)) {
        score += 20;
        matches = true;
      }

      // Uses match
      if (snippet.uses) {
        const usesMatches = snippet.uses.filter(use => 
          use.toLowerCase().includes(queryLower)
        ).length;
        score += usesMatches * 25;
        if (usesMatches > 0) matches = true;
      }

      // Only include if it matches the query
      if (!matches) {
        continue;
      }
    } else {
      // No query - include all (filtered by area/tags if specified)
      matches = true;
    }

    if (matches) {
      scoredResults.push({
        snippet,
        score,
      });
    }
  }

  // Sort by score (descending) and limit results
  scoredResults.sort((a, b) => b.score - a.score);
  
  return scoredResults
    .slice(0, limit)
    .map(({ snippet }) => ({
      id: snippet.id,
      uri: snippet.uri,
      name: snippet.name,
      area: snippet.area,
      function: snippet.function,
      file: snippet.file,
      tags: snippet.tags,
      uses: snippet.uses,
      description: `${snippet.area}/${snippet.function} - ${snippet.name}`,
      startLine: snippet.startLine,
      endLine: snippet.endLine,
    }));
}
