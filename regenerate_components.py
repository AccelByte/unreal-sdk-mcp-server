"""
Regenerate all 49 AGSUI plugin component .uasset files from their updated JSON specs.

Strategy:
- Process in dependency order so referenced components are rebuilt before composites that reference them.
- Sleep briefly between requests to let the editor settle asset reloads.
- Retry transient connection failures (Unreal sometimes drops the HTTP bridge briefly during heavy asset work).

Requires the Unreal Editor running with the bridge live at :48757.
"""

import json
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

BRIDGE_URL = "http://127.0.0.1:48757/accelbyte-ui-tools/generate"
HEALTH_URL = "http://127.0.0.1:48757/accelbyte-ui-tools/health"
COMPONENT_DIR = Path(__file__).parent / "data/AccelByteUITools/Tools/specs/components/agsui"

# Order matters: rebuild atoms first, then rows/cards, then feature blocks that reference them.
PROCESSING_ORDER = [
    # 1. Core atoms — depended on by everything
    "core_badge.json",
    "core_avatar.json",
    "core_divider.json",
    "core_currency_pill.json",
    "core_section_header.json",
    "core_loading_indicator.json",
    "core_status_message.json",
    "core_empty_state.json",
    "core_secondary_button.json",
    "core_error_state.json",
    "core_toast.json",
    "core_key_value_row.json",
    # 2. Core controls
    "core_base_button.json",
    "core_danger_button.json",
    "core_icon_button.json",
    "core_text_input.json",
    "core_password_input.json",
    "core_search_input.json",
    # 3. Core panels
    "core_base_panel.json",
    "core_modal_panel.json",
    # 4. List rows
    "list_row.json",
    "player_row.json",
    "leaderboard_row.json",
    "entitlement_row.json",
    "list_panel.json",
    # 5. Feature rows + cards (referenced by feature blocks)
    "feature_friend_row.json",
    "feature_party_member_row.json",
    "feature_block_user_row.json",
    "feature_cloud_save_slot_row.json",
    "feature_session_row.json",
    "feature_incoming_friend_row.json",
    "feature_achievement_card.json",
    "feature_store_item_card.json",
    # 6. Common UI-backed button variants (require UAGSCommonButtonBase C++ class compiled in)
    "core_common_button.json",
    "core_common_secondary_button.json",
    "core_common_danger_button.json",
    "core_common_icon_button.json",
    # 7. Feature blocks (reference rows/cards above)
    "feature_login_block.json",
    "feature_account_link_block.json",
    "feature_session_expired_block.json",
    "feature_matchmaking_status_block.json",
    "feature_wallet_balance_block.json",
    "feature_generic_async_action_block.json",
    "feature_friends_list_block.json",
    "feature_party_block.json",
    "feature_session_browser_block.json",
    "feature_leaderboard_block.json",
    "feature_notification_list_block.json",
    "feature_entitlements_block.json",
    "feature_cloud_save_slots_block.json",
    "feature_stats_summary_block.json",
    "feature_achievement_grid_block.json",
    "feature_store_grid_block.json",
]

SLEEP_BETWEEN = 2.0         # seconds between successful requests — give editor time to settle
SLEEP_AFTER_FAIL = 5.0      # seconds to wait for editor recovery
MAX_RETRIES = 1             # don't burn time retrying if the editor crashed; just record + move on
REQUEST_TIMEOUT = 60
CHECKPOINT_FILE = Path(__file__).parent / ".regen_checkpoint.json"


def check_health(timeout=5):
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data.get("ok"))
    except Exception:
        return False


def wait_for_bridge(max_wait=120):
    print("  Waiting for bridge to come back...", end="", flush=True)
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        if check_health(timeout=2):
            print(" back.")
            return True
        print(".", end="", flush=True)
        time.sleep(2)
    print(" timeout.")
    return False


def generate_once(spec_path: Path) -> tuple[bool, str]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    body = json.dumps({"force": True, "spec": spec}).encode("utf-8")
    req = urllib.request.Request(BRIDGE_URL, data=body,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok") is True or (result.get("errors") in (None, [])):
                return True, result.get("asset_path", "?")
            errors = result.get("errors") or [{"message": "unknown"}]
            return False, json.dumps(errors)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        return False, f"HTTP {e.code}: {body[:200]}"
    except (urllib.error.URLError, TimeoutError, ConnectionResetError, ConnectionAbortedError) as e:
        return False, f"conn_error: {e}"


def generate_with_retry(spec_path: Path) -> tuple[bool, str]:
    last_info = ""
    for attempt in range(1, MAX_RETRIES + 1):
        ok, info = generate_once(spec_path)
        last_info = info
        if ok:
            return True, info
        # Connection / transient failure: wait for bridge to recover before retry
        if "conn_error" in info or "HTTP 5" in info:
            print(f"     attempt {attempt} failed ({info[:80]}), waiting for bridge...")
            time.sleep(SLEEP_AFTER_FAIL)
            if not wait_for_bridge(max_wait=120):
                return False, f"bridge_down after {attempt} attempts"
            continue
        # Schema / validation failure: don't retry
        return False, info
    return False, last_info


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            return set(json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_checkpoint(completed: set):
    CHECKPOINT_FILE.write_text(json.dumps(sorted(completed), indent=2), encoding="utf-8")


def main():
    if not check_health():
        print("Bridge unreachable. Open the Unreal Editor and wait for it to finish loading.")
        sys.exit(1)
    print("Bridge healthy.\n")

    completed = load_checkpoint()
    if completed:
        print(f"Resuming from checkpoint: {len(completed)} already completed; skipping those.\n")

    specs = [COMPONENT_DIR / name for name in PROCESSING_ORDER]
    missing = [p.name for p in specs if not p.exists()]
    if missing:
        print(f"Missing spec files: {missing}")
        sys.exit(1)

    todo = [p for p in specs if p.name not in completed]
    print(f"Regenerating {len(todo)} remaining (of {len(specs)} total)...\n")

    ok_count = 0
    failures = []
    bridge_died = False
    for i, path in enumerate(todo, 1):
        print(f"  [{i:2d}/{len(todo)}] {path.name}")
        ok, info = generate_with_retry(path)
        if ok:
            print(f"     OK   -> {info}")
            ok_count += 1
            completed.add(path.name)
            save_checkpoint(completed)
            time.sleep(SLEEP_BETWEEN)
        else:
            print(f"     FAIL -> {info[:200]}")
            failures.append((path.name, info))
            if "bridge_down" in info or "conn_error" in info:
                bridge_died = True
                print("\n  Bridge died. Stopping. Reopen Unreal Editor and rerun to resume from checkpoint.")
                break
            time.sleep(SLEEP_AFTER_FAIL)

    print(f"\nThis run: {ok_count} ok, {len(failures)} failed. Total completed: {len(completed)}/{len(specs)}.")
    if not failures and len(completed) == len(specs):
        print("\nAll components regenerated. Removing checkpoint.")
        CHECKPOINT_FILE.unlink(missing_ok=True)
        return
    if failures:
        print("\nFailures this run:")
        for name, info in failures:
            print(f"  - {name}: {info[:200]}")
    if bridge_died:
        sys.exit(3)
    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
