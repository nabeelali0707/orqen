"""MCP stdio interface using the official SDK and the shared execution service."""

from __future__ import annotations

from .api import Principal
from .service import ExecutionService, ServiceError


def create_mcp(service: ExecutionService, principal: Principal):
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("Orqen")

    @server.tool()
    def list_workflows() -> list[dict]:
        """List registered workflows available to this local MCP process."""
        return service.catalog(principal.permissions)

    @server.tool()
    async def execute_workflow(task: str, inputs: dict, idempotency_key: str) -> dict:
        """Run a registered workflow. Reuse the key when checking an uncertain response.

        The server owns permissions, budgets and verification. Never invent a new
        key to retry an uncertain state-changing operation.
        """
        try:
            return await service.execute(
                principal.name, principal.permissions, task, inputs, idempotency_key
            )
        except ServiceError as exc:
            return {"error": str(exc), "status": exc.status}
        except Exception:
            return {
                "error": "Execution unavailable; inspect history before retrying",
                "status": 500,
            }

    @server.tool()
    def get_execution(run_id: str) -> dict:
        """Read this principal's execution metadata without rerunning tools."""
        try:
            return service.get(principal.name, run_id)
        except ServiceError as exc:
            return {"error": str(exc), "status": exc.status}

    @server.tool()
    def list_executions() -> list[dict]:
        """List this principal's latest 100 executions; raw tool results are omitted."""
        return service.history(principal.name)

    return server
