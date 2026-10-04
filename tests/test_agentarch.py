import asyncio
import os
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("yaml")

from orqen.agentarch import USE_CASES, AgentArchDataset


def test_rejects_unknown_usecase_before_touching_files(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        AgentArchDataset(tmp_path, "../escape")


@pytest.mark.skipif(
    not os.getenv("ORQEN_AGENTARCH_CHECKOUT"), reason="Pinned checkout not configured"
)
@pytest.mark.parametrize("use_case, count", [(USE_CASES[0], 60), (USE_CASES[1], 50)])
def test_pinned_dataset_tools_and_grader_bridge(use_case, count):
    dataset = AgentArchDataset(Path(os.environ["ORQEN_AGENTARCH_CHECKOUT"]), use_case)
    assert len(dataset.cases()) == count
    assert all(set(case) == {"id", "goal"} for case in dataset.cases())
    session = dataset.session("1")
    assert "ground_truth" not in session.instructions
    calls = []

    def grader(config, history, truth, mode, thinking):
        calls.append((history, truth, mode, thinking))
        return {"compatibility_only": True}

    asyncio.run(session.registry.get("finish").handler(message="Request rejected"))
    assert session.grade(grader)["compatibility_only"]
    assert calls[0][0][0]["content"]["tool_name"] == "finish"
    assert calls[0][2:] == ("single_agent", False)
    assert all(tool.permissions == frozenset({"agentarch.mock"}) for tool in session.registry.all())
    if use_case == USE_CASES[0]:
        output = asyncio.run(session.registry.get("get_employee_id").handler(employee_name="test"))
        assert output == "Employee1234"


def test_unpinned_repository_is_rejected(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    with pytest.raises(ValueError, match="pinned revision"):
        AgentArchDataset(tmp_path, USE_CASES[0])
