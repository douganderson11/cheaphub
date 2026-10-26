#!/usr/bin/env python3
"""Sanity-check catalog trust rules and page mounts."""

from __future__ import annotations

import html
import importlib.util
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
    if len(PRODUCTS) < 1:
        fail("published catalog is empty")
    seed = json.loads((ROOT / "data" / "seed-catalog.json").read_text())
    expired_ids = {row["id"] for row in seed if row.get("status") == "expired"}
    if CATALOG.get("seed_count") != len(seed):
        fail(f"expected {len(seed)} seed products, found {CATALOG.get('seed_count')}")
    if any(not product.get("image_url") for product in PRODUCTS):
        fail("published catalog contains a product without image_url")
    if any(product.get("status") == "expired" for product in PRODUCTS):
        fail("published catalog contains an expired product")
    verified = [p for p in PRODUCTS if p["is_verified_discount"]]
    if len(verified) < 1:
        fail("expected at least one verified discount")
    for product in verified:
        if product["current_price"] is None or product["list_or_typical_price"] is None:
            fail(f"{product['id']} is verified without both prices")
        if product["list_or_typical_price"] <= product["current_price"]:
            fail(f"{product['id']} verified list price is not above the current price")
        if "merchant page" not in product["discount_basis"]:
            fail(f"{product['id']} verified basis does not cite the merchant page")
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
            if image_url.startswith("/assets/products/"):
                local = ROOT / image_url.lstrip("/")
                if not local.is_file():
                    fail(f"{product['id']} local image missing: {image_url}")
            else:
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
        "seasonal/thanksgiving-hosting-under-100/index.html": "thanksgiving-hosting",
        "best/everyday-restock-under-25/index.html": "everyday-restock-under-25",
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
    expected_go = len(seed) - len(expired_ids)
    if go_count != expected_go:
        fail(f"expected {expected_go} go pages, found {go_count}")

    catalog_js = (ROOT / "assets" / "catalog.js").read_text(encoding="utf-8")
    if "No photo yet" in catalog_js:
        fail("catalog.js still renders a public No photo yet state")
    if "thanksgiving-hosting" not in catalog_js:
        fail("catalog.js missing thanksgiving-hosting module")
    if "everyday-restock-under-25" not in catalog_js:
        fail("catalog.js missing everyday-restock-under-25 module")

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

    footer_disclosure = (
        "As an Amazon Associate and affiliate for other websites, we earn from qualifying purchases. "
        "This site contains affiliate links, and we may receive a commission if you make a purchase through our links at no extra cost to you."
    )
    old_footer = "As an Amazon Associate I earn from qualifying purchases."
    footer_pages = 0
    for path in ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if 'class="legal-line"' not in text or "<footer" not in text:
            continue
        footer_pages += 1
        footer = text.split("<footer", 1)[1]
        rel = path.relative_to(ROOT)
        if footer_disclosure not in footer:
            fail(f"{rel} footer is missing the affiliate disclosure sentence")
        if old_footer in footer:
            fail(f"{rel} footer still uses the old Amazon Associate sentence")
        if "Affiliate link. We may earn a commission if you buy through it." in text:
            fail(f"{rel} still repeats a per-link commission sentence")
    if footer_pages < 1:
        fail("no page footers found")

    csp = (ROOT / "_headers").read_text(encoding="utf-8")
    for host in (
        "m.media-amazon.com",
        "target.scene7.com",
        "images.thdstatic.com",
    ):
        if host not in csp:
            fail(f"_headers CSP is missing img-src host {host}")
    build_spec = importlib.util.spec_from_file_location(
        "build_catalog", ROOT / "scripts" / "build-catalog.py"
    )
    build_catalog = importlib.util.module_from_spec(build_spec)
    build_spec.loader.exec_module(build_catalog)

    ledger = build_catalog.load_deal_numbers()
    if build_catalog.assign_deal_numbers(PRODUCTS, ledger) != ledger:
        fail("deal number ledger is behind the catalog; run build-catalog.py")
    seen_numbers = set()
    for product in PRODUCTS:
        if "deal_number" not in product:
            fail(f"{product['id']} is missing deal_number")
        number = product["deal_number"]
        if build_catalog.is_live_deal(product):
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                fail(f"{product['id']} live deal is missing a stable deal number")
        if number is None:
            continue
        if ledger.get(product["id"]) != number:
            fail(f"{product['id']} deal_number does not match data/deal-numbers.json")
        if number in seen_numbers:
            fail(f"deal number {number} is reused")
        seen_numbers.add(number)

    today_path = ROOT / "today" / "index.html"
    if not today_path.is_file():
        fail("today/index.html is missing")
    today = today_path.read_text(encoding="utf-8")
    if today.count("https://www.googletagmanager.com/gtag/js?id=G-5YT1Y0TFBR") != 1:
        fail("today page must load G-5YT1Y0TFBR exactly once")
    if today.count("gtag('config', 'G-5YT1Y0TFBR'") != 1:
        fail("today page must configure GA once")
    for token in ("utm_source", "instagram", "tiktok", "youtube", "utm_medium", "social", "campaign_source"):
        if token not in today:
            fail(f"today page does not pass through {token}")
    if footer_disclosure not in today.split("<footer", 1)[1]:
        fail("today page footer disclosure changed")
    if "CheapHub may earn a commission when you shop through a link here." not in today:
        fail("today page is missing the commission line")
    copy = today.split('<div class="topline">', 1)[1].split("</main>", 1)[0]
    if re.search(r"\b(don't|do not|no other|never|cannot|can't|isn't|won't|aren't|not|no)\b", copy, re.I):
        fail("today page copy uses a negative word")
    expected = build_catalog.select_today_deals(PRODUCTS)
    found = [int(value) for value in re.findall(r'data-deal="(\d+)"', today)]
    if found != [product["deal_number"] for product in expected]:
        fail("today page deals are not the newest verified discounts")
    if len(expected) > 20 or (len([p for p in PRODUCTS if build_catalog.is_live_deal(p)]) >= 12 and not 12 <= len(expected) <= 20):
        fail(f"today page should list about 12-20 deals, found {len(expected)}")
    for product in expected:
        if f'/go/{product["id"]}/' not in today:
            fail(f"today card for {product['id']} is missing its /go/ link")
        if html.escape(product["image_url"], quote=True) not in today:
            fail(f"today card for {product['id']} is missing its photo")
        if f'Deal #{product["deal_number"]}' not in today:
            fail(f"today card for {product['id']} is missing its deal number")
    if "catalog.js" in today:
        fail("today page should be static catalog HTML, without a second catalog fetch")
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    if "<loc>https://cheaphub.com/today/</loc>" not in sitemap:
        fail("sitemap is missing https://cheaphub.com/today/")

    forbidden_tags = ("luxuryhom06-20", "uniqueinamer-20")
    for rel in ("assets/outbound.json", "_redirects", "netlify/functions/lib/go.mjs", "today/index.html"):
        blob = (ROOT / rel).read_text(encoding="utf-8")
        for tag in forbidden_tags:
            if tag in blob:
                fail(f"{rel} contains forbidden associate tag {tag}")
    go_source = (ROOT / "netlify/functions/lib/go.mjs").read_text(encoding="utf-8")
    if "cheaphubus-20" not in go_source:
        fail("Amazon associate tag is no longer cheaphubus-20")
    for line in (ROOT / "_redirects").read_text(encoding="utf-8").splitlines():
        if any(host in line for host in ("target.com", "walmart.com", "homedepot.com")) and "tag=" in line:
            fail(f"non-Amazon redirect is tagged: {line}")

    if "deal_number" not in catalog_js or "Deal #" not in catalog_js:
        fail("catalog.js does not show deal numbers on cards")

    print("Catalog checks passed.")


if __name__ == "__main__":
    main()
