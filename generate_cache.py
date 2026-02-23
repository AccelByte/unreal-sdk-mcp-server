#!/usr/bin/env python3
"""
Cache generation entry point.
Generates symbol, source index, and snippet caches.
Python translation of generateCache.js.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
SOURCES_DIR = BASE_DIR / "data"
UNREAL_SDK_XML_DIR = SOURCES_DIR / "unreal-sdk"
OSS_SDK_DIR = SOURCES_DIR / "oss-sdk"
CACHE_DIR = BASE_DIR.parent / ".cache"


def main() -> None:
    from parser import generate_symbols_cache
    from source_indexer import generate_source_index_cache, generate_snippet_cache

    print("=== Generating Cache Files ===", file=sys.stderr)
    print(f"Base directory: {BASE_DIR}", file=sys.stderr)
    print("", file=sys.stderr)

    # 1. Generate symbols cache
    print("1. Generating symbols cache...", file=sys.stderr)
    try:
        print("   - unreal-sdk symbols...", file=sys.stderr)
        unreal_symbols = generate_symbols_cache(UNREAL_SDK_XML_DIR, "unreal-sdk", BASE_DIR)
        print(f"   + Generated {len(unreal_symbols)} unreal-sdk symbols", file=sys.stderr)

        print("   - oss-sdk symbols...", file=sys.stderr)
        oss_symbols = generate_symbols_cache(OSS_SDK_DIR, "oss-sdk", BASE_DIR)
        print(f"   + Generated {len(oss_symbols)} oss-sdk symbols", file=sys.stderr)
    except Exception as e:
        print(f"   x Error generating symbols cache: {e}", file=sys.stderr)
        sys.exit(1)

    print("", file=sys.stderr)

    # 2. Generate source index cache
    print("2. Generating source index cache...", file=sys.stderr)
    try:
        source_index = generate_source_index_cache(CACHE_DIR)
        file_count = len(source_index.get("files", {}))
        class_count = len(source_index.get("classes", {}))
        method_count = len(source_index.get("methods", {}))
        print(
            f"   + Generated source index: {file_count} files, "
            f"{class_count} classes, {method_count} methods",
            file=sys.stderr,
        )
    except Exception as e:
        import traceback
        print(f"   x Error generating source index cache: {e}", file=sys.stderr)
        print(f"   Stack trace: {traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)

    print("", file=sys.stderr)

    # 3. Generate snippet index cache
    print("3. Generating snippet index cache...", file=sys.stderr)
    try:
        snippet_index = generate_snippet_cache(BASE_DIR)
        snippet_count = len(snippet_index.get("snippets", {}))
        print(f"   + Generated snippet index: {snippet_count} snippets", file=sys.stderr)
    except Exception as e:
        import traceback
        print(f"   x Error generating snippet index cache: {e}", file=sys.stderr)
        print(f"   Stack trace: {traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)

    print("", file=sys.stderr)
    print("=== Cache Generation Complete ===", file=sys.stderr)


if __name__ == "__main__":
    main()
