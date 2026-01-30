/**
 * Download from GitHub and install the AccelByte Unreal SDK plugin into an Unreal project.
 * Supports release ZIP (GitHub API) or git clone; optionally patches .uproject and Build files.
 * Can optionally regenerate IDE project files (.sln / .vcxproj) after setup.
 */
import fs from "fs";
import path from "path";
import os from "os";
import { execSync } from "child_process";
import AdmZip from "adm-zip";

const REGENERATE_TIMEOUT_MS = 120000;

const GITHUB_REPO = "AccelByte/accelbyte-unreal-sdk-plugin";
const GITHUB_REPO_URL = `https://github.com/${GITHUB_REPO}.git`;
const GITHUB_API_BASE = "https://api.github.com/repos";

/**
 * Resolve projectPath to absolute; ensure it exists and contains exactly one .uproject file.
 * @returns {{ projectRoot: string, uprojectPath: string, uprojectName: string }}
 */
function validateProjectPath(projectPath, workspaceRoot) {
  const resolved = path.isAbsolute(projectPath)
    ? path.resolve(projectPath)
    : path.resolve(workspaceRoot || process.cwd(), projectPath);

  if (!fs.existsSync(resolved)) {
    throw new Error(
      `Project path does not exist: ${resolved}. Provide an absolute path or a path relative to the workspace.`
    );
  }

  const stat = fs.statSync(resolved);
  if (!stat.isDirectory()) {
    throw new Error(`Project path is not a directory: ${resolved}`);
  }

  const entries = fs.readdirSync(resolved);
  const uprojectFiles = entries.filter((e) => e.endsWith(".uproject"));
  if (uprojectFiles.length === 0) {
    throw new Error(
      `No .uproject file found in ${resolved}. The path must be the Unreal project root (directory containing the .uproject file).`
    );
  }
  if (uprojectFiles.length > 1) {
    throw new Error(
      `Multiple .uproject files found in ${resolved}. Specify a directory that contains exactly one Unreal project.`
    );
  }

  const uprojectName = uprojectFiles[0];
  const uprojectPath = path.join(resolved, uprojectName);
  return { projectRoot: resolved, uprojectPath, uprojectName };
}

/**
 * Read the plugin module name from the installed plugin's .uplugin file.
 * @param pluginDir - Path to the plugin folder (containing .uplugin)
 * @returns {string} Module name (e.g. "AccelByteUe4Sdk")
 */
function getPluginModuleName(pluginDir) {
  const entries = fs.readdirSync(pluginDir);
  const upluginFile = entries.find((e) => e.endsWith(".uplugin"));
  if (!upluginFile) {
    throw new Error(
      `No .uplugin file found in ${pluginDir}. The installed folder may not be a valid Unreal plugin.`
    );
  }
  const upluginPath = path.join(pluginDir, upluginFile);
  const content = fs.readFileSync(upluginPath, "utf8");
  let json;
  try {
    json = JSON.parse(content);
  } catch (e) {
    throw new Error(`Failed to parse .uplugin file: ${upluginPath}. ${e.message}`);
  }
  const modules = json.Modules;
  if (Array.isArray(modules) && modules.length > 0 && modules[0].Name) {
    return modules[0].Name;
  }
  if (json.FriendlyName) {
    return json.FriendlyName.replace(/\s+/g, "");
  }
  throw new Error(
    `Could not determine plugin module name from ${upluginPath}. Ensure the .uplugin has Modules[0].Name or FriendlyName.`
  );
}

/**
 * Download release ZIP from GitHub (latest or specific tag) and extract to a temp directory.
 * @param version - Optional tag (e.g. "v1.2.0"). Omit for latest.
 * @returns {string} Path to the extracted plugin folder (single top-level folder, or root if single .uplugin at root)
 */
