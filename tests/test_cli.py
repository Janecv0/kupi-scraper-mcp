from typer.testing import CliRunner

import kupi_scraper_mcp.__main__ as cli

runner = CliRunner()


def test_cli_streamable_http_command(monkeypatch) -> None:
    called = {"value": False}

    def fake_run() -> None:
        called["value"] = True

    monkeypatch.setattr(cli, "run_streamable_http", fake_run)
    result = runner.invoke(cli.app, ["streamable-http"])

    assert result.exit_code == 0
    assert called["value"] is True


def test_cli_sse_command(monkeypatch) -> None:
    called = {"value": False}

    def fake_run() -> None:
        called["value"] = True

    monkeypatch.setattr(cli, "run_sse", fake_run)
    result = runner.invoke(cli.app, ["sse"])

    assert result.exit_code == 0
    assert called["value"] is True


def test_cli_stdio_command(monkeypatch) -> None:
    called = {"value": False}

    def fake_run() -> None:
        called["value"] = True

    monkeypatch.setattr(cli, "run_stdio", fake_run)
    result = runner.invoke(cli.app, ["stdio"])

    assert result.exit_code == 0
    assert called["value"] is True


def test_cli_help_lists_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "streamable-http" in result.output
    assert "sse" in result.output
    assert "stdio" in result.output
