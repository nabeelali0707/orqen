# API, dashboard and MCP

Install `pip install -e '.[web,mcp]'`. The default interfaces expose one registered,
verified addition workflow. They run the actual SDK executor and persist metadata
to SQLite; they do not expose arbitrary Python or unrestricted tool execution.

Generate a random API token locally, put it in `ORQEN_API_TOKEN` (32+ ASCII characters),
and start `orqen serve`. Open <http://127.0.0.1:8080> and enter the token. The dashboard
keeps it in tab memory only. It lists permitted tasks, validates executions through
the service, shows history and displays verification, calls, retries and reconciliation
metadata. Disconnect clears the visible history and token. HTTP access logging is off.

Authenticated routes:

| Route | Purpose |
| --- | --- |
| `GET /v1/tasks` | Allowed workflow names and input schemas |
| `POST /v1/runs` | JSON `{"task":"addition","inputs":{"a":2,"b":3}}` |
| `GET /v1/runs` | This principal's latest 100 runs |
| `GET /v1/runs/{id}` | This principal's run metadata |

Use `Authorization: Bearer <token>` and a unique `Idempotency-Key` on POST. Reuse
the same key and inputs after a lost response. A different payload with the same
key returns 409. The health endpoint and static dashboard shell are public; task
data and execution require authentication. No cookies or cross-origin API access
are enabled. Request bodies are capped at 16 KiB; up to four executions run at once.
History is capped at 10,000 rows and requires operator archival before more work.

Configure real workflows in Python with `RegisteredTask`, `ExecutionService`,
`Principal` and `create_app`. Task builders, input schemas, budgets, verifiers and
principal permissions belong to trusted server configuration. A bearer token maps
to one principal. This prototype has no user signup, token issuance UI, OAuth or
multi-tenant administration. It does not auto-confirm tools that require confirmation.

Use **one service process per SQLite database**. Restart marks interrupted runs
unknown and never replays them. Idempotency applies per principal and key; it does
not provide exactly-once side effects across different keys or backend systems.
Database files contain identifiers, payload fingerprints and traces, but no raw
goals, arguments or tool outputs. Keep the database under ignored `runs/` and secure
its filesystem permissions. Unknown writes require backend reconciliation.

## MCP

Configure an MCP client to launch your environment's `orqen` executable with
`["mcp", "--database", "<absolute-path>/runs/mcp.sqlite3"]`. This uses the official
[MCP Python SDK v1](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)
over stdio. Tools are `list_workflows`, `execute_workflow`, `get_execution` and
`list_executions`. The local process identity is `local-mcp`; its default permissions
are empty. MCP does not bypass service validation or idempotency. Host configuration
is the trust boundary for stdio; no public MCP network endpoint is exposed.

## Hosting

`orqen serve --host 0.0.0.0` supports hosting behind an HTTPS reverse proxy. The included
Dockerfile runs as a non-root user and expects the token through the environment and
a writable persistent volume at `/data`. One worker only. Configure TLS, token rotation,
backups, network restrictions and monitoring before external use. The API/dashboard
have been exercised locally; public deployment requires the owner's hosting destination
and domain. No public deployment is claimed by the roadmap's local implementation checks.
