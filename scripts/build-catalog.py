#!/usr/bin/env python3
"""Normalize the seed catalog and generate outbound /go/ artifacts."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
GO = ROOT / "go"

RESEARCH_DATE = "2026-09-19"
STATIC_REDIRECTS = [
    "/best-under/ /best/ 301",
    "/disclosure/ /affiliate-disclosure/ 301",
    "/home/ /home-savings/ 301",
]

PRIORITY_IDS = [
    "tinkr-home-essentials-kit-target",
    "rubbermaid-brilliance-glass-8cup-target",
    "packit-freezable-lunch-bag-gray-fog-target",
    "oxo-good-grips-kitchen-scissors-amazon",
    "oxo-good-grips-swivel-peeler-amazon",
    "lodge-8in-cast-iron-skillet-amazon",
    "stanley-fatmax-25ft-tape-homedepot",
    "black-decker-led-under-cabinet-2bar-homedepot",
    "amazon-basics-microfiber-cloths-24pk",
    "scotch-brite-heavy-duty-sponges-3ct-target",
    "amazon-basics-hdmi-cable-6ft",
    "anker-powercore-10000-amazon",
    "cabeau-evolution-classic-travel-pillow-target",
    "eagle-creek-pack-it-original-set-xs-s-m-amazon",
    "travelon-rfid-anti-theft-mini-shoulder-target",
    "clorox-fresh-scent-wipes-75ct-target",
    "pyrex-3pc-measuring-cup-set-amazon",
    "microplane-premium-classic-zester-target",
    "room-essentials-storage-crate-target",
    "hart-2-position-ratcheting-screwdriver-walmart",
]

CATEGORY_LABELS = {
    "home": "Home Savings",
    "everyday": "Everyday Shopping",
    "travel": "Travel",
}

TOPIC_LABELS = {
    "home": "Home",
    "everyday": "Everyday",
    "travel": "Travel",
}


IMAGE_HOSTS = {
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "target.scene7.com",
    "images.thdstatic.com",
    "images.homedepot-static.com",
    "i5.walmartimages.com",
    "i.walmartimages.com",
}

LOCAL_IMAGE_PREFIX = "/assets/products/"


def require_https(url: str, field: str, product_id: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{product_id}: {field} is not an absolute http(s) URL: {url!r}")
    return url


def normalize_image_url(row: dict, product_id: str) -> str | None:
    url = row.get("image_url")
    if url in (None, "", False):
        return None
    if not isinstance(url, str):
        raise ValueError(f"{product_id}: image_url must be a URL string or null")
    if url.startswith(LOCAL_IMAGE_PREFIX):
        local = ROOT / url.lstrip("/")
        if not local.is_file():
            raise ValueError(f"{product_id}: local image missing at {url}")
        return url
    parsed = urlparse(require_https(url, "image_url", product_id))
    host = parsed.hostname or ""
    if host not in IMAGE_HOSTS:
        raise ValueError(f"{product_id}: image_url host {host!r} is not an allowed merchant CDN")
    return url


def load_overrides() -> dict[str, str]:
    raw = json.loads((DATA / "affiliate-overrides.json").read_text())
    if not isinstance(raw, dict):
        raise ValueError("affiliate-overrides.json must be an object of id → url")
    cleaned: dict[str, str] = {}
    for key, value in raw.items():
        if value in (None, "", False):
            continue
        if not isinstance(value, str):
            raise ValueError(f"Override for {key} must be a URL string or empty")
        cleaned[key] = require_https(value, "affiliate_url", key)
    return cleaned


def normalize_product(row: dict, index: int, overrides: dict[str, str]) -> dict:
    product_id = row["id"]
    product_url = require_https(row["product_url"], "product_url", product_id)
    image_url = normalize_image_url(row, product_id)
    affiliate_url = overrides.get(product_id)
    destination = affiliate_url or product_url
    last_checked = row.get("last_checked_date") or RESEARCH_DATE
    datetime.strptime(last_checked, "%Y-%m-%d")
    priority_rank = PRIORITY_IDS.index(product_id) + 1 if product_id in PRIORITY_IDS else None
    return {
        "id": product_id,
        "title": row["title"],
        "category": row["category"],
        "category_label": CATEGORY_LABELS[row["category"]],
        "topic": TOPIC_LABELS[row["category"]],
        "subcategory": row["subcategory"],
        "short_pitch": row["short_pitch"],
        "merchant": row["merchant"],
        "product_url": product_url,
        "affiliate_url": affiliate_url,
        "destination": destination,
        "uses_affiliate_url": bool(affiliate_url),
        "list_or_typical_price": row.get("list_or_typical_price"),
        "current_price": row.get("current_price"),
        "discount_basis": row["discount_basis"],
        "is_verified_discount": bool(row.get("is_verified_discount")),
        "currency": row.get("currency") or "USD",
        "ceiling_bucket": row["ceiling_bucket"],
        "restrictions_notes": row["restrictions_notes"],
        "last_checked_date": last_checked,
        "suggested_affiliate_network": row.get("suggested_affiliate_network") or "pending",
        "image_url": image_url,
        "image_alt": row.get("image_alt") or (row["title"] if image_url else None),
        "image_source": row.get("image_source") or None,
        "status": row.get("status") or "draft",
        "priority_rank": priority_rank,
        "sort_index": index,
    }


def write_go_page(product: dict) -> None:
    dest = html.escape(product["destination"], quote=True)
    title = html.escape(product["title"])
    merchant = html.escape(product["merchant"])
    product_id = html.escape(product["id"])
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Continue to {merchant} | CheapHub</title>
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="refresh" content="0;url={dest}">
<link rel="canonical" href="https://cheaphub.com/go/{product_id}/">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/styles.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<main id="main" class="wrap page-intro">
<p class="eyebrow">Outbound link</p>
<h1>Continue to {merchant}</h1>
<p class="lede">{title}</p>
<p><a class="button" href="{dest}" rel="sponsored noopener noreferrer">See at {merchant}</a></p>
<p>This may be an affiliate link. MarshMack Media LLC, which operates CheapHub, may earn a commission if you buy through it, at no extra cost to you.</p>
<p><a class="text-link" href="/affiliate-disclosure/">Affiliate disclosure</a></p>
</main>
</body>
</html>
"""
    target = GO / product_id / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")


