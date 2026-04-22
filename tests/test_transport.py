from starlette.testclient import TestClient

from kupi_scraper_mcp.server import build_streamable_http_asgi_app, resolve_host_port


def test_healthz_public_when_api_key_enabled() -> None:
    app = build_streamable_http_asgi_app(api_key="secret", api_key_header="x-api-key")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_mcp_rejects_missing_or_invalid_api_key() -> None:
    app = build_streamable_http_asgi_app(api_key="secret", api_key_header="x-api-key")
    client = TestClient(app, raise_server_exceptions=False)

    missing = client.get("/mcp")
    invalid = client.get("/mcp", headers={"x-api-key": "bad"})

    assert missing.status_code == 401
    assert invalid.status_code == 403


def test_mcp_accepts_valid_api_key() -> None:
    app = build_streamable_http_asgi_app(api_key="secret", api_key_header="x-api-key")
    client = TestClient(app, raise_server_exceptions=False)

    valid = client.get("/mcp", headers={"x-api-key": "secret"})
    assert valid.status_code not in {401, 403}


def test_sales_by_retailer_route_returns_filtered_sales() -> None:
    app = build_streamable_http_asgi_app()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/sales/by-retailer", params={"query": "Tesco"})

    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "get_sales_by_retailer"
    assert body["input"] == {"query": "Tesco"}
    assert body["data"]["total_sales"] > 0
    assert all("tesco" in item["shop"].lower() for item in body["data"]["sales"])


def test_port_resolution_uses_port_env_first(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("FASTMCP_PORT", "7777")

    _, port = resolve_host_port()
    assert port == 9001


def test_port_resolution_falls_back_to_fastmcp_port(monkeypatch) -> None:
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setenv("FASTMCP_PORT", "7777")

    _, port = resolve_host_port()
    assert port == 7777
