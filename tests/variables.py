from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


class Variables:
    def __init__(self, data: dict[str, Any], test_id: str):
        self._data = data
        self._test_id = test_id

    def require(self, key: str) -> Any:
        if key not in self._data:
            raise AssertionError(
                f"[{self._test_id}] missing required key '{key}' in JSON test variables"
            )
        return self._data[key]
    
    def optional(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def str(self, key: str) -> str:
        v = self.require(key)
        if not isinstance(v, str):
            raise AssertionError(
                f"[{self._test_id}] '{key}' must be a string, got {type(v).__name__}"
            )
        return v

    def int(self, key: str) -> int:
        v = self.require(key)
        if not isinstance(v, int):
            raise AssertionError(
                f"[{self._test_id}] '{key}' must be an int, got {type(v).__name__}"
            )
        return v

    def bool(self, key: str) -> bool:
        v = self.require(key)
        if not isinstance(v, bool):
            raise AssertionError(
                f"[{self._test_id}] '{key}' must be a bool, got {type(v).__name__}"
            )
        return v

    def dict(self, key: str) -> dict[str, Any]:
        v = self.require(key)
        if not isinstance(v, dict):
            raise AssertionError(
                f"[{self._test_id}] '{key}' must be a dict, got {type(v).__name__}"
            )
        return v

    def list(self, key: str) -> list[Any]:
        v = self.require(key)
        if not isinstance(v, list):
            raise AssertionError(
                f"[{self._test_id}] '{key}' must be a list, got {type(v).__name__}"
            )
        return v

    def __getitem__(self, key: str) -> Any:
        return self.require(key)


def _vars_file_path() -> Path:
    return Path(__file__).parent / "data" / "test_vars.json"


def load_variables() -> dict[str, Any]:
    path = _vars_file_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise RuntimeError(f"Missing test variables JSON file: {path}") from e

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in test variables file: {path} ({e})") from e

    if not isinstance(data, dict):
        raise RuntimeError(f"Top-level JSON must be an object/dict in: {path}")

    return data


def _suite_from_nodeid(nodeid: str) -> str:
    nodeid_norm = nodeid.replace("\\", "/")
    if "tests/" in nodeid_norm:
        nodeid_norm = nodeid_norm.split("tests/", 1)[1]
    parts = nodeid_norm.split("/", 1)
    return parts[0] if parts else "tests"


def _test_name_from_node(request: pytest.FixtureRequest) -> str:
    node = request.node
    # originalname is stable even when parametrized (node.name becomes test_x[param])
    return node.originalname or node.name.split("[", 1)[0]


def init_variables(request: pytest.FixtureRequest, _all_test_vars: dict[str, Any]) -> Variables:
    node = request.node
    suite = _suite_from_nodeid(node.nodeid)
    cls_name = request.cls.__name__ if request.cls else None
    test_name = _test_name_from_node(request)
    test_id = f"{suite}.{cls_name or '<module>'}.{test_name}"

    globals_block = _all_test_vars.get("_globals_", {})
    if not isinstance(globals_block, dict):
        raise AssertionError("_globals_ must be a JSON object/dict")

    suite_block = _all_test_vars.get(suite, {})
    if not isinstance(suite_block, dict):
        raise AssertionError(f"Suite '{suite}' must be a JSON object/dict")

    suite_globals_block = suite_block.get("_globals_", {})
    if not isinstance(suite_globals_block, dict):
        raise AssertionError(f"{suite}._globals_ must be a JSON object/dict")

    class_block = suite_block.get(cls_name, {}) if cls_name else {}
    if not isinstance(class_block, dict):
        raise AssertionError(f"'{suite}.{cls_name}' must be a JSON object/dict")

    test_block = class_block.get(test_name, {})
    if not isinstance(test_block, dict):
        raise AssertionError(f"{test_id} must be a JSON object/dict")

    merged = {**globals_block, **suite_globals_block, **test_block}

    if merged.get("enabled", True) is False:
        skip_reason = merged.get("skip", "disabled by config.")
        pytest.skip(f"{test_id}: {skip_reason}")

    return Variables(data=merged, test_id=test_id)
