from csv import DictReader
from datetime import datetime
from pathlib import Path
import unicodedata

import pytest

from kupi_scraper_mcp.server import (
    PROJECT_ROOT,
    get_all_products,
    get_categories,
    get_products_by_categories,
    get_sales,
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    no_diacritics = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return no_diacritics.lower().strip()


def _assert_common_payload(payload: dict, tool_name: str, expected_input: dict) -> None:
    assert payload["tool"] == tool_name
    assert payload["dummy"] is False
    assert payload["input"] == expected_input
    assert isinstance(payload["data"], dict)

    timestamp = payload["timestamp"].replace("Z", "+00:00")
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None


def _read_sales_rows() -> list[dict[str, str]]:
    sales_path = Path(PROJECT_ROOT) / "slevy_all.csv"
    with sales_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = DictReader(csv_file, delimiter=";")
        return [dict(row) for row in reader]


def test_get_categories_returns_sorted_categories_and_counts() -> None:
    payload = get_categories()
    _assert_common_payload(payload, "get_categories", {})

    data = payload["data"]
    categories = data["categories"]
    counts = data["counts_by_category"]

    assert categories == sorted(categories)
    assert data["total_categories"] == len(categories)
    assert set(categories) == set(counts.keys())
    assert all(counts[category] > 0 for category in categories)
    assert {"vody", "sirupy", "limonady", "ledove_caje", "koly", "dzusy"}.issubset(set(categories))


def test_get_all_products_returns_deduplicated_full_product_objects() -> None:
    payload = get_all_products()
    _assert_common_payload(payload, "get_all_products", {})

    products = payload["data"]["products"]
    assert payload["data"]["total_products"] == len(products)
    assert len(products) > 0

    unique_keys = set()
    saw_optional_category = False
    for product in products:
        assert set(product.keys()) == {"name", "manufacturer", "source_category", "category"}
        if product["category"] is not None:
            saw_optional_category = True

        dedupe_key = (
            _normalize_text(product["source_category"]),
            _normalize_text(product["name"]),
            _normalize_text(product["manufacturer"]),
            _normalize_text(product["category"] or ""),
        )
        unique_keys.add(dedupe_key)

    assert len(unique_keys) == len(products)
    assert saw_optional_category is True


def test_get_products_by_categories_single_category_filter() -> None:
    payload = get_products_by_categories(["vody"])
    _assert_common_payload(payload, "get_products_by_categories", {"categories": ["vody"]})

    data = payload["data"]
    assert data["categories"] == ["vody"]
    assert data["total_products"] == len(data["products"])
    assert data["total_products"] > 0
    assert all(item["source_category"] == "vody" for item in data["products"])


def test_get_products_by_categories_multiple_category_filter() -> None:
    payload = get_products_by_categories(["vody", "sirupy"])
    _assert_common_payload(
        payload,
        "get_products_by_categories",
        {"categories": ["vody", "sirupy"]},
    )

    data = payload["data"]
    categories = {item["source_category"] for item in data["products"]}
    assert categories.issubset({"vody", "sirupy"})
    assert "vody" in categories
    assert "sirupy" in categories


def test_get_products_by_categories_invalid_category_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Unknown categories: neexistuje"):
        get_products_by_categories(["neexistuje"])


def test_get_sales_without_query_returns_all_sales() -> None:
    payload = get_sales()
    _assert_common_payload(payload, "get_sales", {"query": None})

    expected_count = len(_read_sales_rows())
    assert payload["data"]["total_sales"] == expected_count
    assert len(payload["data"]["sales"]) == expected_count


def test_get_sales_query_prirodni_matches_diacritics_insensitive() -> None:
    payload = get_sales("prirodni")
    _assert_common_payload(payload, "get_sales", {"query": "prirodni"})

    sales = payload["data"]["sales"]
    assert payload["data"]["total_sales"] == len(sales)
    assert len(sales) > 0
    assert all("prirodni" in _normalize_text(item["name"]) for item in sales)


def test_get_sales_query_coca_matches_case_insensitive() -> None:
    payload = get_sales("CoCa")
    _assert_common_payload(payload, "get_sales", {"query": "CoCa"})

    sales = payload["data"]["sales"]
    assert payload["data"]["total_sales"] == len(sales)
    assert len(sales) > 0
    assert all("coca" in _normalize_text(item["name"]) for item in sales)