async function downloadReleaseZip(version) {
  const url = version
    ? `${GITHUB_API_BASE}/${GITHUB_REPO}/releases/tags/${encodeURIComponent(version)}`
    : `${GITHUB_API_BASE}/${GITHUB_REPO}/releases/latest`;

  const res = await fetch(url, {
    headers: { Accept: "application/vnd.github+json", "User-Agent": "AccelByte-Unreal-SDK-MCP" },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `GitHub API failed (${res.status}): ${url}. ${text.slice(0, 200)}. Check network and that the release/tag exists.`
    );
  }

  const release = await res.json();
  const assets = release.assets || [];
  const zipAsset = assets.find((a) => (a.name && a.name.toLowerCase().endsWith(".zip")) || false);
  if (!zipAsset || !zipAsset.browser_download_url) {
    throw new Error(
      `No ZIP asset found in release "${release.tag_name || release.name}". Check ${GITHUB_REPO}/releases.`
    );
  }

  const zipRes = await fetch(zipAsset.browser_download_url, {
    headers: { "User-Agent": "AccelByte-Unreal-SDK-MCP" },
  });
  if (!zipRes.ok) {
    throw new Error(
      `Failed to download ZIP (${zipRes.status}): ${zipAsset.browser_download_url}. Check network.`
    );
  }

  const arrayBuffer = await zipRes.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  const tempDir = path.join(os.tmpdir(), `accelbyte-sdk-install-${Date.now()}`);
  fs.mkdirSync(tempDir, { recursive: true });

  const zip = new AdmZip(buffer);
  zip.extractAllTo(tempDir, true);

  const topEntries = fs.readdirSync(tempDir);
  if (topEntries.length === 0) {
    throw new Error("Downloaded ZIP is empty.");
  }

  // If single top-level directory, that's the plugin folder
  if (topEntries.length === 1) {
    const single = path.join(tempDir, topEntries[0]);
    if (fs.statSync(single).isDirectory()) {
      return single;
    }
  }

  // If .uplugin is at root of extracted content, use tempDir as plugin folder
  const hasUpluginAtRoot = topEntries.some((e) => e.endsWith(".uplugin"));
  if (hasUpluginAtRoot) {
    return tempDir;
  }

  // Look for a subfolder that contains .uplugin
  for (const entry of topEntries) {
    const full = path.join(tempDir, entry);
    if (fs.statSync(full).isDirectory()) {
      const subEntries = fs.readdirSync(full);
      if (subEntries.some((e) => e.endsWith(".uplugin"))) {
        return full;
      }
    }
  }

  throw new Error(
    "Downloaded ZIP does not contain a recognizable plugin folder (expected a folder with a .uplugin file)."
  );
}

/**
 * Clone repo via git into a temp directory and return path to plugin folder.
 * @param version - Optional branch or tag. Omit for default branch.
 * @returns {string} Path to the plugin folder (repo root if .uplugin at root, else single subfolder)
 */
function cloneGit(version) {
  try {
    execSync("git --version", { stdio: "pipe" });
  } catch (e) {
    throw new Error(
      "Git is not available. Use source: 'release' to download a ZIP, or install Git."
    );
  }

  const tempDir = path.join(os.tmpdir(), `accelbyte-sdk-git-${Date.now()}`);
  fs.mkdirSync(tempDir, { recursive: true });

  const branchArg = version ? `--branch ${version}` : "";
  const cmd = `git clone --depth 1 ${branchArg} ${GITHUB_REPO_URL} plugin`.replace(/\s+/g, " ").trim();
  try {
    execSync(cmd, { cwd: tempDir, stdio: "pipe", timeout: 120000 });
  } catch (e) {
    throw new Error(
      `Git clone failed: ${e.message}. Check repository URL and branch/tag "${version || "default"}".`
    );
  }

  const pluginPath = path.join(tempDir, "plugin");
  if (!fs.existsSync(pluginPath)) {
    throw new Error("Git clone did not create expected 'plugin' directory.");
  }

  const entries = fs.readdirSync(pluginPath);
  const hasUpluginAtRoot = entries.some((e) => e.endsWith(".uplugin"));
  if (hasUpluginAtRoot) {
    return pluginPath;
  }
  const subdir = entries.find((e) => {
    const full = path.join(pluginPath, e);
    return fs.statSync(full).isDirectory() && fs.readdirSync(full).some((f) => f.endsWith(".uplugin"));
  });
  if (subdir) {
    return path.join(pluginPath, subdir);
  }
  return pluginPath;
}

