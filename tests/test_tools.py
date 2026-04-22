from kupi_scraper_mcp.server import (
    DUMMY_TIMESTAMP,
    get_all_data,
    get_all_data_per_week,
    get_availiable_data_brand,
    get_availiable_data_product,
)


def assert_common_payload(payload: dict, tool_name: str, expected_input: dict) -> None:
    assert payload["tool"] == tool_name
    assert payload["dummy"] is True
    assert payload["timestamp"] == DUMMY_TIMESTAMP
    assert payload["input"] == expected_input
    assert isinstance(payload["data"], dict)


def test_get_all_data_payload_shape() -> None:
    payload = get_all_data()
    assert_common_payload(payload, "get_all_data", {})
    assert payload["data"]["total_items"] == 3
    assert len(payload["data"]["items"]) == 3


def test_get_all_data_per_week_echo_and_data() -> None:
    payload = get_all_data_per_week("2026-W17")
    assert_common_payload(payload, "get_all_data_per_week", {"week": "2026-W17"})
    assert payload["data"]["week"] == "2026-W17"
    assert payload["data"]["total_items"] == 2


def test_get_availiable_data_brand_payload_shape() -> None:
    payload = get_availiable_data_brand()
    assert_common_payload(payload, "get_availiable_data_brand", {})
    assert payload["data"]["total_brands"] == 3
    assert "Mattoni" in payload["data"]["brands"]


def test_get_availiable_data_product_without_brand() -> None:
    payload = get_availiable_data_product()
    assert_common_payload(payload, "get_availiable_data_product", {"brand": None})
    assert payload["data"]["brand"] is None
    assert payload["data"]["total_products"] >= 1


def test_get_availiable_data_product_with_brand() -> None:
    payload = get_availiable_data_product("Kupi")
    assert_common_payload(payload, "get_availiable_data_product", {"brand": "Kupi"})
    assert payload["data"]["brand"] == "Kupi"
    assert payload["data"]["products"] == ["Water", "Sparkling Water"]
