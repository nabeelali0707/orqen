"""Run the offline conditional refund regression experiment."""

import asyncio
import json

from orqen.return_workflow import evaluate_returns

if __name__ == "__main__":
    report = asyncio.run(evaluate_returns())
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["checks_passed"] == report["runs"] else 1)
