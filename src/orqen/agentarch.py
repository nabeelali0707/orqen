"""Pinned AgentArch data/tool adapter; never imports or executes upstream code."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import Tool
from .registry import ToolRegistry

UPSTREAM_REVISION = "dfdd9cd69642f74d7f2c72738c96faff7b70e59f"
USE_CASES = ("requesting_time_off", "customer_request_routing")


class AgentArchDataset:
    """Load the two published use cases from a clean, pinned local checkout.

    Ground truth is accessible only through a separate grading call. Mock tools
    reproduce upstream record-indexed responses, not real enterprise side effects.
    """

    def __init__(self, checkout: Path, use_case: str) -> None:
        if use_case not in USE_CASES:
            raise ValueError("Unsupported AgentArch use case")
        root = Path(checkout).resolve()
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        if revision != UPSTREAM_REVISION:
            raise ValueError("AgentArch checkout does not match the pinned revision")
        relative_paths = [
            f"agent_arch/configs/use_case_configs/{use_case}.yaml",
            f"agent_arch/configs/mocked_data/{use_case}_mocked_tool_calls.json",
        ]
        content = []
        for relative in relative_paths:
            raw = (root / relative).read_bytes()
            tracked = subprocess.run(
                ["git", "-C", str(root), "show", f"{revision}:{relative}"],
                check=True,
                capture_output=True,
                timeout=10,
            ).stdout
            # Git may apply CRLF on Windows checkout; compare normalized text.
            if raw.replace(b"\r\n", b"\n") != tracked.replace(b"\r\n", b"\n"):
                raise ValueError("AgentArch input differs from pinned content")
            content.append(tracked)
        import yaml

        self._config = yaml.safe_load(content[0])
        self._mock = json.loads(content[1])
        self.use_case = use_case
        self.provenance = {
            "repository": "https://github.com/ServiceNow/AgentArch",
            "revision": revision,
            "use_case": use_case,
            "input_sha256": hashlib.sha256(b"\n".join(content)).hexdigest(),
        }

    def cases(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {"id": str(c["id"]), "goal": c["user_utterance"]}
            for c in self._config["utterances_and_ground_truths"]
        )

    def session(self, case_id: str) -> AgentArchSession:
        if case_id not in {case["id"] for case in self.cases()}:
            raise ValueError("Unknown case")
        return AgentArchSession(self, case_id)


class AgentArchSession:
    def __init__(self, dataset: AgentArchDataset, case_id: str) -> None:
        self.dataset, self.case_id = dataset, case_id
        self._history: list[dict] = []
        self.registry = ToolRegistry()
        config = dataset._config
        self.instructions = (
            config["use_case_instructions"]
            + "\n"
            + "\n".join(
                agent.get("agent_instructions") or "" for agent in config["agents"].values()
            )
        )
        unique = {}
        for agent_name, agent in config["agents"].items():
            for tool in agent["tools"]:
                unique[tool["tool_name"]] = (agent_name, tool)
        for name, (agent_name, tool) in unique.items():
            properties = deepcopy(tool.get("input_parameters", {}))
            self.registry.register(
                Tool(
                    name,
                    tool["tool_description"],
                    agent_name,
                    self._handler(
                        name, agent_name, tool.get("skip_automatic_tool_registration", False)
                    ),
                    {
                        "type": "object",
                        "properties": properties,
                        "required": list(properties),
                        "additionalProperties": False,
                    },
                    {},
                    read_only=tool["tool_type"] == "query",
                    permissions=frozenset({"agentarch.mock"}),
                )
            )
        self.registry.register(
            Tool(
                "finish",
                "Return the final response after completing the workflow",
                "finish",
                self._finish,
                {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                    "additionalProperties": False,
                },
                {"type": "object"},
                read_only=True,
                permissions=frozenset({"agentarch.mock"}),
            )
        )

    def _record(self, name: str, agent: str, arguments: dict) -> None:
        self._history.append(
            {
                "agent": agent,
                "content": {
                    "tool_call_id": f"orqen-{len(self._history)}",
                    "tool_name": name,
                    "tool_args": deepcopy(arguments),
                },
            }
        )

    def _handler(self, name: str, agent: str, skipped: bool = False) -> Callable:
        async def call(**arguments: Any) -> Any:
            self._record(name, agent, arguments)
            if skipped:
                return f"{name} is not a valid tool"
            return deepcopy(self.dataset._mock[self.case_id].get(name, "Not found"))

        return call

    async def _finish(self, message: str) -> dict:
        self._record("finish", "single_agent", {"message": message})
        return {"message": message}

    def grade(self, official_run_metrics: Callable) -> dict:
        """Invoke the caller's upstream run_metrics, without leaking labels to planning.

        Supply the function from the pinned checkout in the upstream environment.
        Full histories remain in memory; this adapter does not persist raw data.
        """
        case = next(
            c
            for c in self.dataset._config["utterances_and_ground_truths"]
            if str(c["id"]) == self.case_id
        )
        return official_run_metrics(
            deepcopy(self.dataset._config),
            deepcopy(self._history),
            deepcopy(case["ground_truth"]),
            "single_agent",
            False,
        )
