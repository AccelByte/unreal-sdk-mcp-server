"""
XML symbol parser for AccelByte Unreal SDK documentation.
Converts Doxygen-generated XML files into a searchable symbol cache.
Python translation of parser.js.
"""

import json
import sys
import defusedxml.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent


def _get_symbols_cache_file(base_dir: Path, sdk_name: str) -> Path:
    cache_dir = base_dir / ".cache"
    return cache_dir / f"{sdk_name}-symbols.json"


def save_symbols_cache(base_dir: Path, sdk_name: str, symbols: dict) -> None:
    try:
        cache_file = _get_symbols_cache_file(base_dir, sdk_name)
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "version": "1.0",
            "indexedAt": datetime.now(timezone.utc).isoformat(),
            "symbolCount": len(symbols),
            "symbols": symbols,
        }

        cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        print(f"Symbols cache saved to: {cache_file}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to save symbols cache: {e}", file=sys.stderr)


def load_symbols_cache(base_dir: Path, sdk_name: str) -> dict | None:
    try:
        cache_file = _get_symbols_cache_file(base_dir, sdk_name)

        if not cache_file.exists():
            return None

        cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        print(
            f"Symbols cache loaded from: {cache_file} ({cache_data.get('symbolCount', 0)} symbols)",
            file=sys.stderr,
        )
        return cache_data.get("symbols")
    except Exception as e:
        print(f"Failed to load symbols cache: {e}", file=sys.stderr)
        return None


def is_symbols_cache_valid(base_dir: Path, sdk_name: str, xml_dir: Path) -> bool:
    try:
        cache_file = _get_symbols_cache_file(base_dir, sdk_name)

        if not cache_file.exists() or not xml_dir.exists():
            return False

        cache_time = cache_file.stat().st_mtime

        for xml_file in xml_dir.rglob("*.xml"):
            if xml_file.stat().st_mtime > cache_time:
                return False  # XML file is newer than cache

        return True
    except Exception as e:
        print(f"Error checking symbols cache validity: {e}", file=sys.stderr)
        return False


def generate_symbols_cache(xml_dir: Path, sdk_name: str, base_dir: Path) -> dict:
    """Generate symbols cache (force regeneration, ignores existing cache)."""
    print(f"Generating symbols cache for {sdk_name}...", file=sys.stderr)
    symbols = _parse_symbols_from_xml(xml_dir)
    if base_dir and sdk_name:
        save_symbols_cache(base_dir, sdk_name, symbols)
    return symbols


def _extract_description_text(desc_elem) -> str:
    """Extract plain text from a Doxygen description element (briefdescription / detaileddescription)."""
    if desc_elem is None:
        return ""
    # xml.etree.ElementTree itertext() recursively collects all text nodes
    return " ".join(desc_elem.itertext()).strip()


def _extract_type(type_elem) -> str:
    """Extract a type string from a <type> element (may contain <ref> subelements)."""
    if type_elem is None:
        return ""
    return "".join(type_elem.itertext()).strip()


def _parse_symbols_from_xml(xml_dir: Path) -> dict:
    """Parse all Doxygen XML files in xml_dir and return a flat symbol dict."""
    symbols: dict = {}

    PREFIX = "D:/dev/mcp/"

    for xml_file in xml_dir.rglob("*.xml"):
        try:
            tree = ET.parse(xml_file)
        except ET.ParseError:
            continue

        root = tree.getroot()
        c = root.find("compounddef")
        if c is None:
            continue

        name: str = c.findtext("compoundname", "")
        if name.startswith(PREFIX):
            name = name[len(PREFIX):].replace("\\", "/")

        kind = c.get("kind", "")
        symbol_id = f"{name}@cpp"

        brief_desc = _extract_description_text(c.find("briefdescription"))
        detailed_desc = _extract_description_text(c.find("detaileddescription"))

        symbol: dict = {
            "id": symbol_id,
            "name": name,
            "type": kind,
            "description": brief_desc or detailed_desc or "",
            "fields": {},
            "methods": {},
        }

        for section in c.findall("sectiondef"):
            for m in section.findall("memberdef"):
                m_kind = m.get("kind", "")

                if m_kind == "variable":
                    field_brief = _extract_description_text(m.find("briefdescription"))
                    field_detailed = _extract_description_text(m.find("detaileddescription"))
                    field_name = m.findtext("name", "")
                    if field_name:
                        symbol["fields"][field_name] = {
                            "type": _extract_type(m.find("type")),
                            "required": True,
                            "description": field_brief or field_detailed or "",
                        }

                elif m_kind == "function":
                    params = m.findall("param")
                    param_types = [
                        _extract_type(p.find("type"))
                        for p in params
                        if p.find("type") is not None
                    ]
                    param_types = [t for t in param_types if t]
                    func_name = m.findtext("name", "")
                    sig = f"{func_name}({','.join(param_types)})"

                    method_brief = _extract_description_text(m.find("briefdescription"))
                    method_detailed = _extract_description_text(m.find("detaileddescription"))

                    symbol["methods"][sig] = {
                        "returnType": _extract_type(m.find("type")),
                        "params": [
                            {
                                "name": p.findtext("declname") or p.findtext("defname") or "",
                                "type": _extract_type(p.find("type")),
                            }
                            for p in params
                        ],
                        "const": m.get("const") == "yes",
                        "description": method_brief or method_detailed or "",
                    }

        symbols[symbol_id] = symbol

    return symbols


def load_symbols(
    xml_dir: Path,
    sdk_name: str,
    base_dir: Path,
    use_cache: bool = True,
    load_only: bool = False,
) -> dict:
    # Try to load from cache first
    if use_cache and base_dir and sdk_name and is_symbols_cache_valid(base_dir, sdk_name, xml_dir):
        cached = load_symbols_cache(base_dir, sdk_name)
        if cached:
            print(f"Using cached symbols for {sdk_name}", file=sys.stderr)
            return cached

    # If loadOnly is true, don't generate — return empty
    if load_only:
        print(
            f"Cache not found for {sdk_name} and load_only=True, returning empty symbols",
            file=sys.stderr,
        )
        return {}

    # Otherwise parse from XML and cache
    if use_cache and base_dir and sdk_name:
        print(f"Cache is invalid or missing for {sdk_name}, parsing XML files...", file=sys.stderr)

    symbols = _parse_symbols_from_xml(xml_dir)

    if base_dir and sdk_name:
        save_symbols_cache(base_dir, sdk_name, symbols)

    return symbols
