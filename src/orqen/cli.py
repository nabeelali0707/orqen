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
    args = parser.parse_args()
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
