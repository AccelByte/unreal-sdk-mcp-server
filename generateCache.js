import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { generateSymbolsCache } from "./parser.js";
import { generateSourceIndexCache, generateSnippetCache } from "./sourceIndexer.js";

// Get the directory of this script file
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourcesDir = join(__dirname, "source");
const unrealSDKXmlDir = join(sourcesDir, "unreal-sdk");
const ossSDKDir = join(sourcesDir, "oss-sdk");

console.error("=== Generating Cache Files ===");
console.error(`Base directory: ${__dirname}`);
console.error("");

// Generate symbols cache
console.error("1. Generating symbols cache...");
try {
  console.error("   - unreal-sdk symbols...");
  const unrealSymbols = generateSymbolsCache(unrealSDKXmlDir, "unreal-sdk", __dirname);
  console.error(`   ✓ Generated ${Object.keys(unrealSymbols).length} unreal-sdk symbols`);
  
  console.error("   - oss-sdk symbols...");
  const ossSymbols = generateSymbolsCache(ossSDKDir, "oss-sdk", __dirname);
  console.error(`   ✓ Generated ${Object.keys(ossSymbols).length} oss-sdk symbols`);
} catch (error) {
  console.error(`   ✗ Error generating symbols cache: ${error.message}`);
  process.exit(1);
}

console.error("");

// Generate source index cache
console.error("2. Generating source index cache...");
try {
  const cacheDir = join(__dirname, "..", ".cache");
  const sourceIndex = generateSourceIndexCache(cacheDir);
  const fileCount = Object.keys(sourceIndex.files).length;
  const classCount = Object.keys(sourceIndex.classes).length;
  const methodCount = Object.keys(sourceIndex.methods).length;
  console.error(`   ✓ Generated source index: ${fileCount} files, ${classCount} classes, ${methodCount} methods`);
} catch (error) {
  console.error(`   ✗ Error generating source index cache: ${error.message}`);
  console.error(`   Stack trace: ${error.stack}`);
  process.exit(1);
}

console.error("");

// Generate snippet index cache
console.error("3. Generating snippet index cache...");
try {
  const snippetIndex = generateSnippetCache(__dirname);
  const snippetCount = Object.keys(snippetIndex.snippets).length;
  console.error(`   ✓ Generated snippet index: ${snippetCount} snippets`);
} catch (error) {
  console.error(`   ✗ Error generating snippet index cache: ${error.message}`);
  console.error(`   Stack trace: ${error.stack}`);
  process.exit(1);
}

console.error("");
console.error("=== Cache Generation Complete ===");
