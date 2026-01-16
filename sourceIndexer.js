import fs from "fs";
import path from "path";
import { execSync } from "child_process";

const GITHUB_REPO_URL = "https://github.com/AccelByte/accelbyte-unreal-sdk-plugin.git";
const REPO_NAME = "accelbyte-unreal-sdk-plugin";

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
      
      execSync(`git clone --depth 1 ${repoUrl} "${repoPath}"`, {
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
        execSync("git fetch origin main", { cwd: repoPath, stdio: 'pipe', timeout: 30000 });
        execSync("git reset --hard origin/main", { cwd: repoPath, stdio: 'pipe' });
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
  const sourceDir = path.join(repoPath, "Source", "AccelByteUe4Sdk");
  if (!fs.existsSync(sourceDir)) {
    throw new Error(`Repository structure is incorrect. Expected Source/AccelByteUe4Sdk directory not found at: ${sourceDir}`);
  }
  
  return repoPath;
}

/**
 * Indexes C++ source files from the SDK repository
 * Clones from GitHub if not present, or updates existing clone
 */
export function indexSourceFiles(baseDir) {
  console.error(`indexSourceFiles called with baseDir: ${baseDir}`);
  
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

  const sourceIndex = {
    files: {},
    methods: {},  // Method name -> [file paths where it's implemented]
    classes: {},  // Class name -> file paths
  };

  // Directories to scan for source files
  const publicDir = path.join(repoRoot, "Source", "AccelByteUe4Sdk", "Public");
  const privateDir = path.join(repoRoot, "Source", "AccelByteUe4Sdk", "Private");
  
  console.error(`Looking for source directories:`);
  console.error(`  Public: ${publicDir} (exists: ${fs.existsSync(publicDir)})`);
  console.error(`  Private: ${privateDir} (exists: ${fs.existsSync(privateDir)})`);

  function scanDirectory(dir, relativePath = "") {
    if (!fs.existsSync(dir)) {
      console.error(`Directory does not exist: ${dir}`);
      return;
    }

    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      // Build relative path from Source/AccelByteUe4Sdk
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

  // Scan Public directory (headers)
  if (fs.existsSync(publicDir)) {
    console.error(`Scanning Public directory: ${publicDir}`);
    scanDirectory(publicDir, "Public");
  } else {
    const errorMsg = `Public directory not found: ${publicDir}. Repository may not be cloned correctly.`;
    console.error(`ERROR: ${errorMsg}`);
    throw new Error(errorMsg);
  }

  // Scan Private directory (implementations)
  if (fs.existsSync(privateDir)) {
    console.error(`Scanning Private directory: ${privateDir}`);
    scanDirectory(privateDir, "Private");
  } else {
    const errorMsg = `Private directory not found: ${privateDir}. Repository may not be cloned correctly.`;
    console.error(`ERROR: ${errorMsg}`);
    throw new Error(errorMsg);
  }

  if (Object.keys(sourceIndex.files).length === 0) {
    throw new Error(`No source files were indexed. Check that the repository structure is correct.`);
  }

  return sourceIndex;
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
