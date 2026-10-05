# Mistral and OpenRouter

Status: October 5, 2026. Both adapters have offline HTTP contract tests and mocked
end-to-end executor tests. Neither supplied credential has been used for a live
request. Credential presence does not establish validity, credit or model access.

Install `pip install -e '.[hosted]'`. Store `MISTRAL_API_KEY` and
`OPENROUTER_API_KEY` in the process environment or in the ignored local `.env` file.
The SDK does not search for or automatically load credential files.

Preview configuration with no network requests:

```powershell
orqen demo-hosted --provider mistral --model YOUR_MODEL_ID --env-file .env
orqen demo-hosted --provider openrouter --model YOUR_MODEL_ID --env-file .env --dry-run
```

The preview only reports whether a credential is configured; it does not print keys,
contact the provider, validate the model ID against a catalog, or write a run report.
Model IDs are explicitly supplied rather than selecting a default billable model.
An already-set environment variable takes precedence over the named file. The small
credential-file reader supports `KEY=value` with optional matching quotes. It does
not execute shell syntax, expand variables, or change process environment variables.

When a live check is authorized, adding `--live` enables exactly one planning request
for the fixed addition smoke task. `--max-output-tokens` defaults to 512 and
`--timeout` to 60 seconds. The call may be billable even if validation fails. Request
and output limits do not constitute a monetary spending cap. Reports default to
ignored `runs/hosted-demo.json`; they contain settings, safe status categories,
reported token usage, returned model/provider and executor trace metadata.

For Python integration:

```python
from pathlib import Path
from orqen.planning import JSONPlanner
from orqen.providers.hosted import HostedConfig, HostedTransport, load_api_key

settings = HostedConfig("mistral", "YOUR_MODEL_ID", max_requests=1)
transport = HostedTransport(
    settings,
    api_key=load_api_key("mistral", env_file=Path(".env")),
    allow_live=False,  # explicitly enable only when the application authorizes inference
)
planner = JSONPlanner(transport)
```

Calls use fixed HTTPS origins, with redirects, environment proxies and automatic
retries disabled. The per-instance allowance is reserved before awaiting I/O, so
concurrent calls cannot exceed it. Timeout and cancellation consume an allowance:
the provider may already have processed the request. The engine planning budget
is enforced separately. No provider response can grant tool permissions or bypass
the task verifier.

Both transports request JSON object mode, include the planning schema in the prompt,
and leave contract enforcement to `JSONPlanner`. They reject partial completions,
refusals, native tool calls, multiple choices and oversized responses. There is no
automatic switch to another model or weaker format on failure. Provider JSON mode
does not itself prove schema adherence or business correctness.

Mistral receives `random_seed`; OpenRouter receives `seed`. OpenRouter routing
requires support for the supplied parameters, disables fallback and requests
`data_collection: deny`. Use `--routing-provider` for a specific provider slug;
without it, initial routing is selected by OpenRouter. These preferences can reduce
available model endpoints and are not a guarantee of deterministic hosted weights
or a substitute for provider data-policy review. Costs remain unknown when the
adapter lacks a verified price; missing usage remains unknown rather than zero.

Contracts checked against the official [Mistral chat API](https://docs.mistral.ai/api/endpoint/chat),
[Mistral JSON mode](https://docs.mistral.ai/studio/conversations/structured-output/json_mode),
[OpenRouter parameters](https://openrouter.ai/docs/api_reference/parameters) and
[OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection).
