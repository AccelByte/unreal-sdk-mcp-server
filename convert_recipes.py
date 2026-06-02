"""
Convert recipe JSON files from hardcoded position+size slots to anchor-based slots.

Patterns:
  Pattern A (full-panel): main block spans full width top 82%, state widgets at bottom
  Pattern B (centered):   main block centered horizontally with margins

Slot assignments are driven by child name suffix:
  *_SuccessBlock / (first child / none of the below) → Pattern A or B main slot
  *_IdleStatus   → anchors [0, 0.82, 1, 1], full width bottom strip
  *_LoadingState → anchors [0.5, 0.87, 0.5, 0.87], centered, auto_size
  *_EmptyState   → anchors [0.5, 0.87, 0.5, 0.87], centered, auto_size
  *_ErrorState   → anchors [0, 0.87, 1, 1], full width bottom strip
"""

import json
from pathlib import Path

RECIPE_DIR = Path(__file__).parent / "data/AccelByteUITools/Tools/specs/recipes"

SKIP = {"ags_user_profile_panel.json", "ags_tabbed_social_panel.json"}

PATTERN_B = {
    "ags_login_panel.json",
    "ags_account_link_panel.json",
    "ags_session_expired_panel.json",
    "ags_action_modal.json",
}

SLOT_MAIN_A = {"anchors": [0, 0, 1, 0.82], "offsets": [0, 0, 0, 0], "alignment": [0, 0]}
SLOT_MAIN_B = {"anchors": [0.1, 0.05, 0.9, 0.82], "offsets": [0, 0, 0, 0], "alignment": [0, 0]}
SLOT_IDLE   = {"anchors": [0, 0.82, 1, 1], "offsets": [0, 0, 0, 0], "alignment": [0, 0]}
SLOT_LOAD   = {"anchors": [0.5, 0.87, 0.5, 0.87], "offsets": [0, 0, 0, 0], "alignment": [0.5, 0.5], "auto_size": True}
SLOT_EMPTY  = {"anchors": [0.5, 0.87, 0.5, 0.87], "offsets": [0, 0, 0, 0], "alignment": [0.5, 0.5], "auto_size": True}
SLOT_ERROR  = {"anchors": [0, 0.87, 1, 1], "offsets": [0, 0, 0, 0], "alignment": [0, 0]}


def classify_child(name: str, is_first: bool, is_pattern_b: bool) -> dict:
    n = name.lower()
    if n.endswith("_idlestatus") or n.endswith("_idlestate"):
        return SLOT_IDLE
    if n.endswith("_loadingstate"):
        return SLOT_LOAD
    if n.endswith("_emptystate"):
        return SLOT_EMPTY
    if n.endswith("_errorstate"):
        return SLOT_ERROR
    # Main content block (SuccessBlock or first child)
    return SLOT_MAIN_B if is_pattern_b else SLOT_MAIN_A


def convert(path: Path, is_pattern_b: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    children = data["root"].get("children", [])
    for i, child in enumerate(children):
        slot = classify_child(child["name"], i == 0, is_pattern_b)
        child["slot"] = dict(slot)
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    print(f"  converted ({('B' if is_pattern_b else 'A')}): {path.name}")


def main():
    converted = 0
    skipped = 0
    for path in sorted(RECIPE_DIR.glob("*.json")):
        if path.name in SKIP:
            print(f"  skipped:   {path.name}")
            skipped += 1
            continue
        is_pattern_b = path.name in PATTERN_B
        convert(path, is_pattern_b)
        converted += 1
    print(f"\nDone: {converted} converted, {skipped} skipped.")


if __name__ == "__main__":
    main()