const PLUGINS_SUBFOLDER = "Accelbyte";

/**
 * Copy plugin folder to project's Plugins/Accelbyte directory. Fails if destination already exists.
 * Uses pluginFolderName (e.g. AccelByteUe4Sdk from .uplugin) as the folder name when provided.
 * @param sourcePluginDir - Extracted or cloned plugin folder
 * @param projectRoot - Unreal project root
 * @param pluginFolderName - Optional. Name of the folder inside Plugins/Accelbyte/ (e.g. plugin module name). If omitted, uses basename of sourcePluginDir.
 * @returns {{ installedPath: string, pluginFolderName: string }}
 */
function installPlugin(sourcePluginDir, projectRoot, pluginFolderName) {
  const folderName = pluginFolderName || path.basename(sourcePluginDir);
  const pluginsDir = path.join(projectRoot, "Plugins", PLUGINS_SUBFOLDER);
  const destPath = path.join(pluginsDir, folderName);

  if (fs.existsSync(destPath)) {
    throw new Error(
      `Plugin already installed at ${destPath}. Remove the existing folder or use a different version.`
    );
  }

  fs.mkdirSync(pluginsDir, { recursive: true });
  copyDirSync(sourcePluginDir, destPath);
  return { installedPath: destPath, pluginFolderName: folderName };
}

function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/**
 * Add plugin to .uproject Plugins array and add module to Build.cs and Target.cs.
 * @param projectRoot - Unreal project root
 * @param uprojectPath - Full path to .uproject file
 * @param moduleName - Plugin module name (e.g. AccelByteUe4Sdk)
 * @returns {string[]} List of changes made
 */
