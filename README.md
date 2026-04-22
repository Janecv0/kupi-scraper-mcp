# kupi-scraper-mcp

Railway-ready MCP server exposing product and sales data from local CSV files.

Runtime target: Python `3.14.4`.

## Features

- FastMCP server with three transports: `streamable-http`, `sse`, and `stdio`.
- CSV-backed MCP tools:
  - `get_categories`
  - `get_all_products`
  - `get_products_by_categories`
  - `get_sales`
  - `get_sales_by_retailer`
- Optional API key auth for HTTP transports.
- Public health check endpoint at `/healthz`.
- Dockerfile optimized for Railway deployment.

## Data Sources

- Product category files: `produkty/*.csv`
- Sales file: `slevy_all.csv`
- CSV parsing: UTF-8 (`utf-8-sig`) with `;` delimiter.

## Tool Contract

All tool responses use this envelope:

```json
{
  "tool": "tool_name",
  "dummy": false,
  "timestamp": "ISO-8601 UTC",
  "input": {},
  "data": {}
}
```

### Tool Details

- `get_categories()`
  - Returns sorted category names (CSV filename stems) and product counts per category.
- `get_all_products()`
  - Returns deduplicated products from all category files.
  - Product fields: `name`, `manufacturer`, `source_category`, `category` (nullable).
- `get_products_by_categories(categories: list[str])`
  - Returns deduplicated products filtered by the selected file categories.
  - Raises a validation error for unknown categories and includes allowed values.
- `get_sales(query: str | None = None)`
  - Returns all sales rows from `slevy_all.csv` when query is empty.
  - When query is provided, filters by partial product-name match (case-insensitive and diacritic-insensitive).
  - Sales fields: `name`, `shop`, `price`, `amount`, `validity`.
- `get_sales_by_retailer(query: str | None = None)`
  - Returns all sales rows from `slevy_all.csv` when query is empty.
  - When query is provided, filters by partial retailer/shop match (case-insensitive and diacritic-insensitive).
  - Sales fields: `name`, `shop`, `price`, `amount`, `validity`.

## Project Layout

```text
src/kupi_scraper_mcp/
  __init__.py
  __main__.py
  server.py
tests/
  test_tools.py
  test_transport.py
  test_cli.py
produkty/
  *.csv
slevy_all.csv
Dockerfile
pyproject.toml
```

## Local Usage

Install in editable mode:

```bash
pip install -e .
```

Run streamable HTTP:

```bash
kupi-scraper-mcp streamable-http
```

Run SSE:

```bash
kupi-scraper-mcp sse
```

Run stdio:

```bash
kupi-scraper-mcp stdio
```

## Environment Variables

- `PORT`: main bind port (Railway-friendly, default `8000`)
- `FASTMCP_PORT`: fallback bind port when `PORT` is unset
- `FASTMCP_HOST`: bind host (default `0.0.0.0`)
- `KUPI_MCP_API_KEY`: optional API key to protect HTTP MCP endpoints
- `KUPI_MCP_API_KEY_HEADER`: API key header name (default `x-api-key`)
- `KUPI_MCP_DATA_DIR`: base directory containing `produkty/` and `slevy_all.csv`
- `KUPI_MCP_PRODUCTS_DIR`: override path for category CSV directory (defaults to `<data_dir>/produkty`)
- `KUPI_MCP_SALES_FILE`: override path for sales CSV file (defaults to `<data_dir>/slevy_all.csv`)

## Endpoints

Streamable HTTP mode:
- MCP endpoint: `/mcp`
- Retailer sales endpoint: `/sales/by-retailer?query=Tesco`
- Health endpoint: `/healthz`

SSE mode:
- SSE endpoint: `/sse`
- Retailer sales endpoint: `/sales/by-retailer?query=Tesco`
- Health endpoint: `/healthz`

`/healthz` is intentionally public even when API key auth is enabled.

## Railway Deployment (Dockerfile-first)

This repository includes a `Dockerfile` with default start command:

```text
kupi-scraper-mcp streamable-http
```

Railway should set `PORT` automatically. You can optionally set:

- `KUPI_MCP_API_KEY`
- `KUPI_MCP_API_KEY_HEADER`
- `KUPI_MCP_DATA_DIR` (or `KUPI_MCP_PRODUCTS_DIR` + `KUPI_MCP_SALES_FILE`)

Alternate Railway start command for SSE:

```text
kupi-scraper-mcp sse
```

## LibreChat MCP Config Examples

Streamable HTTP without auth:

```yaml
mcpServers:
  kupi-scraper:
    type: streamable-http
    url: https://your-railway-domain/mcp
```

Streamable HTTP with API key:

```yaml
mcpServers:
  kupi-scraper:
    type: streamable-http
    url: https://your-railway-domain/mcp
    headers:
      x-api-key: "${KUPI_MCP_API_KEY}"
```

SSE with API key:

```yaml
mcpServers:
  kupi-scraper:
    type: sse
    url: https://your-railway-domain/sse
    headers:
      x-api-key: "${KUPI_MCP_API_KEY}"
```

## Tests

Run tests:

```bash
pytest -q
```
