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
    args = parser.parse_args()
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
