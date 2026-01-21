import fs from "fs";
import path from "path";
import { XMLParser } from "fast-xml-parser";

const parser = new XMLParser({ ignoreAttributes: false });

/**
 * Get the cache file path for symbols
 */
function getSymbolsCacheFile(baseDir, sdkName) {
  const cacheDir = path.join(baseDir, ".cache");
  return path.join(cacheDir, `${sdkName}-symbols.json`);
}

/**
 * Save symbols to disk cache
 */
function saveSymbolsCache(baseDir, sdkName, symbols) {
  try {
    const cacheFile = getSymbolsCacheFile(baseDir, sdkName);
    const cacheDir = path.dirname(cacheFile);
    
    // Ensure cache directory exists
    if (!fs.existsSync(cacheDir)) {
      fs.mkdirSync(cacheDir, { recursive: true });
    }
    
    const cacheData = {
      version: "1.0",
      indexedAt: new Date().toISOString(),
      symbolCount: Object.keys(symbols).length,
      symbols: symbols,
    };
    
    fs.writeFileSync(cacheFile, JSON.stringify(cacheData, null, 2), "utf8");
    console.error(`Symbols cache saved to: ${cacheFile}`);
  } catch (error) {
    console.error(`Failed to save symbols cache: ${error.message}`);
  }
}

/**
 * Load symbols from disk cache
 */
function loadSymbolsCache(baseDir, sdkName) {
  try {
    const cacheFile = getSymbolsCacheFile(baseDir, sdkName);
    
    if (!fs.existsSync(cacheFile)) {
      return null;
    }
    
    const cacheData = JSON.parse(fs.readFileSync(cacheFile, "utf8"));
    console.error(`Symbols cache loaded from: ${cacheFile} (${cacheData.symbolCount} symbols)`);
    return cacheData.symbols;
  } catch (error) {
    console.error(`Failed to load symbols cache: ${error.message}`);
    return null;
  }
}

/**
 * Check if cache is still valid by comparing file modification times
 */
function isSymbolsCacheValid(baseDir, sdkName, xmlDir) {
  try {
    const cacheFile = getSymbolsCacheFile(baseDir, sdkName);
    
    if (!fs.existsSync(cacheFile) || !fs.existsSync(xmlDir)) {
      return false;
    }
    
    const cacheStats = fs.statSync(cacheFile);
    const cacheTime = cacheStats.mtime.getTime();
    
    // Check if any XML file has been modified since cache was created
    function checkDirectory(dir) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory()) {
          if (!checkDirectory(fullPath)) {
            return false;
          }
        } else if (entry.isFile() && entry.name.endsWith(".xml")) {
          const fileStats = fs.statSync(fullPath);
          if (fileStats.mtime.getTime() > cacheTime) {
            return false; // XML file is newer than cache
          }
        }
      }
      
      return true;
    }
    
    return checkDirectory(xmlDir);
  } catch (error) {
    console.error(`Error checking symbols cache validity: ${error.message}`);
    return false;
  }
}

/**
 * Generate symbols cache (force regeneration, ignores existing cache)
 */
export function generateSymbolsCache(xmlDir, sdkName, baseDir) {
  console.error(`Generating symbols cache for ${sdkName}...`);
  const symbols = parseSymbolsFromXml(xmlDir);
  if (baseDir && sdkName) {
    saveSymbolsCache(baseDir, sdkName, symbols);
  }
  return symbols;
}

/**
 * Parse symbols from XML files (internal function)
 */
