#!/usr/bin/env python3
"""Resolve merchant product-image URLs for the seed catalog.

Hotlinks official retailer CDNs (Amazon media, Target Scene7, Home Depot
thdstatic, Walmart images, brand sites). Does not invent SKUs: search and
category URLs stay image-less. Bot-walled PDPs stay image-less unless a
merchant CDN URL was already verified from that listing.
"""

from __future__ import annotations

import csv
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed-catalog.json"
CSV_PATH = ROOT / "data" / "seed-catalog.csv"
REPORT = ROOT / "data" / "product-image-report.json"
LOCKS = ROOT / "data" / "product-image-locks.json"

CTX = ssl.create_default_context()
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

ALLOWED_HOSTS = {
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "target.scene7.com",
    "images.thdstatic.com",
    "images.homedepot-static.com",
    "i5.walmartimages.com",
    "i.walmartimages.com",
}

# Live HD HTML is Akamai-walled; these CDN URLs were taken from Wayback
# snapshots of the same Home Depot PDPs and then HEAD-verified live.
WAYBACK_VERIFIED_HD = {
    "stanley-fatmax-25ft-tape-homedepot": (
        "https://images.thdstatic.com/productImages/"
        "df5797b7-07fb-46c8-919c-64a2662fdc81/svn/"
        "stanley-tape-measures-33-725y-64_600.jpg"
    ),
    "dewalt-tough-tape-25ft-homedepot": (
        "https://images.thdstatic.com/productImages/"
        "bda3cdea-0d21-49a2-8b01-40e720988513/svn/"
        "dewalt-tape-measures-dwht36925s-64_600.jpg"
    ),
}

ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)")
TCIN_RE = re.compile(r"/A-(\d{8,10})(?:[/?]|$)")
HD_ITEM_RE = re.compile(r"homedepot\.com/p/[^/]+/(\d{8,10})")
WALMART_IP_RE = re.compile(r"walmart\.com/ip/[^/]+/(\d+)")
HIRES_RE = re.compile(r'"hiRes"\s*:\s*"(https://m\.media-amazon\.com/images/I/[^"]+)"')
TARGET_GUEST_RE = re.compile(
    r"https://target\.scene7\.com/is/image/Target/GUEST_[0-9a-fA-F-]+"
)
HD_IMG_RE = re.compile(
    r"https://images\.(?:thdstatic|homedepot-static)\.com/productImages/"
    r"[0-9a-fA-F-]+/svn/[^\"'\\s]+?\.(?:jpg|jpeg|png|webp)"
)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
    re.I,
)
WALMART_IMG_RE = re.compile(r"https://i5\.walmartimages\.com/[^\"'\\s]+")


def request(url: str, timeout: int = 20, n: int = 0, accept: str = "*/*") -> tuple[int, str, bytes]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as response:
            body = response.read(n) if n else response.read()
            return response.status, response.getheader("Content-Type") or "", body
    except urllib.error.HTTPError as exc:
        body = exc.read(n or 4000) if exc.fp else b""
        return exc.code, exc.headers.get("Content-Type") if exc.headers else "", body


