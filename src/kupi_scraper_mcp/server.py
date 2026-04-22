import os
import secrets
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

API_KEY_ENV_VAR = "KUPI_MCP_API_KEY"
API_KEY_HEADER_ENV_VAR = "KUPI_MCP_API_KEY_HEADER"
DUMMY_TIMESTAMP = "2026-01-01T00:00:00Z"

mcp = FastMCP(
    name="kupi-scraper-mcp",
    instructions=(
        "Dummy scraper MCP server bootstrap. "
        "Replace tool internals with real scraping logic in the next iteration."
    ),
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


def _dummy_payload(tool_name: str, input_echo: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "dummy": True,
        "timestamp": DUMMY_TIMESTAMP,
        "input": input_echo,
        "data": data,
    }


@mcp.tool()
def get_all_data() -> dict[str, Any]:
    """Return a deterministic dummy dataset for full data retrieval."""
    data = {
        "total_items": 3,
        "items": [
            {"brand": "Kupi", "product": "Water", "week": "2026-W01", "price": 1.99},
            {"brand": "Kupi", "product": "Sparkling Water", "week": "2026-W01", "price": 2.49},
            {"brand": "Mattoni", "product": "Mineral Water", "week": "2026-W01", "price": 2.29},
        ],
    }
    return _dummy_payload("get_all_data", input_echo={}, data=data)


@mcp.tool()
def get_all_data_per_week(week: str) -> dict[str, Any]:
    """Return a deterministic dummy dataset filtered by week."""
    data = {
        "week": week,
        "total_items": 2,
        "items": [
            {"brand": "Kupi", "product": "Water", "week": week, "price": 1.99},
            {"brand": "Mattoni", "product": "Mineral Water", "week": week, "price": 2.29},
        ],
    }
    return _dummy_payload("get_all_data_per_week", input_echo={"week": week}, data=data)


@mcp.tool()
def get_availiable_data_brand() -> dict[str, Any]:
    """Return deterministic dummy list of available brands."""
    data = {
        "total_brands": 3,
        "brands": ["Kupi", "Mattoni", "Dobra Voda"],
    }
    return _dummy_payload("get_availiable_data_brand", input_echo={}, data=data)


@mcp.tool()
def get_availiable_data_product(brand: Optional[str] = None) -> dict[str, Any]:
    """Return deterministic dummy list of products, optionally filtered by brand."""
    all_products = {
        "Kupi": ["Water", "Sparkling Water"],
        "Mattoni": ["Mineral Water", "Flavored Water"],
        "Dobra Voda": ["Still Water"],
    }

    if brand:
        products = all_products.get(brand, [])
        data = {
            "brand": brand,
            "total_products": len(products),
            "products": products,
        }
    else:
        merged = sorted({product for items in all_products.values() for product in items})
        data = {
            "brand": None,
            "total_products": len(merged),
            "products": merged,
        }

    return _dummy_payload(
        "get_availiable_data_product",
        input_echo={"brand": brand},
        data=data,
    )


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "kupi-scraper-mcp", "dummy": True})


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "kupi-scraper-mcp", "dummy": True})


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
