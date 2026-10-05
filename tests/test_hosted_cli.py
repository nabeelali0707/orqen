import json
import sys

import httpx
import pytest

from orqen.cli import main


@pytest.mark.parametrize("provider", ["mistral", "openrouter"])
@pytest.mark.parametrize("explicit_dry", [False, True])
def test_preview_never_opens_client_or_writes_report(
    provider, explicit_dry, tmp_path, monkeypatch, capsys
):
    key = "isolated-cli-test-key"
    name = "MISTRAL_API_KEY" if provider == "mistral" else "OPENROUTER_API_KEY"
    monkeypatch.delenv(name, raising=False)
    path = tmp_path / ".env"
    path.write_text(f"{name}={key}\n", encoding="utf-8")
    output = tmp_path / "report.json"

    def forbidden(*args, **kwargs):
        raise AssertionError("Preview opened an HTTP client")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    args = [
        "orqen",
        "demo-hosted",
        "--provider",
        provider,
        "--model",
        "test",
        "--env-file",
        str(path),
        "--output",
        str(output),
    ]
    if explicit_dry:
        args.append("--dry-run")
    monkeypatch.setattr(sys, "argv", args)
    main()
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["dry_run"] and document["network_requests"] == 0
    assert document["credential_configured"] and not output.exists()
    assert key not in captured.out + captured.err


def test_explicit_live_without_credentials_fails_before_http(monkeypatch, capsys):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setattr(
        sys, "argv", ["orqen", "demo-hosted", "--provider", "mistral", "--model", "test", "--live"]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "credential is missing" in capsys.readouterr().err


def test_preview_invalid_settings_has_safe_error(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["orqen", "demo-hosted", "--provider", "mistral", "--model", "test", "--timeout", "0"],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "Invalid hosted provider settings" in capsys.readouterr().err
