"""Command-line entry point for reproducible local experiments."""

import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="orqen", description="Adaptive Agent Orchestrator")
    parser.add_argument("--version", action="version", version=f"orqen {version('orqen')}")
    subparsers = parser.add_subparsers(dest="command")
    evaluate_parser = subparsers.add_parser("evaluate", help="Run local deterministic fault cases")
    evaluate_parser.add_argument("--repetitions", type=int, default=3)
    evaluate_parser.add_argument("--seed", type=int, default=0)
    evaluate_parser.add_argument("--output", type=Path, default=Path("runs/local-evaluation.json"))
    evaluate_parser.add_argument("--traces", type=Path)
    catalog_parser = subparsers.add_parser(
        "evaluate-catalog", help="Measure required-tool coverage"
    )
    catalog_parser.add_argument("--dataset", type=Path)
    catalog_parser.add_argument("--output", type=Path, default=Path("runs/catalog-evaluation.json"))
    model_parser = subparsers.add_parser(
        "demo-ollama", help="Run one bounded local-model smoke test"
    )
    model_parser.add_argument("--model", required=True)
    model_parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    model_parser.add_argument("--timeout", type=float, default=60.0)
    model_parser.add_argument("--seed", type=int, default=0)
    model_parser.add_argument("--max-output-tokens", type=int, default=2048)
    model_parser.add_argument("--allow-remote", action="store_true")
    model_parser.add_argument(
        "--dry-run", action="store_true", help="Show config without inference"
    )
    model_parser.add_argument("--output", type=Path, default=Path("runs/ollama-demo.json"))
    hosted = subparsers.add_parser(
        "demo-hosted", help="Preview or explicitly run a hosted smoke test"
    )
    hosted.add_argument("--provider", required=True, choices=("mistral", "openrouter"))
    hosted.add_argument("--model", required=True)
    hosted.add_argument("--seed", type=int, default=0)
    hosted.add_argument("--max-output-tokens", type=int, default=512)
    hosted.add_argument("--timeout", type=float, default=60.0)
    hosted.add_argument("--routing-provider")
    hosted.add_argument("--env-file", type=Path, help="Read credentials from this file explicitly")
    hosted.add_argument("--output", type=Path, default=Path("runs/hosted-demo.json"))
    mode = hosted.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Enable one potentially billable request")
    mode.add_argument("--dry-run", action="store_true", help="Default: preview without a request")
    trials = subparsers.add_parser("evaluate-model", help="Run bounded local model ablations")
    trials.add_argument("--model", required=True)
    trials.add_argument("--repetitions", type=int, default=2)
    trials.add_argument("--seed", type=int, default=0)
    trials.add_argument("--timeout", type=float, default=120)
    trials.add_argument(
        "--variants", nargs="+", choices=("baseline", "retrieval", "no_recovery", "proposal_review")
    )
    trials.add_argument("--faults", choices=("both", "none", "transient"), default="both")
    trials.add_argument(
        "--constrain-step-ids",
        action="store_true",
        help="Encode application step identifiers in the planning contract",
    )
    trials.add_argument(
        "--dry-run", action="store_true", help="Preview the bounded schedule without inference"
    )
    trials.add_argument("--output", type=Path, default=Path("runs/model-evaluation.json"))
    serve = subparsers.add_parser("serve", help="Serve the authenticated API and dashboard")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--database", type=Path, default=Path("runs/service.sqlite3"))
    mcp = subparsers.add_parser("mcp", help="Serve registered workflows over MCP stdio")
    mcp.add_argument("--database", type=Path, default=Path("runs/mcp.sqlite3"))
    args = parser.parse_args()
    if args.command == "demo-hosted":
        from .providers.hosted import HostedConfig, HostedTransport, load_api_key

        try:
            config = HostedConfig(
                args.provider,
                args.model,
                seed=args.seed,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout,
                routing_provider=args.routing_provider,
            )
        except (ValueError, TypeError):
            parser.error("Invalid hosted provider settings; see docs/hosted-providers.md")
        try:
            api_key = load_api_key(args.provider, env_file=args.env_file)
        except ValueError:
            api_key = None
        if not args.live:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "network_requests": 0,
                        "credential_configured": api_key is not None,
                        "provider": HostedTransport(config).metadata(),
                    },
                    indent=2,
                )
            )
            return
        if api_key is None:
            parser.error("Provider credential is missing or invalid; use environment or --env-file")
        from importlib.util import find_spec

        if find_spec("httpx") is None:
            parser.error("Install the optional transport with pip install 'orqen[hosted]'")
        from .demo import run_hosted_demo
        from .evaluation import write_report

        report = asyncio.run(run_hosted_demo(config, api_key=api_key, allow_live=True))
        write_report(report, args.output)
        print(json.dumps(report, indent=2))
        if not report["passed"]:
            raise SystemExit(1)
        return
    if args.command in {"serve", "mcp"}:
        from .api import Principal
        from .service import demo_service

        service = demo_service(args.database)
        if args.command == "mcp":
            from .mcp_server import create_mcp

            create_mcp(service, Principal("local-mcp")).run(transport="stdio")
        else:
            import os

            import uvicorn

            from .api import create_app

            token = os.environ.get("ORQEN_API_TOKEN", "")
            if len(token) < 32:
                parser.error("Set ORQEN_API_TOKEN to a randomly generated token of 32+ characters")
            uvicorn.run(
                create_app(service, {token: Principal("operator")}),
                host=args.host,
                port=args.port,
                access_log=False,
                proxy_headers=False,
            )
        return
    if args.command == "evaluate-model":
        from .evaluation import write_report
        from .model_evaluation import VARIANTS, evaluate_models
        from .providers.ollama import OllamaConfig

        config = OllamaConfig(
            args.model, seed=args.seed, timeout_seconds=args.timeout, max_output_tokens=512
        )
        variants = tuple(args.variants) if args.variants else VARIANTS
        faults = {"both": (False, True), "none": (False,), "transient": (True,)}[args.faults]
        if not 1 <= args.repetitions <= 100 or len(set(variants)) != len(variants):
            parser.error("Use 1–100 repetitions and unique variants")
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "network_requests": 0,
                        "scheduled_runs": args.repetitions * len(variants) * len(faults),
                        "max_planning_calls": args.repetitions
                        * len(faults)
                        * sum(2 if v in {"proposal_review", "retrieval"} else 1 for v in variants),
                        "variants": variants,
                        "faults": faults,
                        "constrain_step_ids": args.constrain_step_ids,
                    },
                    indent=2,
                )
            )
            return
        report = asyncio.run(
            evaluate_models(
                config,
                repetitions=args.repetitions,
                seed=args.seed,
                variants=variants,
                faults=faults,
                checkpoint=args.output,
                constrain_step_ids=args.constrain_step_ids,
            )
        )
        write_report(report, args.output)
        print(
            json.dumps(
                {
                    "report_status": report["report_status"],
                    "identity_stable": report["identity_stable"],
                    "source_stable": report["source_stable"],
                    "summaries": report["summaries"],
                },
                indent=2,
            )
        )
        if report["identity_stable"] is not True or report["source_stable"] is not True:
            raise SystemExit(1)
        return
    if args.command == "demo-ollama":
        from .providers.ollama import OllamaConfig, OllamaTransport

        try:
            config = OllamaConfig(
                args.model,
                base_url=args.base_url,
                seed=args.seed,
                timeout_seconds=args.timeout,
                allow_remote=args.allow_remote,
                max_output_tokens=args.max_output_tokens,
            )
        except (ValueError, TypeError):
            parser.error("Invalid model transport settings; see docs/ollama.md")
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "network_requests": 0,
                        "provider": OllamaTransport(config).metadata(),
                    },
                    indent=2,
                )
            )
            return
        from importlib.util import find_spec

        if find_spec("httpx") is None:
            parser.error("Install the optional transport with pip install 'orqen[ollama]'")
        from .demo import run_ollama_demo
        from .evaluation import write_report

        report = asyncio.run(run_ollama_demo(config))
        write_report(report, args.output)
        print(json.dumps(report, indent=2))
        print(f"Report: {args.output.resolve()}")
        if not report["passed"]:
            raise SystemExit(1)
        return
    if args.command == "evaluate-catalog":
        from .catalog_evaluation import default_dataset, evaluate_catalog
        from .evaluation import write_report

        try:
            dataset = (
                json.loads(args.dataset.read_text("utf-8")) if args.dataset else default_dataset()
            )
            report = evaluate_catalog(dataset)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        write_report(report, args.output)
        print(
            json.dumps({"evidence": report["evidence"], "summaries": report["summaries"]}, indent=2)
        )
        print(f"Report: {args.output.resolve()}")
        return
    if args.command != "evaluate":
        parser.print_help()
        return
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    if args.traces and args.traces.resolve() == args.output.resolve():
        parser.error("--output and --traces must be different files")
    from .evaluation import evaluate, write_report, write_traces

    report = asyncio.run(evaluate(repetitions=args.repetitions, seed=args.seed))
    write_report(report, args.output)
    if args.traces:
        write_traces(report, args.traces)
    print(json.dumps({"evidence": report["evidence"], "summaries": report["summaries"]}, indent=2))
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
