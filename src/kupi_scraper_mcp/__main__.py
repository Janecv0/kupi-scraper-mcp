import typer

from .server import run_sse, run_stdio, run_streamable_http

app = typer.Typer(help="Kupi Scraper MCP Server", add_completion=False)


@app.command("streamable-http")
def streamable_http() -> None:
    """Start server in streamable HTTP mode."""
    run_streamable_http()


@app.command()
def sse() -> None:
    """Start server in SSE mode."""
    run_sse()


@app.command()
def stdio() -> None:
    """Start server in stdio mode."""
    run_stdio()


if __name__ == "__main__":
    app()
