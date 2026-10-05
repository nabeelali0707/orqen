# Orqen

**Adaptive Agent Orchestrator**

Orqen is a proposed orchestration engine that helps agents choose an execution strategy, discover relevant tools, validate calls, verify outcomes, and recover from failures within explicit limits.

Orqen includes a working modular Python SDK with deterministic routing, dependency-aware execution, JSON Schema validation, application-owned permissions, task verification, and bounded read recovery. The Ollama transport has passed a live Qwen smoke test. An opt-in proposal/review planner makes two measured agent calls. An authenticated API, dashboard, and MCP stdio server expose registered workflows.

The current focus is a small contract-enforcing execution and evaluation layer. The original adaptive-orchestration concept remains a research hypothesis; see the [independent review and revised direction](docs/research-review.md).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe examples/customer_workflow.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m orqen.cli evaluate --repetitions 5 --seed 17
.\.venv\Scripts\python.exe -m orqen.cli evaluate-catalog
```

See the [SDK guide](docs/sdk.md) for integration examples and execution limits.

## Architecture

```mermaid
flowchart TD
    A[User task] --> B[1. Task Analyzer]
    B --> C[2. Strategy Router]
    C --> D[3. Adaptive Tool Router]
    D --> E[4. Execution + Verification]
    E --> F[5. Recovery + Evaluation]
    F --> G[Verified result or explicit escalation]
    F -->|Bounded safe recovery| D
```

1. **Task Analyzer:** identify task type, complexity, dependencies, risk, and missing information.
2. **Strategy Router:** select direct response, function calling, plan-and-execute, or multi-agent execution where justified.
3. **Adaptive Tool Router:** retrieve relevant tools and validate required arguments and permissions.
4. **Execution + Verification:** execute within budgets and check both tool results and task completion conditions.
5. **Recovery + Evaluation:** classify failures, attempt safe bounded recovery, and record outcomes and overhead.

## Research foundation

Inspired by [AgentArch: A Comprehensive Benchmark to Evaluate Agent Architectures in Enterprise](https://arxiv.org/abs/2509.10769), by Tara Bogavelli, Roshnee Sharma, and Hari Subramani. First submitted September 13, 2025; revised January 6, 2026. See the [official ServiceNow repository](https://github.com/ServiceNow/AgentArch).

AgentArch evaluates architectural configurations in enterprise workflows. Its task- and model-dependent findings motivate our hypothesis: selecting orchestration strategies and tool sets according to task requirements may improve reliability and efficiency over a fixed architecture.

Orqen is an independent project, not an AgentArch implementation. Its local fault suite checks executor behavior; no AgentArch results or real model performance improvements have been established.

## Project documents

- [Architecture and implementation boundaries](docs/architecture.md)
- [Python SDK usage](docs/sdk.md)
- [Structured planning and catalog policies](docs/planning.md)
- [Optional Ollama model connection](docs/ollama.md)
- [Mistral and OpenRouter setup and offline preview](docs/hosted-providers.md)
- [Measured local model outcomes](docs/model-results.md)
- [Controlled evaluation plan](docs/evaluation.md)
- [Independent research and architecture review](docs/research-review.md)
- [Measured local fault-suite results](docs/local-results.md)
- [Catalog coverage results and failures](docs/catalog-results.md)
- [Development milestones](docs/roadmap.md)
- [Completion plan and owner inputs](docs/completion-plan.md)

## Development workflow

Use `orqen` as the project and Python package name. Commit each major completed milestone after its relevant checks pass. Current instruction: keep commits local; do not push until explicitly authorized again. Keep secrets, local environments, and raw execution data out of Git.
## New research and interface commands

```powershell
python -m pip install -e '.[dev,research,web,mcp]'
orqen evaluate-model --model qwen2.5-coder:7b --repetitions 2 --timeout 180
# Set ORQEN_API_TOKEN to a locally generated random token before serving.
orqen serve
orqen mcp --database runs/mcp.sqlite3
```

The API and dashboard run at <http://127.0.0.1:8080>. See
[interface setup and deployment limits](docs/interfaces.md),
[model ablations and proposal/review agents](docs/model-experiments.md), and
[the pinned AgentArch adapter](docs/agentarch.md). Default product interfaces expose
a registered addition workflow; real business workflows are configured by the application.
