from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


TOKEN_PATH = Path(__file__).resolve().parent / "specs" / "theme_tokens.json"


def load_theme_tokens(path: Path | None = None) -> dict[str, Any]:
    token_path = path or TOKEN_PATH
    return json.loads(token_path.read_text(encoding="utf-8"))


def token_value(tokens: dict[str, Any], dotted_path: str) -> Any:
    value: Any = tokens
    for part in dotted_path.split("."):
        value = value[part]
    return deepcopy(value)


def color(tokens: dict[str, Any], name: str) -> list[float]:
    return token_value(tokens, f"colors.{name}")


def radius(tokens: dict[str, Any], name: str) -> int:
    return int(token_value(tokens, f"radius.{name}"))


def spacing(tokens: dict[str, Any], name: str) -> Any:
    return token_value(tokens, f"spacing.{name}")


def preset(tokens: dict[str, Any], name: str) -> dict[str, Any]:
    return token_value(tokens, f"presets.{name}")
