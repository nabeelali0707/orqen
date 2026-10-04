import asyncio
import json
import sys

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_real_stdio_client_discovers_executes_and_reads_workflow(tmp_path):
    async def check():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "orqen.cli", "mcp", "--database", str(tmp_path / "db")],
        )
        async with asyncio.timeout(30):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    tools = await client.list_tools()
                    assert {t.name for t in tools.tools} == {
                        "list_workflows",
                        "execute_workflow",
                        "get_execution",
                        "list_executions",
                    }
                    result = await client.call_tool(
                        "execute_workflow",
                        {"task": "addition", "inputs": {"a": 2, "b": 3}, "idempotency_key": "one"},
                    )
                    assert not result.isError
                    row = json.loads(result.content[0].text)
                    assert row["trace"]["verified"]
                    fetched = await client.call_tool("get_execution", {"run_id": row["id"]})
                    assert json.loads(fetched.content[0].text) == row

    asyncio.run(check())
