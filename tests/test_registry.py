"""Registry sanity: every toolset loads, every tool has a valid schema."""

from __future__ import annotations

from omniuse.tools import TOOLSETS, get_tool_schemas, run_tool


def test_all_toolsets_load():
    assert len(TOOLSETS) >= 24, f"expected >= 24 toolsets, got {len(TOOLSETS)}"


def test_all_schemas_valid():
    schemas = get_tool_schemas(None)
    assert len(schemas) >= 120
    for schema in schemas:
        fn = schema["function"]
        assert fn["name"], "schema missing a name"
        assert schema["type"] == "function"
        assert isinstance(fn.get("parameters", {}).get("properties", {}), dict)


def test_unknown_toolset_raises():
    try:
        get_tool_schemas(["definitely-not-a-toolset"])
        assert False, "should have raised"
    except ValueError as e:
        assert "Unknown toolset" in str(e)


def test_run_tool_unknown_name():
    result = run_tool("no_such_tool_xyz", {})
    assert result.startswith("ERROR")


def test_run_tool_bad_arguments():
    result = run_tool("text_case", "not-a-dict")
    assert result.startswith("ERROR")
