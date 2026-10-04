# What remains to complete Orqen

Status: October 4, 2026. The repository contains an executable SDK and local experiments. It is not yet a validated adaptive-agent research result or production service.

## Recommended finish line

Finish a **research MVP** first: one documented enterprise workflow, a working real-model integration, fixed and experimental policies evaluated fairly, and an honest report showing whether the added components help. Keep the SDK and command-line interface. A dashboard, hosted API, MCP server, and multi-agent system are optional later directions, not prerequisites for that result.

The original hypothesis can fail. A report showing that a simpler baseline is equally good or better is a valid research outcome, provided the experiment is sound.

## Completed foundation

- Typed tool/task contracts, dependency ordering, whole-plan preflight, permissions, action checks, bounded read recovery, and partial-write metadata.
- Strict JSON planning, optional catalog filtering, and bounded catalog expansion.
- Stateful fault tests and catalog prerequisite-coverage experiments, with their limitations documented.
- Optional Ollama HTTP adapter with model settings, reported token usage, error handling, and offline transport tests.
- A bounded model smoke command and a dry-run mode that makes no network requests.

These establish implementation behavior. They do not establish natural-language task success, live provider compatibility, or a useful improvement over existing frameworks.

## Inputs needed from the project owner

| Input | Why it matters | Smallest useful answer |
| --- | --- | --- |
| Intended deliverable and deadline | Separates a research prototype from a production product and prevents unnecessary platform work | Research/capstone, reusable SDK, or production pilot; target date |
| Model access and resource budget | Required for real inference and reproducible comparison | An installed local model with a running Ollama server, or the chosen hosted provider/model with credentials configured locally and an explicit spending cap |
| First real workflow and examples | Supplies business meaning that schemas and research papers cannot infer | Choose support routing, time off, or another workflow; ideally provide 20–50 anonymized examples with expected outcomes, required actions, and policy rules |
| Definition of acceptable behavior | Prevents optimizing completion at the expense of incorrect actions or impractical overhead | Nonnegotiable rules, actions requiring confirmation, and acceptable latency/cost per task |

If proprietary examples are unavailable, use a public benchmark first and explicitly limit conclusions to it. Twenty to fifty examples are a starting collection target, not a guarantee of statistical power. More independent tasks or trials may be needed after examining variance and failure categories.

Do not paste API keys into chat or tracked configuration. Set credentials through the provider's local environment or secret store if a hosted integration is chosen. No key is needed for the default local Ollama adapter.

During implementation, the Ollama executable was found on this Windows machine, but the default `127.0.0.1:11434` model-catalog endpoint could not be read. No model was downloaded and no inference was started. A server on another configured endpoint may still be available.

## Remaining engineering and validation

1. **Live compatibility:** record Ollama/server version and model digest, then run the one-call smoke test. Resolve any model-specific schema, context, or output-limit issues. Passing this check proves connectivity and one plan only.
2. **Domain adapter and independent grader:** implement the selected workflow's tools against a sandbox or controlled fixtures. Define preconditions, postconditions, and an independent state-based grader. Preserve an upstream revision if AgentArch data is used.
3. **Fair baseline:** compare ordinary fixed workflow code or a fixed agent to Orqen with equivalent tools, permissions, model settings, and budget. Do not compare mere strategy labels as different algorithms. Adaptive branching/replanning is not implemented and should be added only if this workflow requires it.
4. **Frozen evaluation:** separate development from held-out cases, pin settings and data revisions, and record failures, usage, latency, recovery, and unsafe effects. Run paired trials. Use framework-native validation as a comparison if claiming an advantage over an existing framework.
5. **Evidence report:** report task success and uncertainty alongside cost and latency. Keep, simplify, or remove experimental components based on those results. Never use fixture coverage as an agent-success score.
6. **Delivery:** provide installation instructions, a reproducible command, versioned package, examples, limitations, and the final research report. Choose a repository license before distributing the SDK for outside reuse.

Production deployment is a separate scope. It may require persistent execution records, backend idempotency/reconciliation, authentication, tenant separation, operational monitoring, and integration-specific security review. These are not currently implemented.

## Current Git policy

Create local commits after each verified milestone. Do not push, publish, or deploy unless the user explicitly authorizes it again.
