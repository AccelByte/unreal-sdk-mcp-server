"""
One-shot migration: rename state-widget suffixes in all recipe specs.

  *_IdleStatus  -> *_IdleState
  *_SuccessBlock -> *_SuccessState

The other three suffixes (_LoadingState, _EmptyState, _ErrorState) already match
the *_State convention; left untouched.

Scope: `Tools/specs/recipes/*.json` ONLY. Does not touch component specs.
Idempotent: re-running on already-renamed specs is a no-op.
"""

import json
from pathlib import Path

RECIPE_DIR = Path(__file__).parent / "data/AccelByteUITools/Tools/specs/recipes"

RENAMES = [
    ("_IdleStatus", "_IdleState"),
    ("_SuccessBlock", "_SuccessState"),
]


def rename_widget_names(node: dict) -> int:
    """Recursively rename widget names matching the suffix table. Returns count."""
    count = 0
    name = node.get("name", "")
    for old_suffix, new_suffix in RENAMES:
        if name.endswith(old_suffix):
            node["name"] = name[: -len(old_suffix)] + new_suffix
            count += 1
            break
    for child in node.get("children", []):
        count += rename_widget_names(child)
    return count


def process(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    count = rename_widget_names(data.get("root", {}))
    if count > 0:
        path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return count


def main():
    total = 0
    for path in sorted(RECIPE_DIR.glob("*.json")):
        renamed = process(path)
        if renamed:
            print(f"  {path.name}: renamed {renamed} widget(s)")
            total += renamed
        else:
            print(f"  {path.name}: no changes")
    print(f"\nDone: renamed {total} widget(s) across recipes.")


if __name__ == "__main__":
    main()