function parseSymbolsFromXml(xmlDir) {

  const symbols = {};

  // Helper function to extract text from description nodes (briefdescription, detaileddescription)
  function extractDescriptionText(descObj) {
    if (!descObj) return "";
    if (typeof descObj === "string") return descObj.trim();
    
    let text = "";
    
    // Handle para tags
    if (descObj.para) {
      const paras = Array.isArray(descObj.para) ? descObj.para : [descObj.para];
      for (const para of paras) {
        if (typeof para === "string") {
          text += para + " ";
        } else if (para["#text"]) {
          text += para["#text"] + " ";
        } else if (Array.isArray(para)) {
          // Handle nested structures
          for (const item of para) {
            if (typeof item === "string") {
              text += item + " ";
            } else if (item["#text"]) {
              text += item["#text"] + " ";
            }
          }
        }
      }
    }
    
    // Handle direct text content
    if (descObj["#text"]) {
      text += descObj["#text"] + " ";
    }
    
    // Handle parameterlist (extract parameter descriptions)
    if (descObj.parameterlist) {
      const paramLists = Array.isArray(descObj.parameterlist) ? descObj.parameterlist : [descObj.parameterlist];
      for (const paramList of paramLists) {
        if (paramList.parameteritem) {
          const items = Array.isArray(paramList.parameteritem) ? paramList.parameteritem : [paramList.parameteritem];
          for (const item of items) {
            if (item.parameterdescription?.para) {
              const paras = Array.isArray(item.parameterdescription.para) 
                ? item.parameterdescription.para 
                : [item.parameterdescription.para];
              for (const para of paras) {
                if (typeof para === "string") {
                  text += para + " ";
                } else if (para["#text"]) {
                  text += para["#text"] + " ";
                }
              }
            }
          }
        }
      }
    }
    
    // Handle simplesect (like return values)
    if (descObj.simplesect) {
      const simplesects = Array.isArray(descObj.simplesect) ? descObj.simplesect : [descObj.simplesect];
      for (const sect of simplesects) {
        if (sect.para) {
          const paras = Array.isArray(sect.para) ? sect.para : [sect.para];
          for (const para of paras) {
            if (typeof para === "string") {
              text += para + " ";
            } else if (para["#text"]) {
              text += para["#text"] + " ";
            }
          }
        }
      }
    }
    
    return text.trim();
  }

  // Helper function to extract type string from type object
  function extractType(typeObj) {
    if (!typeObj) return "";
    if (typeof typeObj === "string") return typeObj;
    // Handle complex type objects with ref and #text
    let typeStr = "";
    if (typeObj.ref) {
      typeStr += typeObj.ref["#text"] || "";
    }
    if (typeObj["#text"]) {
      typeStr += (typeStr ? " " : "") + typeObj["#text"];
    }
    return typeStr.trim() || "";
  }

  // Recursively scan for all XML files in the directory and subdirectories
  function scanDirectory(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        // Recursively scan subdirectories
        scanDirectory(fullPath);
      } else if (entry.isFile() && entry.name.endsWith(".xml")) {
        // Process XML files
        const xml = fs.readFileSync(fullPath, "utf8");
        const data = parser.parse(xml);

        let c = data?.doxygen?.compounddef;
        if (!c) continue;

        const prefix = "D:/dev/mcp/";

        let name = c.compoundname;

        if (name.startsWith(prefix)) {
          name = name.slice(prefix.length).replace(/\\/g, "/");
        }

        
        const kind = c["@_kind"];

        const id = `${name}@cpp`;

        // Extract descriptions from compounddef - prefer brief, fallback to detailed
        const briefDescription = extractDescriptionText(c.briefdescription);
        const detailedDescription = extractDescriptionText(c.detaileddescription);
        
        const symbol = {
          id,
          name,
          type: kind,
          description: briefDescription || detailedDescription || "",
          fields: {},
          methods: {}
        };

        // sectiondef is an array, each containing memberdef array
        const sectiondefs = c.sectiondef || [];
        const sectiondefList = Array.isArray(sectiondefs) ? sectiondefs : [sectiondefs];

        // Iterate through all sectiondefs to collect all members
        for (const section of sectiondefList) {
          if (!section.memberdef) continue;
          
          const members = section.memberdef;
          const memberList = Array.isArray(members) ? members : [members];

          for (const m of memberList) {
            if (!m || !m["@_kind"]) continue;

            if (m["@_kind"] === "variable") {
              const fieldBriefDesc = extractDescriptionText(m.briefdescription);
              const fieldDetailedDesc = extractDescriptionText(m.detaileddescription);
              
              symbol.fields[m.name] = {
                type: extractType(m.type),
                required: true,
                description: fieldBriefDesc || fieldDetailedDesc || "",
              };
            }

            if (m["@_kind"] === "function") {
              // Ensure param is always an array (can be single object or array)
              const params = m.param || [];
              const paramList = Array.isArray(params) ? params : params ? [params] : [];
              
              const paramTypes = paramList.map(p => extractType(p?.type)).filter(t => t);
              const sig = m.name + "(" + paramTypes.join(",") + ")";

              const methodBriefDesc = extractDescriptionText(m.briefdescription);
              const methodDetailedDesc = extractDescriptionText(m.detaileddescription);

              symbol.methods[sig] = {
                returnType: extractType(m.type),
                params: paramList.map(p => ({
                  name: p?.declname || p?.defname || "",
                  type: extractType(p?.type)
                })),
                const: m["@_const"] === "yes",
                description: methodBriefDesc || methodDetailedDesc || "",
              };
            }
          }
        }

        symbols[id] = symbol;
      }
    }
  }

  // Start recursive scan from the root directory
  scanDirectory(xmlDir);

  return symbols;
}

export function loadSymbols(xmlDir, sdkName, baseDir, useCache = true, loadOnly = false) {
  // Try to load from cache first
  if (useCache && baseDir && sdkName && isSymbolsCacheValid(baseDir, sdkName, xmlDir)) {
    const cachedSymbols = loadSymbolsCache(baseDir, sdkName);
    if (cachedSymbols) {
      console.error(`Using cached symbols for ${sdkName}`);
      return cachedSymbols;
    }
  }
  
  // If loadOnly is true, don't generate cache - just return empty object
  if (loadOnly) {
    console.error(`Cache not found for ${sdkName} and loadOnly=true, returning empty symbols`);
    return {};
  }
  
  // Otherwise, parse from XML and generate cache
  if (useCache && baseDir && sdkName) {
    console.error(`Cache is invalid or missing for ${sdkName}, parsing XML files...`);
  }

  // Parse from XML
  const symbols = parseSymbolsFromXml(xmlDir);

  // Save to cache if baseDir and sdkName are provided
  if (baseDir && sdkName) {
    saveSymbolsCache(baseDir, sdkName, symbols);
  }

  return symbols;
}