def is_search_or_category(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if "/s" == path or path.startswith("/s/") or "search?" in url or "/search" in path:
        return True
    if parsed.path.startswith("/c/") or "/-/N-" in parsed.path:
        return True
    return False


def allowed_image_url(url: str) -> bool:
    if url.startswith("/assets/products/"):
        return (ROOT / url.lstrip("/")).is_file()
    host = urlparse(url).hostname or ""
    if host not in ALLOWED_HOSTS and not host.endswith(".oxo.com"):
        return False
    if host.endswith(".oxo.com") and not any(
        token in url.lower() for token in (".jpg", ".jpeg", ".png", ".webp", "/media/", "/catalog/")
    ):
        return False
    return url.startswith("https://")


def card_sized_amazon(url: str) -> str:
    return re.sub(r"\._AC_[^.]+\.", "._AC_SL500_.", url)


def card_sized_hd(url: str) -> str:
    return re.sub(r"_\d+\.(jpg|jpeg|png|webp)$", r"_600.\1", url, flags=re.I)


def verify_image(url: str) -> bool:
    if not allowed_image_url(url):
        return False
    if url.startswith("/assets/products/"):
        return True
    try:
        status, ctype, body = request(url, timeout=15, n=64, accept="image/*,*/*;q=0.8")
    except Exception:
        return False
    if status != 200:
        return False
    ctype = (ctype or "").split(";")[0].strip().lower()
    if not ctype.startswith("image/"):
        return False
    if ctype == "image/gif" and len(body) < 200:
        return False
    if body.startswith(b"GIF89a") and len(body) < 200:
        return False
    return True


def amazon_p_image(asin: str) -> str:
    return f"https://m.media-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"


def load_locks() -> dict:
    if not LOCKS.exists():
        return {}
    raw = json.loads(LOCKS.read_text())
    return raw if isinstance(raw, dict) else {}


def extract_amazon(html: str) -> str | None:
    matches = HIRES_RE.findall(html)
    for url in matches:
        url = url.replace("\\u002F", "/")
        if "/images/I/" in url and url.lower().endswith((".jpg", ".jpeg", ".png")):
            return card_sized_amazon(url)
    return None


def extract_target(html: str) -> str | None:
    # First GUEST_ URL on a Target page is often nav/taxonomy art (e.g. "New
    # Arrivals"). Only the product Open Graph image is listing-specific.
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if title and re.search(r"undefined", title.group(1), re.I):
        return None
    og = OG_IMAGE_RE.findall(html) + OG_IMAGE_RE2.findall(html)
    for url in og:
        url = url.replace("&amp;", "&").split("?")[0]
        if re.search(r"target\.scene7\.com/is/image/Target/GUEST_[0-9a-fA-F-]+$", url):
            return f"{url}?wid=600&hei=600&qlt=85"
    return None


def extract_homedepot(html: str) -> str | None:
    og = OG_IMAGE_RE.findall(html) + OG_IMAGE_RE2.findall(html)
    for url in og:
        url = url.replace("&amp;", "&")
        if "productImages" in url:
            return card_sized_hd(url)
    matches = HD_IMG_RE.findall(html)
    if matches:
        return card_sized_hd(matches[0])
    return None


def extract_walmart(html: str) -> str | None:
    og = OG_IMAGE_RE.findall(html) + OG_IMAGE_RE2.findall(html)
    for url in og:
        url = url.replace("&amp;", "&")
        if "walmartimages.com" in url:
            return url
    matches = WALMART_IMG_RE.findall(html)
    for url in matches:
        if "/seo/" in url or "/asr/" in url:
            return url.split("?")[0]
    return None


def extract_generic(html: str) -> str | None:
    og = OG_IMAGE_RE.findall(html) + OG_IMAGE_RE2.findall(html)
    for url in og:
        url = url.replace("&amp;", "&")
        if allowed_image_url(url) or urlparse(url).hostname and urlparse(url).hostname.endswith(".oxo.com"):
            return url
    return None


def source_for_url(url: str) -> str:
    if url.startswith("/assets/products/"):
        name = url.rsplit("/", 1)[-1]
        if name.startswith("klein"):
            return "klein"
        if name.startswith("milwaukee"):
            return "milwaukee"
        if name.startswith("channellock"):
            return "channellock"
        return "local"
    host = urlparse(url).hostname or ""
    if "amazon" in host:
        return "amazon"
    if "target.scene7.com" in host:
        return "target"
    if "thdstatic" in host or "homedepot" in host:
        return "homedepot"
    if "walmartimages" in host:
        return "walmart"
    if "oxo.com" in host:
        return "oxo"
    return host


def resolve_product(product: dict, locks: dict | None = None) -> dict:
    product_id = product["id"]
    merchant = product["merchant"]
    url = product["product_url"]
    locks = locks or {}
    result = {
        "id": product_id,
        "merchant": merchant,
        "image_url": None,
        "image_alt": None,
        "image_source": None,
        "status": "missing",
        "detail": "",
    }

    lock = locks.get(product_id)
    if lock and lock.get("image_url") and verify_image(lock["image_url"]):
        result["image_url"] = lock["image_url"]
        result["image_alt"] = product["title"]
        result["image_source"] = lock.get("image_source") or source_for_url(lock["image_url"])
        result["status"] = "ok"
        result["detail"] = lock.get("detail") or "verified lock"
        return result

    if is_search_or_category(url):
        result["status"] = "skipped_unlocked_url"
        result["detail"] = "product_url is a search or category page; SKU is not locked"
        return result

    html = ""
    try:
        status, ctype, body = request(url, timeout=22, n=1_200_000, accept="text/html,*/*;q=0.8")
        html = body.decode("utf-8", "replace") if body else ""
        if status != 200:
            result["detail"] = f"PDP HTTP {status}"
    except Exception as exc:
        result["detail"] = f"PDP fetch error: {exc}"

    candidate = None
    host = urlparse(url).hostname or ""
    asin_match = ASIN_RE.search(url)
    if "amazon.com" in host:
        candidate = extract_amazon(html)
        if not candidate and asin_match:
            p_url = amazon_p_image(asin_match.group(1))
            if verify_image(p_url):
                candidate = p_url
                result["detail"] = "Amazon PDP blocked or image-less; used verified P/ASIN main image"
    elif "target.com" in host:
        candidate = extract_target(html)
    elif "homedepot.com" in host:
        candidate = extract_homedepot(html) or WAYBACK_VERIFIED_HD.get(product_id)
        if candidate and product_id in WAYBACK_VERIFIED_HD and candidate == WAYBACK_VERIFIED_HD[product_id]:
            result["detail"] = "Home Depot PDP blocked; used Wayback-verified thdstatic CDN URL"
    elif "walmart.com" in host:
        candidate = extract_walmart(html)
    else:
        candidate = extract_generic(html)

    if not candidate and product_id in WAYBACK_VERIFIED_HD:
        candidate = WAYBACK_VERIFIED_HD[product_id]
        result["detail"] = "Home Depot PDP blocked; used Wayback-verified thdstatic CDN URL"

    if not candidate:
        result["status"] = "missing"
        if not result["detail"]:
            result["detail"] = "no merchant product image found on PDP"
        return result

    if verify_image(candidate):
        result["image_url"] = candidate
        result["image_alt"] = product["title"]
        result["image_source"] = source_for_url(candidate)
        result["status"] = "ok"
        return result

    result["status"] = "unverified"
    result["detail"] = f"candidate rejected by image check: {candidate}"
    return result


def write_csv(products: list[dict]) -> None:
    fields = [
        "id",
        "title",
        "category",
        "subcategory",
        "short_pitch",
        "merchant",
        "product_url",
        "list_or_typical_price",
        "current_price",
        "discount_basis",
        "is_verified_discount",
        "currency",
        "ceiling_bucket",
        "restrictions_notes",
        "last_checked_date",
        "suggested_affiliate_network",
        "image_notes",
        "image_url",
        "image_alt",
        "image_source",
        "status",
    ]

    def cell(value):
        if value is True:
            return "true"
        if value is False:
            return "false"
        if value is None:
            return ""
        return value

    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for product in products:
            writer.writerow({key: cell(product.get(key)) for key in fields})


def main() -> None:
    products = json.loads(SEED.read_text())
    locks = load_locks()
    reports = []
    for index, product in enumerate(products):
        lock = locks.get(product["id"])
        if lock:
            if lock.get("product_url"):
                product["product_url"] = lock["product_url"]
            if lock.get("merchant"):
                product["merchant"] = lock["merchant"]
            if lock.get("title"):
                product["title"] = lock["title"]
        report = resolve_product(product, locks)
        reports.append(report)
        product["image_url"] = report["image_url"]
        product["image_alt"] = report["image_alt"]
        product["image_source"] = report["image_source"]
        print(f"{index + 1:02d}/{len(products)} {report['status']:22} {product['id']} {report['detail'][:90]}")
        time.sleep(0.25)

    SEED.write_text(json.dumps(products, indent=2) + "\n", encoding="utf-8")
    write_csv(products)
    summary = {
        "ok": [r["id"] for r in reports if r["status"] == "ok"],
        "skipped_unlocked_url": [r["id"] for r in reports if r["status"] == "skipped_unlocked_url"],
        "missing": [r["id"] for r in reports if r["status"] in {"missing", "unverified"}],
        "reports": reports,
    }
    REPORT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        f"Images ok={len(summary['ok'])} "
        f"skipped={len(summary['skipped_unlocked_url'])} "
        f"missing={len(summary['missing'])}"
    )


if __name__ == "__main__":
    main()
