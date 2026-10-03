import json
import subprocess
import sys

import pytest

from orqen.catalog_evaluation import default_dataset, evaluate_catalog


def test_full_catalog_has_full_coverage_but_greater_exposure():
    report = evaluate_catalog(default_dataset())
    assert len(report["rows"]) == 32
    assert report["summaries"]["all"]["complete_coverage_rate"] == 1
    assert report["summaries"]["all"]["mean_tools_offered"] == 12
    assert report["summaries"]["fixed_1"]["complete_coverage_rate"] < 1
    assert report["summaries"]["fixed_1"]["mean_tools_offered"] == 1
    assert "task success" in report["evidence"]


def test_adaptive_filter_can_drop_required_prerequisites():
    report = evaluate_catalog(default_dataset())
    row = next(
        row
        for row in report["rows"]
        if row["policy"] == "adaptive_3" and row["query"] == "paraphrase"
    )
    assert not row["complete_coverage"]
    assert "charge_find" in row["missing"] and "refund_create" in row["missing"]


def test_ground_truth_changes_grading_not_retrieval():
    dataset = default_dataset()
    before = evaluate_catalog(dataset)
    dataset["queries"][0]["required_tools"] = ["notification_send"]
    after = evaluate_catalog(dataset)
    assert [row["candidates"] for row in before["rows"]] == (
        [row["candidates"] for row in after["rows"]]
    )
    assert before["dataset_sha256"] != after["dataset_sha256"]


@pytest.mark.parametrize("defect", ["duplicate_tool", "duplicate_query", "missing_tool", "empty"])
def test_invalid_datasets_fail_explicitly(defect):
    dataset = default_dataset()
    if defect == "duplicate_tool":
        dataset["tools"].append(dataset["tools"][0])
    elif defect == "duplicate_query":
        dataset["queries"].append(dataset["queries"][0])
    elif defect == "missing_tool":
        dataset["queries"][0]["required_tools"] = ["nonexistent"]
    else:
        dataset["queries"] = []
    with pytest.raises(ValueError):
        evaluate_catalog(dataset)


def test_catalog_cli_loads_packaged_fixture(tmp_path):
    path = tmp_path / "report.json"
    completed = subprocess.run(
        [sys.executable, "-m", "orqen.cli", "evaluate-catalog", "--output", str(path)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert len(json.loads(path.read_text())["rows"]) == 32
