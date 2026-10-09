"""Preview, negative-control, or run a bounded local AgentArch pilot.

No model call occurs unless --run-local is supplied. No hosted API is supported.
Raw model text, tool arguments, observations and official labels are not exported.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import random
import subprocess
import sys
from dataclasses import asdict, replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from orqen import Budget
from orqen.agentarch import USE_CASES, AgentArchDataset
from orqen.agentarch_evaluation import MODES, run_case
from orqen.evaluation import write_report
from orqen.model_evaluation import model_identity, source_fingerprint
from orqen.providers.ollama import OllamaConfig, OllamaTransport


def grader_fingerprint(checkout: Path) -> str:
    """Reject changed/extra upstream Python code before importing the grader."""
    changed = subprocess.check_output(
        [
            "git",
            "-C",
            str(checkout),
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "agent_arch",
        ],
        text=True,
        timeout=15,
    )
    if changed.strip():
        raise ValueError("Upstream grader tree must be pristine")
    tracked = (
        subprocess.check_output(
            ["git", "-C", str(checkout), "ls-files", "-z", "--", "agent_arch"], timeout=15
        )
        .decode()
        .split("\0")
    )
    files = sorted(p for p in tracked if p.endswith(".py"))
    actual = {p.relative_to(checkout).as_posix() for p in (checkout / "agent_arch").rglob("*.py")}
    if actual != set(files):
        raise ValueError("Unexpected upstream Python files")
    digest = hashlib.sha256()
    for name in files:
        digest.update(name.encode())
        digest.update((checkout / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def official_grader(checkout: Path):
    for name, module in tuple(sys.modules.items()):
        if name == "agent_arch" or name.startswith("agent_arch."):
            origin = getattr(module, "__file__", None)
            if origin and not Path(origin).resolve().is_relative_to(checkout):
                raise ValueError("Another AgentArch installation is already imported")
    sys.path.insert(0, str(checkout))
    module = importlib.import_module("agent_arch.metrics")
    if not Path(module.__file__).resolve().is_relative_to(checkout):
        raise ValueError("Official grader imported from the wrong checkout")
    return module.run_metrics


def dependency_versions() -> dict:
    result = {}
    for name in ("orqen", "httpx", "jsonschema", "PyYAML", "pandas", "numpy", "pydantic"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


def runner_fingerprint() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


async def evaluate(args) -> dict:
    checkout = args.checkout.resolve()
    dataset = AgentArchDataset(checkout, args.use_case)
    all_ids = [c["id"] for c in dataset.cases()]
    case_ids = all_ids if args.cases == ["all"] else args.cases
    if not case_ids or len(set(case_ids)) != len(case_ids) or not set(case_ids) <= set(all_ids):
        raise ValueError("Select unique case IDs from the pinned dataset, or all")
    if not 1 <= args.repetitions <= 100 or len(set(args.modes)) != len(args.modes):
        raise ValueError("Use 1–100 repetitions and unique modes")
    budget = Budget(
        max_calls=args.max_calls,
        max_steps=args.max_calls,
        max_planner_calls=args.max_planner_calls,
        max_retries=0,
        timeout_seconds=args.timeout,
    )
    if budget.max_calls < 1 or budget.max_planner_calls < 1:
        raise ValueError("Benchmark call budgets must be positive")
    config = OllamaConfig(
        args.model, timeout_seconds=args.request_timeout, max_output_tokens=1024, seed=args.seed
    )
    protocol = {
        "dataset": dataset.provenance,
        "case_ids": case_ids,
        "modes": args.modes,
        "repetitions": args.repetitions,
        "order_seed": args.seed,
        "budget": asdict(budget),
        "model_settings": None if args.negative_control else asdict(config),
        "treatment": "finish-only-negative-control" if args.negative_control else "local-model",
        "grader_mode": "single_agent",
        "thinking_tools": False,
        "max_context_bytes": 65536,
    }
    report = {
        "suite": "agentarch-pilot-v1",
        "report_status": "preview",
        "evidence": "Public AgentArch mocks; not real backend or architecture-superiority evidence",
        "protocol": protocol,
        "protocol_sha256": hashlib.sha256(
            json.dumps(protocol, sort_keys=True).encode()
        ).hexdigest(),
        "source_sha256": source_fingerprint(),
        "runner_sha256": runner_fingerprint(),
        "environment": dependency_versions(),
        "rows": [],
        "scheduled_runs": len(case_ids) * len(args.modes) * args.repetitions,
        "completed_runs": 0,
    }
    if not args.run_local and not args.negative_control:
        report["network_requests"] = 0
        write_report(report, args.output)
        return report
    report["grader_sha256"] = grader_fingerprint(checkout)
    grade = official_grader(checkout)
    identity = await model_identity(config) if args.run_local else None
    report["identity"] = identity
    report["report_status"] = "running"
    report["identity_stable"] = None
    write_report(report, args.output)
    schedule = [
        (case, mode, trial)
        for trial in range(args.repetitions)
        for case in case_ids
        for mode in args.modes
    ]
    random.Random(args.seed).shuffle(schedule)
    for case, mode, trial in schedule:
        transport = OllamaTransport(replace(config, seed=config.seed + trial))

        async def negative_control(_):
            return json.dumps(
                {
                    "kind": "tools",
                    "steps": [
                        {
                            "id": "done",
                            "tool": "finish",
                            "arguments": {"message": {"literal": ""}},
                            "depends_on": [],
                        }
                    ],
                }
            )

        row = await run_case(
            dataset,
            case,
            negative_control if args.negative_control else transport,
            grade,
            mode=mode,
            budget=budget,
        )
        row["trial"] = trial
        row["provider"] = None if args.negative_control else transport.metadata()
        report["rows"].append(row)
        report["completed_runs"] = len(report["rows"])
        write_report(report, args.output)
    report["report_status"] = "complete"
    if args.run_local:
        try:
            report["identity_stable"] = identity == await model_identity(config)
        except Exception:
            report["report_status"] = "identity_unavailable"
    report["source_stable"] = report["source_sha256"] == source_fingerprint()
    report["runner_stable"] = report["runner_sha256"] == runner_fingerprint()
    try:
        report["grader_stable"] = report["grader_sha256"] == grader_fingerprint(checkout)
    except Exception:
        report["grader_stable"] = False
    report["summaries"] = [
        {
            "mode": mode,
            "attempted": sum(r["mode"] == mode for r in report["rows"]),
            "graded": sum(r["mode"] == mode and r["graded"] for r in report["rows"]),
            "official_strict_successes": sum(
                r["mode"] == mode and r["official_strict_success"] is True for r in report["rows"]
            ),
        }
        for mode in args.modes
    ]
    write_report(report, args.output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--use-case", choices=USE_CASES, required=True)
    parser.add_argument("--cases", nargs="+", default=["2"])
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--max-calls", type=int, default=8)
    parser.add_argument("--max-planner-calls", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--request-timeout", type=float, default=120)
    parser.add_argument("--output", type=Path, default=Path("runs/agentarch-pilot.json"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run-local", action="store_true")
    mode.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(evaluate(args))
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("report_status", "scheduled_runs", "completed_runs", "summaries")
                if k in report
            },
            indent=2,
        )
    )
    if (
        report["report_status"] not in {"complete", "preview"}
        or any(
            report.get(k) is False
            for k in ("source_stable", "runner_stable", "grader_stable", "identity_stable")
        )
        or any(not row["graded"] for row in report["rows"])
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
