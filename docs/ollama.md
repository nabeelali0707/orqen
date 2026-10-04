# Optional Ollama transport

Orqen now includes a callable HTTP transport for a configured Ollama server. It plugs into `JSONPlanner`; provider code remains separate from the executor. No model is selected automatically, downloaded, started, or contacted on import.

Install the optional dependency from this checkout:

```powershell
.\.venv\isolated\Scripts\python.exe -m pip install -e ".[ollama]"
```

```python
from orqen import JSONPlanner, Orchestrator
from orqen.providers.ollama import OllamaConfig, OllamaTransport

transport = OllamaTransport(OllamaConfig(model="YOUR_INSTALLED_MODEL"))
engine = Orchestrator(registry, planner=JSONPlanner(transport))
# result = await engine.run(your_task, budget=your_budget)
# metadata = transport.metadata()
```

Use one transport instance per run when associating its request records with a run. The default endpoint is `http://127.0.0.1:11434`; a different loopback origin can be configured. Remote endpoints require `allow_remote=True` and HTTPS. URLs containing credentials, query strings, or paths are rejected. Environment proxy settings and redirects are disabled. The adapter has no automatic HTTP retry; the executor may make a separate planning request only for explicit catalog expansion.

The adapter uses `POST /api/chat`, requests nonstreaming structured output, passes the plan schema as `format`, and records provider-reported prompt and generation token counts. These fields follow the [official chat API](https://docs.ollama.com/api/chat). The schema is also included in the prompt, as recommended by the [structured-output documentation](https://docs.ollama.com/capabilities/structured-outputs). Model/server support still requires a live compatibility check.

## Bounds and records

`OllamaConfig` requires an explicit model name and records temperature, seed, generation-token limit, context limit, timeout, and response-byte limit. Defaults are temperature 0, seed 0, 2,048 output tokens, 8,192 context tokens, 60 seconds, and 1 MiB of response JSON. The server's actual behavior and resource use remain outside Orqen's control. Context truncation and schema support vary with the selected model and server version.

`metadata()` contains settings, a system-instruction fingerprint, and per-request status, returned model name, reported token counts, and elapsed time. It excludes goals, prompts, generated plans, raw provider errors, and tool outputs. Missing or malformed token counts remain `None`; cost remains `None`. A model tag is not an immutable version: record the installed model digest and Ollama version before a controlled experiment.

Incomplete responses, output-limit termination, unexpected native tool calls, invalid HTTP responses, oversized responses, and provider errors are rejected. Transport failures map to `planner_transport_error` and do not execute tools. Invalid generated JSON still maps to `invalid_plan`. Cancellation propagates and is recorded; Orqen's overall run deadline may be shorter than the transport timeout.

## Validation status

HTTP contract tests use an injected HTTPX mock transport. They cover payload settings, returned usage, cancellation, response size, timeouts, redirects, error redaction, and end-to-end executor integration. They do not establish live model compatibility, plan quality, or task success. A real configured model and approved experiment scope are still needed.