def existing_search_items() -> list[dict]:
    items = json.loads((ASSETS / "search-index.json").read_text())
    return [item for item in items if item.get("type") != "Product"]


def exclusion_reason(row: dict) -> str:
    url = row.get("product_url") or ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if "/s" == path or path.startswith("/s/") or "search?" in url or "/search" in path:
        return "unlocked_search_or_category_url"
    if parsed.path.startswith("/c/") or "/-/N-" in parsed.path:
        return "unlocked_search_or_category_url"
    if not row.get("image_url"):
        return row.get("image_exclusion_reason") or "no_verified_merchant_photo"
    return "no_verified_merchant_photo"


def main() -> None:
    seed = json.loads((DATA / "seed-catalog.json").read_text())
    overrides = load_overrides()
    products = [normalize_product(row, index, overrides) for index, row in enumerate(seed)]
    unknown_overrides = sorted(set(overrides) - {product["id"] for product in products})
    if unknown_overrides:
        raise ValueError(f"Unknown affiliate override ids: {unknown_overrides}")

    published = [product for product in products if product["image_url"]]
    excluded = []
    seed_by_id = {row["id"]: row for row in seed}
    for product in products:
        if product["image_url"]:
            continue
        row = seed_by_id[product["id"]]
        excluded.append(
            {
                "id": product["id"],
                "title": product["title"],
                "merchant": product["merchant"],
                "product_url": product["product_url"],
                "reason": exclusion_reason(row),
                "status": "draft_excluded_pending_photo",
            }
        )
    (DATA / "excluded-pending-photo.json").write_text(
        json.dumps(
            {
                "policy": "Do not list a product without a photo. These seed rows stay in draft until a verified merchant image is attached.",
                "count": len(excluded),
                "products": excluded,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    catalog = {
        "generated_from": "data/seed-catalog.json",
        "research_date": RESEARCH_DATE,
        "seed_count": len(products),
        "count": len(published),
        "excluded_pending_photo_count": len(excluded),
        "verified_discount_count": sum(1 for product in published if product["is_verified_discount"]),
        "products": published,
    }
    (ASSETS / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    outbound = {
        product["id"]: {
            "destination": product["destination"],
            "product_url": product["product_url"],
            "affiliate_url": product["affiliate_url"],
            "merchant": product["merchant"],
            "title": product["title"],
        }
        for product in products
    }
    (ASSETS / "outbound.json").write_text(json.dumps(outbound, indent=2) + "\n", encoding="utf-8")

    if GO.exists():
        for leftover in GO.glob("*/index.html"):
            leftover.unlink()
            leftover.parent.rmdir()
    GO.mkdir(exist_ok=True)

    redirect_lines = list(STATIC_REDIRECTS)
    for product in products:
        dest = product["destination"]
        product_id = product["id"]
        redirect_lines.append(f"/go/{product_id} {dest} 302")
        redirect_lines.append(f"/go/{product_id}/ {dest} 302")
        write_go_page(product)
    (ROOT / "_redirects").write_text("\n".join(redirect_lines) + "\n", encoding="utf-8")

    search_items = existing_search_items()
    for product in published:
        search_items.append(
            {
                "title": product["title"],
                "summary": f"{product['short_pitch']} Sold at {product['merchant']}.",
                "url": f"/deals/#{product['id']}",
                "type": "Product",
                "topic": product["topic"],
            }
        )
    (ASSETS / "search-index.json").write_text(json.dumps(search_items, indent=2) + "\n", encoding="utf-8")

    verified = [product["id"] for product in published if product["is_verified_discount"]]
    print(
        f"Published {len(published)} products with photos "
        f"({len(verified)} verified discounts). "
        f"Excluded {len(excluded)} pending photo. Seed rows {len(products)}."
    )
    print(f"Go pages: {len(list(GO.glob('*/index.html')))}")
    print(f"Redirects: {len(redirect_lines)}")


if __name__ == "__main__":
    main()