function patchProjectFiles(projectRoot, uprojectPath, moduleName) {
  const changes = [];

  try {
    const uprojectContent = fs.readFileSync(uprojectPath, "utf8");
    const uproject = JSON.parse(uprojectContent);
    if (!Array.isArray(uproject.Plugins)) {
      uproject.Plugins = [];
    }
    const hasPlugin = uproject.Plugins.some(
      (p) => (p.Name || p.name) === moduleName
    );
    if (!hasPlugin) {
      uproject.Plugins.push({ Name: moduleName, Enabled: true });
      fs.writeFileSync(uprojectPath, JSON.stringify(uproject, null, 2), "utf8");
      changes.push(`Added "${moduleName}" to .uproject Plugins array`);
    } else {
      changes.push(`.uproject already contained "${moduleName}"`);
    }
  } catch (e) {
    throw new Error(`Failed to update .uproject: ${e.message}. Add "${moduleName}" to the Plugins array manually.`);
  }

  const sourceDir = path.join(projectRoot, "Source");
  if (!fs.existsSync(sourceDir)) {
    changes.push("No Source/ directory; skip Build.cs and Target.cs (add module manually if needed).");
    return changes;
  }

  const projectName = path.basename(uprojectPath, ".uproject");
  const buildCsPath = path.join(sourceDir, projectName, `${projectName}.Build.cs`);
  if (fs.existsSync(buildCsPath)) {
    const buildContent = fs.readFileSync(buildCsPath, "utf8");
    if (buildContent.includes(`"${moduleName}"`)) {
      changes.push(`Build.cs already contained "${moduleName}"`);
    } else {
      const newContent = buildContent.replace(
        /(PublicDependencyModuleNames\.AddRange\s*\(\s*new\s+string\[\]\s*\{)/,
        (m) => `${m} "${moduleName}",`
      );
      if (newContent !== buildContent) {
        fs.writeFileSync(buildCsPath, newContent, "utf8");
        changes.push(`Added "${moduleName}" to ${projectName}.Build.cs PublicDependencyModuleNames`);
      } else {
        const idx = buildContent.indexOf("PublicDependencyModuleNames.AddRange");
        if (idx !== -1) {
          const end = buildContent.indexOf("});", idx);
          const insertIdx = end !== -1 ? end : buildContent.length;
          const patched =
            buildContent.slice(0, insertIdx) +
            ` "${moduleName}",` +
            buildContent.slice(insertIdx);
          fs.writeFileSync(buildCsPath, patched, "utf8");
          changes.push(`Added "${moduleName}" to ${projectName}.Build.cs PublicDependencyModuleNames`);
        } else {
          changes.push(`Could not patch Build.cs; add PublicDependencyModuleNames.Add("${moduleName}") manually.`);
        }
      }
    }
  } else {
    changes.push(`Build.cs not found at ${buildCsPath}; add PublicDependencyModuleNames.Add("${moduleName}") manually.`);
  }

  // Main project target files: Source/*.Target.cs (e.g. MyGame.Target.cs, MyGameEditor.Target.cs)
  const targetFiles = fs.readdirSync(sourceDir).filter((e) => e.endsWith(".Target.cs"));
  for (const targetFile of targetFiles) {
    const targetPath = path.join(sourceDir, targetFile);
    const targetContent = fs.readFileSync(targetPath, "utf8");
    if (targetContent.includes(`"${moduleName}"`)) {
      changes.push(`${targetFile} already contained "${moduleName}"`);
    } else {
      // Prefer AddRange( new string[] { ... } ) - insert module after opening brace
      const addRangeRegex = /(ExtraModuleNames\s*\.\s*AddRange\s*\(\s*new\s+string\[\]\s*\{)/;
      let patched = targetContent.replace(addRangeRegex, (m) => `${m} "${moduleName}",`);
      if (patched !== targetContent) {
        fs.writeFileSync(targetPath, patched, "utf8");
        changes.push(`Added "${moduleName}" to ${targetFile} ExtraModuleNames`);
      } else {
        // Fallback: add new line ExtraModuleNames.Add("ModuleName"); after last ExtraModuleNames line
        const lastExtra = targetContent.lastIndexOf("ExtraModuleNames");
        if (lastExtra !== -1) {
          const lineEnd = targetContent.indexOf("\n", lastExtra);
          const insertAt = lineEnd !== -1 ? lineEnd + 1 : lastExtra;
          patched =
            targetContent.slice(0, insertAt) +
            `\t\tExtraModuleNames.Add("${moduleName}");\n` +
            targetContent.slice(insertAt);
          fs.writeFileSync(targetPath, patched, "utf8");
          changes.push(`Added "${moduleName}" to ${targetFile} ExtraModuleNames`);
        } else {
          changes.push(`Could not patch ${targetFile}; add ExtraModuleNames.Add("${moduleName}") manually.`);
        }
      }
    }
  }

  writeDefaultAccelByteConfig(projectRoot, moduleName, changes);

  return changes;
}

/**
 * Build the default AccelByte config block for DefaultEngine.ini (blank where necessary, comment examples where useful).
 * @param moduleName - Plugin module name (e.g. AccelByteUe4Sdk)
 * @returns {string}
 */
function getDefaultAccelByteConfigBlock(moduleName) {
  const section = `[/Script/${moduleName}.AccelByteSettings]`;
  return `
${section}
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
`;
}

/**
 * Add default AccelByte config keys to Config/DefaultEngine.ini (blank where necessary, comment examples where possible).
 * Creates Config/DefaultEngine.ini if missing; appends AccelByte section if section not present.
 * @param projectRoot - Unreal project root
 * @param moduleName - Plugin module name (e.g. AccelByteUe4Sdk)
 * @param changes - Array to push change messages to
 */
function writeDefaultAccelByteConfig(projectRoot, moduleName, changes) {
  const configDir = path.join(projectRoot, "Config");
  const configPath = path.join(configDir, "DefaultEngine.ini");
  const section = `[/Script/${moduleName}.AccelByteSettings]`;
  const accelByteBlock = getDefaultAccelByteConfigBlock(moduleName);

  if (!fs.existsSync(configPath)) {
    fs.mkdirSync(configDir, { recursive: true });
    const onlineSubsystem = `[OnlineSubsystem]
; Use AccelByte as the default online platform
DefaultPlatformService=AccelByte
`;
    fs.writeFileSync(configPath, onlineSubsystem.trimEnd() + accelByteBlock, "utf8");
    changes.push("Created Config/DefaultEngine.ini with [OnlineSubsystem] and default AccelByte config keys (blank values; fill in your AGS credentials).");
    return;
  }

  const content = fs.readFileSync(configPath, "utf8");
  if (content.includes(section)) {
    changes.push("Config/DefaultEngine.ini already contained AccelByte config section; skipped adding default keys.");
    return;
  }

  const onlineSubsystemSection = "[OnlineSubsystem]";
  const defaultPlatformLine = "DefaultPlatformService=AccelByte";
  let newContent = content;
  if (content.includes(onlineSubsystemSection) && !content.includes(defaultPlatformLine)) {
    const insertIdx = content.indexOf(onlineSubsystemSection) + onlineSubsystemSection.length;
    newContent = content.slice(0, insertIdx) + "\nDefaultPlatformService=AccelByte" + content.slice(insertIdx);
  } else if (!content.includes(onlineSubsystemSection)) {
    newContent = content.trimEnd() + "\n\n[OnlineSubsystem]\nDefaultPlatformService=AccelByte\n";
  }
  const trimmed = newContent.trimEnd();
  fs.writeFileSync(configPath, trimmed + accelByteBlock, "utf8");
  changes.push("Added default AccelByte config keys to Config/DefaultEngine.ini (blank values; fill in ClientId, Namespace, BaseUrl, etc.).");
}

/**
 * Read EngineAssociation from .uproject (e.g. "5.4", "5.2.1", or GUID).
 * @param uprojectPath - Full path to .uproject file
 * @returns {string|null} Engine version/association or null
 */
function readEngineAssociation(uprojectPath) {
  try {
    const content = fs.readFileSync(uprojectPath, "utf8");
    const json = JSON.parse(content);
    return json.EngineAssociation ?? null;
  } catch (e) {
    return null;
  }
}

/**
 * Normalize EngineAssociation to Epic folder name (e.g. "5.4" or "5.2.1" -> "UE_5.4", "UE_5.2").
 * Returns null if not a version string (e.g. GUID).
 */
function engineAssociationToFolderName(engineAssociation) {
  if (!engineAssociation || typeof engineAssociation !== "string") return null;
  const match = String(engineAssociation).match(/^(\d+)\.(\d+)/);
  if (!match) return null;
  return `UE_${match[1]}.${match[2]}`;
}

/**
 * Resolve path to UnrealVersionSelector (Windows) or GenerateProjectFiles (Mac) using engine from .uproject.
 * Engine version is derived from EngineAssociation; fallback: first UE_* folder under Epic Games.
 * @param engineAssociation - From readEngineAssociation(.uproject), e.g. "5.4"
 * @returns {string|null} Path to UnrealVersionSelector.exe or GenerateProjectFiles.sh, or null
 */
function findUnrealVersionSelector(engineAssociation) {
  const folderName = engineAssociationToFolderName(engineAssociation);
  const platform = os.platform();

  if (platform === "win32") {
    const epicBase = path.join(process.env["ProgramFiles"] || "C:\\Program Files", "Epic Games");
    if (!fs.existsSync(epicBase)) return null;
    const candidates = folderName ? [folderName] : [];
    if (!folderName || !fs.existsSync(path.join(epicBase, folderName))) {
      const dirs = fs.readdirSync(epicBase, { withFileTypes: true })
        .filter((d) => d.isDirectory() && d.name.startsWith("UE_"))
        .map((d) => d.name);
      candidates.push(...dirs);
    }
    for (const name of candidates) {
      const exe = path.join(epicBase, name, "Engine", "Binaries", "UnrealVersionSelector.exe");
      if (fs.existsSync(exe)) return exe;
    }
    return null;
  }

  if (platform === "darwin") {
    const epicBase = "/Users/Shared/Epic Games";
    if (!fs.existsSync(epicBase)) return null;
    const candidates = folderName ? [folderName] : [];
    if (!folderName || !fs.existsSync(path.join(epicBase, folderName))) {
      const dirs = fs.readdirSync(epicBase, { withFileTypes: true })
        .filter((d) => d.isDirectory() && d.name.startsWith("UE_"))
        .map((d) => d.name);
      candidates.push(...dirs);
    }
    for (const name of candidates) {
      const exe = path.join(epicBase, name, "Engine", "Build", "BatchFiles", "Mac", "GenerateProjectFiles.sh");
      if (fs.existsSync(exe)) return exe;
    }
    return null;
  }

  return null;
}

/**
 * Run UnrealVersionSelector (Windows) or GenerateProjectFiles (Mac) to regenerate .sln/.vcxproj.
 * Engine version is read from EngineAssociation in the .uproject file.
 * @param uprojectPath - Full path to .uproject file
 * @returns {{ success: boolean, message: string, stderr?: string }}
 */
function regenerateProjectFiles(uprojectPath) {
  const engineAssociation = readEngineAssociation(uprojectPath);
  const selectorPath = findUnrealVersionSelector(engineAssociation);
  const platform = os.platform();

  if (platform === "win32" && selectorPath && selectorPath.endsWith("UnrealVersionSelector.exe")) {
    try {
      execSync(`"${selectorPath}" /projectfiles "${uprojectPath}"`, {
        stdio: "pipe",
        timeout: REGENERATE_TIMEOUT_MS,
        windowsHide: true,
      });
      return { success: true, message: "Project files regenerated successfully (UnrealVersionSelector)." };
    } catch (e) {
      const stderr = (e.stderr && e.stderr.toString()) || e.message || "";
      return {
        success: false,
        message: `Regenerate project files failed: ${e.message}. Run UnrealVersionSelector /projectfiles manually.`,
        stderr: stderr.slice(0, 500),
      };
    }
  }

  if (platform === "darwin" && selectorPath) {
    try {
      execSync(`"${selectorPath}" -project="${uprojectPath}" -game -engine`, {
        stdio: "pipe",
        timeout: REGENERATE_TIMEOUT_MS,
        cwd: path.dirname(selectorPath),
      });
      return { success: true, message: "Project files regenerated successfully (GenerateProjectFiles)." };
    } catch (e) {
      const stderr = (e.stderr && e.stderr.toString()) || e.message || "";
      return {
        success: false,
        message: `Regenerate project files failed: ${e.message}. Run GenerateProjectFiles.sh from the Engine folder manually.`,
        stderr: stderr.slice(0, 500),
      };
    }
  }

  return {
    success: false,
    message: `UnrealVersionSelector (or GenerateProjectFiles) not found. EngineAssociation in .uproject: ${engineAssociation ?? "(missing)"}. Regenerate project files from the .uproject context menu or from the Engine folder.`,
  };
}

/**
 * Main entry: download (release or git), install, and optionally setup project files.
 * @param params.projectPath - Required. Unreal project root (absolute or relative to workspaceRoot).
 * @param params.workspaceRoot - Optional. Workspace root for resolving relative projectPath.
 * @param params.source - "release" (default) or "git"
 * @param params.version - Optional. For release: tag (e.g. "v1.2.0"). For git: branch or tag.
 * @param params.setupProjectFiles - Optional. If true, patch .uproject and Build/Target files. Default false.
 * @param params.regenerateProjectFiles - Optional. If true, run UnrealVersionSelector/GenerateProjectFiles to regenerate .sln/.vcxproj. Default false.
 * @returns {{ success: boolean, installedPath?: string, message: string, setupDetails?: string[], regenerateResult?: { success: boolean, message: string } }}
 */
export async function installUnrealSdk(params) {
  const {
    projectPath,
    workspaceRoot,
    source = "release",
    version,
    setupProjectFiles = false,
    regenerateProjectFiles: doRegenerate = false,
  } = params || {};

  if (!projectPath || typeof projectPath !== "string") {
    return {
      success: false,
      message: "projectPath is required and must be a string (Unreal project root containing a .uproject file).",
    };
  }

  let projectRoot;
  let uprojectPath;
  try {
    const validated = validateProjectPath(projectPath, workspaceRoot);
    projectRoot = validated.projectRoot;
    uprojectPath = validated.uprojectPath;
  } catch (e) {
    return { success: false, message: e.message };
  }

  let sourcePluginDir;
  try {
    if (source === "git") {
      sourcePluginDir = cloneGit(version);
    } else {
      sourcePluginDir = await downloadReleaseZip(version);
    }
  } catch (e) {
    return { success: false, message: e.message };
  }

  let moduleName;
  try {
    moduleName = getPluginModuleName(sourcePluginDir);
  } catch (e) {
    moduleName = null;
  }

  let installedPath;
  let pluginFolderName;
  try {
    const result = installPlugin(sourcePluginDir, projectRoot, moduleName || undefined);
    installedPath = result.installedPath;
    pluginFolderName = result.pluginFolderName;
  } catch (e) {
    return { success: false, message: e.message };
  }

  if (!moduleName) {
    try {
      moduleName = getPluginModuleName(installedPath);
    } catch (e) {
      return {
        success: true,
        installedPath,
        message: `Plugin copied to ${installedPath}. ${e.message}`,
      };
    }
  }

  let setupDetails;
  if (setupProjectFiles) {
    try {
      setupDetails = patchProjectFiles(projectRoot, uprojectPath, moduleName);
    } catch (e) {
      return {
        success: true,
        installedPath,
        message: `Plugin installed at ${installedPath}. Setup failed: ${e.message}. Add the plugin and module manually (see AccelByte Unreal SDK install docs).`,
        setupDetails: [],
      };
    }
  }

  let regenerateResult;
  if (doRegenerate) {
    regenerateResult = regenerateProjectFiles(uprojectPath);
    if (setupDetails && regenerateResult.success) {
      setupDetails.push(regenerateResult.message);
    }
  }

  const nextSteps =
    "Configure DefaultEngine.ini with your AGS credentials (see https://docs.accelbyte.io/gaming-services/getting-started/setup-game-sdk/unreal-sdk).";
  let message = setupProjectFiles
    ? `Installed ${pluginFolderName} to ${installedPath} and updated project files. ${nextSteps}`
    : `Installed ${pluginFolderName} to ${installedPath}. Add the plugin to .uproject and Build.cs/Target.cs, then ${nextSteps}`;
  if (doRegenerate && regenerateResult) {
    message += ` ${regenerateResult.success ? "Project files regenerated." : ` Regenerate: ${regenerateResult.message}`}`;
  }

  return {
    success: true,
    installedPath,
    message,
    setupDetails: setupDetails || undefined,
    regenerateResult: regenerateResult || undefined,
  };
}
