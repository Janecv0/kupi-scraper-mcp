import os
import secrets
import unicodedata
from csv import DictReader
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

API_KEY_ENV_VAR = "KUPI_MCP_API_KEY"
API_KEY_HEADER_ENV_VAR = "KUPI_MCP_API_KEY_HEADER"
DATA_DIR_ENV_VAR = "KUPI_MCP_DATA_DIR"
PRODUCTS_DIR_ENV_VAR = "KUPI_MCP_PRODUCTS_DIR"
SALES_FILE_ENV_VAR = "KUPI_MCP_SALES_FILE"


def _resolve_project_root() -> Path:
    configured_data_dir = os.environ.get(DATA_DIR_ENV_VAR, "").strip()
    if configured_data_dir:
        return Path(configured_data_dir).expanduser()

    module_root = Path(__file__).resolve().parents[2]
    cwd_root = Path.cwd()
    cwd_repo_child = cwd_root / "kupi-scraper-mcp"
    candidates = [module_root, cwd_root, cwd_repo_child]

    for candidate in candidates:
        if (candidate / "slevy_all.csv").is_file() and (candidate / "produkty").is_dir():
            return candidate

    for candidate in candidates:
        if (candidate / "slevy_all.csv").is_file() or (candidate / "produkty").is_dir():
            return candidate

    return cwd_root


PROJECT_ROOT = _resolve_project_root()
PRODUCTS_DIR = Path(
    os.environ.get(PRODUCTS_DIR_ENV_VAR, str(PROJECT_ROOT / "produkty"))
).expanduser()
SALES_FILE = Path(
    os.environ.get(SALES_FILE_ENV_VAR, str(PROJECT_ROOT / "slevy_all.csv"))
).expanduser()

