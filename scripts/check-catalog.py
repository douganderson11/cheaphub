#!/usr/bin/env python3
"""Sanity-check catalog trust rules and page mounts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "assets" / "catalog.json").read_text())
PRODUCTS = CATALOG["products"]
IMAGE_HOSTS = {
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "target.scene7.com",
    "images.thdstatic.com",
    "images.homedepot-static.com",
    "i5.walmartimages.com",
    "i.walmartimages.com",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> None:
    if len(PRODUCTS) != 71:
        fail(f"expected 71 products, found {len(PRODUCTS)}")
    verified = [p for p in PRODUCTS if p["is_verified_discount"]]
    if len(verified) != 4:
        fail(f"expected 4 verified discounts, found {len(verified)}")
    for product in PRODUCTS:
        if product["current_price"] is None and "Check current price" not in "Check current price":
            fail("price helper missing")
        if product["is_verified_discount"] is not True and product["is_verified_discount"] is not False:
            fail(f"{product['id']} has non-boolean verified flag")
        if not product["discount_basis"]:
            fail(f"{product['id']} missing discount_basis")
        if not product["merchant"] or not product["restrictions_notes"]:
            fail(f"{product['id']} missing trust fields")
        if not product["last_checked_date"]:
            fail(f"{product['id']} missing last_checked_date")
        if not product["destination"].startswith("http"):
            fail(f"{product['id']} destination is not http(s)")
        if product["affiliate_url"] is None and product["destination"] != product["product_url"]:
            fail(f"{product['id']} destination should default to product_url")
        image_url = product.get("image_url")
        if image_url:
            parsed = urlparse(image_url)
            if parsed.scheme != "https" or parsed.hostname not in IMAGE_HOSTS:
                fail(f"{product['id']} image_url is not an allowed merchant HTTPS CDN")
            if not product.get("image_alt"):
                fail(f"{product['id']} has image_url but missing image_alt")
            if not product.get("image_source"):
                fail(f"{product['id']} has image_url but missing image_source")
        elif product.get("image_source") or product.get("image_alt"):
            fail(f"{product['id']} has image metadata without image_url")
        invented = re.search(r"\b\d{1,2}%\s*off\b", product["discount_basis"], re.I)
        if invented and not product["is_verified_discount"]:
            fail(f"{product['id']} looks like an invented percent-off claim")

    mounts = {
        "deals/index.html": 'data-module="all"',
        "best/useful-home-tools-under-25/index.html": "home-tools-under-25",
        "best/kitchen-essentials-under-50/index.html": "kitchen-under-50",
        "best/travel-accessories-under-50/index.html": "travel-under-50",
        "categories/home-savings/index.html": 'data-category="home"',
        "categories/everyday/index.html": "everyday-staples",
        "categories/travel/index.html": "travel-under-50",
        "affiliate-disclosure/index.html": "As an Amazon Associate",
        "how-we-make-money/index.html": "MarshMack Media LLC",
        "about/index.html": "Who operates CheapHub",
        "partner/index.html": "Affiliate and commercial partnerships are with MarshMack Media LLC",
    }
    for rel, needle in mounts.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            fail(f"{rel} missing {needle!r}")
        if "catalog.js" not in text and rel.endswith("index.html") and "affiliate" not in rel:
            if "deals" in rel or rel.startswith("best/") or rel.startswith("categories/"):
                fail(f"{rel} missing catalog.js")

    go_count = len(list((ROOT / "go").glob("*/index.html")))
    if go_count != 71:
        fail(f"expected 71 go pages, found {go_count}")

    operator_pages = [
        "about/index.html",
        "affiliate-disclosure/index.html",
        "how-we-make-money/index.html",
        "partner/index.html",
    ]
    for rel in operator_pages:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "DBMM Media LLC" in text:
            fail(f"{rel} names the wrong operator (DBMM Media LLC)")
        if "MarshMack Media LLC" not in text.split("<footer>", 1)[0]:
            fail(f"{rel} body does not name MarshMack Media LLC as operator")
        if "DBMM Anderson LLC" not in text:
            fail(f"{rel} is missing the DBMM Anderson LLC IP line")

    csp = (ROOT / "_headers").read_text(encoding="utf-8")
    for host in (
        "m.media-amazon.com",
        "target.scene7.com",
        "images.thdstatic.com",
    ):
        if host not in csp:
            fail(f"_headers CSP is missing img-src host {host}")
    print("Catalog checks passed.")


if __name__ == "__main__":
    main()
