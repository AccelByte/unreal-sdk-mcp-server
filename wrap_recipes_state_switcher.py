"""
Wrap the five state widgets (Idle / Loading / Success / Empty / Error) of every
recipe panel inside a single `WidgetSwitcher` named `StateSwitcher` so only the
active state renders at a time.

The UAGSStateWidgetBase state machine, after the matching C++ change, binds
`StateSwitcher` via BindWidgetOptional and calls SetActiveWidgetIndex with the
EAGSUIState enum value (Idle=0, Loading=1, Success=2, Empty=3, Error=4).

This script is idempotent: if a `StateSwitcher` already exists in the recipe,
it skips that file.

Skips recipes whose root isn't a CanvasPanel (only `ags_user_profile_panel.json`
qualifies currently and it has no state widgets).
"""

import json
from pathlib import Path

RECIPE_DIR = Path(__file__).parent / "data/AccelByteUITools/Tools/specs/recipes"

# Map name-suffix → enum index. Order matches EAGSUIState.
STATE_SUFFIX_TO_INDEX = {
    "_IdleState": 0,
    "_LoadingState": 1,
    "_SuccessState": 2,
    "_EmptyState": 3,
    "_ErrorState": 4,
}

FULL_STRETCH_SLOT = {
    "anchors": [0, 0, 1, 1],
    "offsets": [0, 0, 0, 0],
    "alignment": [0, 0],
}


def find_state_index(name: str) -> int | None:
    for suffix, index in STATE_SUFFIX_TO_INDEX.items():
        if name.endswith(suffix):
            return index
    return None


def already_has_state_switcher(children: list) -> bool:
    return any(c.get("name") == "StateSwitcher" for c in children)


def wrap_recipe(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    root = data["root"]

    if root.get("type") != "CanvasPanel":
        return "skipped (non-CanvasPanel root)"

    children = root.get("children", [])
    if already_has_state_switcher(children):
        return "skipped (already has StateSwitcher)"

    # Partition children: state widgets vs everything else
    state_by_index: dict[int, dict] = {}
    other_children = []
    for child in children:
        idx = find_state_index(child.get("name", ""))
        if idx is not None and idx not in state_by_index:
            state_by_index[idx] = child
        else:
            other_children.append(child)

    if not state_by_index:
        return "skipped (no state widgets found)"

    # Strip per-child anchor slots — the switcher controls layout now
    ordered_state_children = []
    for index in sorted(state_by_index.keys()):
        child = state_by_index[index]
        child.pop("slot", None)
        ordered_state_children.append(child)

    state_switcher = {
        "type": "WidgetSwitcher",
        "name": "StateSwitcher",
        "is_variable": True,
        "slot": dict(FULL_STRETCH_SLOT),
        "children": ordered_state_children,
    }

    root["children"] = other_children + [state_switcher]
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return f"wrapped {len(ordered_state_children)} state widgets"


def main():
    wrapped = 0
    for path in sorted(RECIPE_DIR.glob("*.json")):
        result = wrap_recipe(path)
        print(f"  {path.name}: {result}")
        if result.startswith("wrapped"):
            wrapped += 1
    print(f"\nDone: wrapped {wrapped} recipes.")


if __name__ == "__main__":
    main()
