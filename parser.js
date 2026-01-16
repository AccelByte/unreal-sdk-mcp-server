import fs from "fs";
import path from "path";
import { XMLParser } from "fast-xml-parser";

const parser = new XMLParser({ ignoreAttributes: false });

export function loadSymbols(xmlDir) {
  const symbols = {};

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

        const c = data?.doxygen?.compounddef;
        if (!c) continue;

        const name = c.compoundname;
        const kind = c["@_kind"];

        const id = `${name}@cpp`;

        const symbol = {
          id,
          name,
          type: kind,
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
              symbol.fields[m.name] = {
                type: extractType(m.type),
                required: true
              };
            }

            if (m["@_kind"] === "function") {
              // Ensure param is always an array (can be single object or array)
              const params = m.param || [];
              const paramList = Array.isArray(params) ? params : params ? [params] : [];
              
              const paramTypes = paramList.map(p => extractType(p?.type)).filter(t => t);
              const sig = m.name + "(" + paramTypes.join(",") + ")";

              symbol.methods[sig] = {
                returnType: extractType(m.type),
                params: paramList.map(p => ({
                  name: p?.declname || p?.defname || "",
                  type: extractType(p?.type)
                })),
                const: m["@_const"] === "yes"
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