mcp = FastMCP(
    name="kupi-scraper-mcp",
    instructions="MCP server exposing product and sale data from local CSV files.",
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Simple API key middleware for HTTP transports."""

    def __init__(
        self,
        app: Any,
        api_key: str,
        header_name: str = "x-api-key",
        exempt_paths: Optional[list[str]] = None,
    ):
        super().__init__(app)
        self.api_key = api_key
        self.header_name = header_name.lower().strip() or "x-api-key"
        self.exempt_paths = exempt_paths or []

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_path = request.url.path
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        for exempt in self.exempt_paths:
            normalized_exempt = exempt.rstrip("/")
            if request_path == normalized_exempt or request_path.startswith(f"{normalized_exempt}/"):
                return await call_next(request)

        provided_key = request.headers.get(self.header_name)
        if not provided_key:
            return JSONResponse(
                {"error": f"Missing API key header: {self.header_name}"},
                status_code=401,
            )

        if not secrets.compare_digest(provided_key, self.api_key):
            return JSONResponse({"error": "Invalid API key."}, status_code=403)

        return await call_next(request)


def get_api_key() -> str:
    return os.environ.get(API_KEY_ENV_VAR, "").strip()


def get_api_key_header_name() -> str:
    return os.environ.get(API_KEY_HEADER_ENV_VAR, "x-api-key").strip() or "x-api-key"


def resolve_host_port() -> tuple[str, int]:
    host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
    raw_port = os.environ.get("PORT") or os.environ.get("FASTMCP_PORT") or "8000"
    return host, int(raw_port)


def _configure_runtime_settings() -> tuple[str, int]:
    host, port = resolve_host_port()
    if hasattr(mcp, "settings"):
        mcp.settings.host = host
        mcp.settings.port = port

        # Keep Railway hostnames allowed when transport security is enabled.
        public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
        private_domain = os.environ.get("RAILWAY_PRIVATE_DOMAIN", "")
        if hasattr(mcp.settings, "transport_security"):
            allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
            if public_domain:
                allowed_hosts.append(public_domain)
            if private_domain:
                allowed_hosts.append(private_domain)
            mcp.settings.transport_security.allowed_hosts = allowed_hosts

    return host, port


def _build_streamable_http_app() -> Any:
    if hasattr(mcp, "streamable_http_app"):
        try:
            return mcp.streamable_http_app()
        except TypeError:
            return mcp.streamable_http_app(path="/mcp")

    if hasattr(mcp, "http_app"):
        try:
            return mcp.http_app(transport="streamable-http")
        except TypeError:
            return mcp.http_app()

    raise RuntimeError("FastMCP version does not expose streamable HTTP app builder.")


def _build_sse_app() -> Any:
    if hasattr(mcp, "http_app"):
        try:
            return mcp.http_app(transport="sse")
        except TypeError:
            pass

    if hasattr(mcp, "sse_app"):
        try:
            return mcp.sse_app(path="/sse")
        except TypeError:
            return mcp.sse_app()

    raise RuntimeError("FastMCP version does not expose SSE app builder.")


def build_streamable_http_asgi_app(
    api_key: Optional[str] = None,
    api_key_header: Optional[str] = None,
) -> Any:
    app = _build_streamable_http_app()
    resolved_api_key = api_key if api_key is not None else get_api_key()
    resolved_api_key = resolved_api_key.strip()
    resolved_header = (api_key_header or get_api_key_header_name()).strip() or "x-api-key"

    if resolved_api_key:
        app.add_middleware(
            APIKeyMiddleware,
            api_key=resolved_api_key,
            header_name=resolved_header,
            exempt_paths=["/health", "/healthz"],
        )

    return app


def build_sse_asgi_app(
    api_key: Optional[str] = None,
    api_key_header: Optional[str] = None,
) -> Any:
    app = _build_sse_app()
    resolved_api_key = api_key if api_key is not None else get_api_key()
    resolved_api_key = resolved_api_key.strip()
    resolved_header = (api_key_header or get_api_key_header_name()).strip() or "x-api-key"

    if resolved_api_key:
        app.add_middleware(
            APIKeyMiddleware,
            api_key=resolved_api_key,
            header_name=resolved_header,
            exempt_paths=["/health", "/healthz"],
        )

    return app


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _payload(tool_name: str, input_echo: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "dummy": False,
        "timestamp": _utc_timestamp(),
        "input": input_echo,
        "data": data,
    }


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}. "
            f"Set {DATA_DIR_ENV_VAR}, {SALES_FILE_ENV_VAR}, or {PRODUCTS_DIR_ENV_VAR} "
            "to point to your data directory/files."
        )

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = DictReader(csv_file, delimiter=";")
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized_row: dict[str, str] = {}
            for key, value in row.items():
                if key is None:
                    continue
                normalized_row[str(key).strip()] = (value or "").strip()
            rows.append(normalized_row)
        return rows


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    no_diacritics = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_diacritics.lower().strip()


def _filter_sales_rows(
    query: Optional[str] = None,
    field: str = "name",
) -> list[dict[str, str]]:
    sales_rows = _read_csv_rows(SALES_FILE)
    cleaned_query = (query or "").strip()

    if not cleaned_query:
        return sales_rows

    normalized_query = _normalize_text(cleaned_query)
    return [
        row
        for row in sales_rows
        if normalized_query in _normalize_text(row.get(field, ""))
    ]


def _serialize_sales_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "name": row.get("name", ""),
            "shop": row.get("shop", ""),
            "price": row.get("price", ""),
            "amount": row.get("amount", ""),
            "validity": row.get("validity", ""),
        }
        for row in rows
    ]


def _get_category_files() -> list[Path]:
    files = sorted(PRODUCTS_DIR.glob("*.csv"), key=lambda p: p.stem)
    if not files:
        raise FileNotFoundError(
            f"No category CSV files found in: {PRODUCTS_DIR}. "
            f"Set {DATA_DIR_ENV_VAR} or {PRODUCTS_DIR_ENV_VAR} to the directory with produkty/*.csv."
        )
    return files


def _load_products_from_categories(categories: Optional[set[str]] = None) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for csv_file in _get_category_files():
        source_category = csv_file.stem
        if categories is not None and source_category not in categories:
            continue

        for row in _read_csv_rows(csv_file):
            name = row.get("name", "")
            manufacturer = row.get("manufacturer", "")
            category = row.get("category") or None

            dedupe_key = (
                _normalize_text(source_category),
                _normalize_text(name),
                _normalize_text(manufacturer),
                _normalize_text(category or ""),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            products.append(
                {
                    "name": name,
                    "manufacturer": manufacturer,
                    "source_category": source_category,
                    "category": category,
                }
            )

    products.sort(
        key=lambda item: (
            item["source_category"],
            _normalize_text(item["name"]),
            _normalize_text(item["manufacturer"]),
            _normalize_text(item["category"] or ""),
        )
    )
    return products


def _resolve_categories(categories: list[str]) -> set[str]:
    available_categories = [path.stem for path in _get_category_files()]
    available_map = {_normalize_text(category): category for category in available_categories}

    requested: set[str] = set()
    unknown_categories: list[str] = []
    for value in categories:
        normalized = _normalize_text(value)
        matched = available_map.get(normalized)
        if matched is None:
            unknown_categories.append(value)
            continue
        requested.add(matched)

    if unknown_categories:
        available_text = ", ".join(sorted(available_categories))
        unknown_text = ", ".join(unknown_categories)
        raise ValueError(f"Unknown categories: {unknown_text}. Allowed categories: {available_text}.")

    return requested


@mcp.tool()
def get_categories() -> dict[str, Any]:
    """Return all category names and product counts per category file."""
    category_counts: dict[str, int] = {}
    for csv_file in _get_category_files():
        category_counts[csv_file.stem] = len(_read_csv_rows(csv_file))

    categories = sorted(category_counts.keys())
    data = {
        "total_categories": len(categories),
        "categories": categories,
        "counts_by_category": {category: category_counts[category] for category in categories},
    }
    return _payload("get_categories", input_echo={}, data=data)


@mcp.tool()
def get_all_products() -> dict[str, Any]:
    """Return deduplicated products from all category files."""
    products = _load_products_from_categories()
    data = {
        "total_products": len(products),
        "products": products,
    }
    return _payload("get_all_products", input_echo={}, data=data)


@mcp.tool()
def get_products_by_categories(categories: list[str]) -> dict[str, Any]:
    """Return deduplicated products filtered by source categories."""
    requested_categories = _resolve_categories(categories)
    products = _load_products_from_categories(categories=requested_categories)
    sorted_requested = sorted(requested_categories)

    data = {
        "categories": sorted_requested,
        "total_products": len(products),
        "products": products,
    }
    return _payload(
        "get_products_by_categories",
        input_echo={"categories": categories},
        data=data,
    )


@mcp.tool()
def get_sales(query: Optional[str] = None) -> dict[str, Any]:
    """Return all sales or filter by partial case/accent-insensitive product name."""
    sales = _serialize_sales_rows(_filter_sales_rows(query=query, field="name"))

    data = {
        "query": query,
        "total_sales": len(sales),
        "sales": sales,
    }
    return _payload("get_sales", input_echo={"query": query}, data=data)


@mcp.tool()
def get_sales_by_retailer(query: Optional[str] = None) -> dict[str, Any]:
    """Return all sales or filter by partial case/accent-insensitive retailer/shop name."""
    sales = _serialize_sales_rows(_filter_sales_rows(query=query, field="shop"))

    data = {
        "query": query,
        "total_sales": len(sales),
        "sales": sales,
    }
    return _payload("get_sales_by_retailer", input_echo={"query": query}, data=data)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "kupi-scraper-mcp", "dummy": True})


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "kupi-scraper-mcp", "dummy": True})


@mcp.custom_route("/sales/by-retailer", methods=["GET"])
async def sales_by_retailer(request: Request) -> JSONResponse:
    query = request.query_params.get("query")
    payload = get_sales_by_retailer(query=query)
    return JSONResponse(payload)


def run_streamable_http() -> None:
    host, port = _configure_runtime_settings()
    api_key = get_api_key()

    if api_key:
        import uvicorn

        asgi_app = build_streamable_http_asgi_app(api_key=api_key)
        uvicorn.run(asgi_app, host=host, port=port)
        return

    mcp.run(transport="streamable-http")


def run_sse() -> None:
    host, port = _configure_runtime_settings()
    api_key = get_api_key()

    if api_key:
        import uvicorn

        asgi_app = build_sse_asgi_app(api_key=api_key)
        uvicorn.run(asgi_app, host=host, port=port)
        return

    mcp.run(transport="sse")


def run_stdio() -> None:
    mcp.run(transport="stdio")
