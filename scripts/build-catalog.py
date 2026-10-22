#!/usr/bin/env python3
"""Normalize the seed catalog and generate outbound /go/ artifacts."""

from __future__ import annotations

import html
import json
import subprocess
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
    "rubbermaid-brilliance-9-6cup-2pk-amazon",
    "rubbermaid-brilliance-tritan-5pk-amazon",
    "amazon-basics-mini-dutch-oven-2qt-amazon",
    "amazon-basics-oversize-bath-towel-2pk-amazon",
    "tsa-30ml-travel-dispenser-4pk-amazon",
    "amazon-basics-21in-hardside-carry-on-amazon",
    "european-type-c-plug-adapter-2pk-amazon",
    "amazon-basics-lr44-12pk-amazon",
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


def apply_amazon_tags(urls: list[str]) -> list[str]:
    """Append AMAZON_ASSOCIATE_TAG from the outbound helper. Other stores stay as written."""
    if not urls:
        return []
    script = ROOT / "netlify" / "functions" / "lib" / "go.mjs"
    result = subprocess.run(
        ["node", str(script), "tag-urls"],
        input=json.dumps(urls),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        detail = (result.stderr or result.stdout or "Could not apply the Amazon associate tag").strip()
        raise SystemExit(detail)
    tagged = json.loads(result.stdout)
    if not isinstance(tagged, list) or len(tagged) != len(urls):
        raise SystemExit("Amazon tag helper returned an unexpected result")
    return [str(url) for url in tagged]


# Website Titans Google Analytics. First child of <head> on every generated /go/ page.
GTAG_SNIPPET = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-5YT1Y0TFBR"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-5YT1Y0TFBR');
</script>
"""


def write_go_page(product: dict, destination: str) -> None:
    dest = html.escape(destination, quote=True)
    title = html.escape(product["title"])
    merchant = html.escape(product["merchant"])
    product_id = html.escape(product["id"])
    page = f"""<!doctype html>
<html lang="en">
<head>
{GTAG_SNIPPET}<meta charset="utf-8">
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


# Newest verified discounts on /today/. Kept inside 12–20 cards.
TODAY_DEAL_LIMIT = 16
DEAL_NUMBERS_PATH = DATA / "deal-numbers.json"
TODAY_SITEMAP_LOC = "https://cheaphub.com/today/"
FOOTER_DISCLOSURE = (
    "As an Amazon Associate and affiliate for other websites, we earn from qualifying purchases. "
    "This site contains affiliate links, and we may receive a commission if you make a purchase through our links at no extra cost to you."
)
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

# One Google tag per page. utm_source / utm_medium on the landing URL are passed
# into this single config call so Instagram, TikTok, and YouTube Shorts sessions
# stay measurable. Deal clicks send one event with the same values; they do not
# load a second tag and they do not add parameters to the merchant URL.
TODAY_GTAG_SNIPPET = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-5YT1Y0TFBR"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  (function () {
    var params = new URLSearchParams(location.search);
    var source = (params.get('utm_source') || '').toLowerCase();
    var medium = (params.get('utm_medium') || '').toLowerCase();
    var allowedSource = { instagram: true, tiktok: true, youtube: true };
    var fields = {};
    if (allowedSource[source]) fields.campaign_source = source;
    if (medium === 'social') fields.campaign_medium = medium;
    gtag('config', 'G-5YT1Y0TFBR', fields);
    document.addEventListener('click', function (event) {
      var link = event.target && event.target.closest ? event.target.closest('a') : null;
      if (!link || !link.closest) return;
      var card = link.closest('[data-deal]');
      if (!card) return;
      gtag('event', 'deal_click', {
        transport_type: 'beacon',
        deal_number: card.getAttribute('data-deal'),
        campaign_source: fields.campaign_source || '',
        campaign_medium: fields.campaign_medium || '',
        link_path: link.pathname || ''
      });
    });
  })();
</script>
"""


def is_live_deal(product: dict) -> bool:
    """A published verified discount with a photo and both merchant prices."""
    current = product.get("current_price")
    typical = product.get("list_or_typical_price")
    if current is None or typical is None:
        return False
    return bool(
        product.get("image_url")
        and product.get("status") != "expired"
        and product.get("is_verified_discount") is True
        and typical > current
    )


def load_deal_numbers() -> dict[str, int]:
    if not DEAL_NUMBERS_PATH.exists():
        return {}
    raw = json.loads(DEAL_NUMBERS_PATH.read_text(encoding="utf-8"))
    by_id = raw.get("by_id") if isinstance(raw, dict) else None
    if not isinstance(by_id, dict):
        raise SystemExit("data/deal-numbers.json must contain a by_id object")
    cleaned: dict[str, int] = {}
    for key, value in by_id.items():
        if not isinstance(key, str) or not key:
            raise SystemExit("deal number ids must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise SystemExit(f"deal number for {key} must be a positive integer")
        cleaned[key] = value
    if len(set(cleaned.values())) != len(cleaned):
        raise SystemExit("deal numbers must be unique and are never reused")
    return cleaned


def assign_deal_numbers(products: list[dict], existing: dict[str, int]) -> dict[str, int]:
    """Keep every existing id → number. New live deals take the next free integer."""
    assigned = dict(existing)
    used = set(assigned.values())
    if len(used) != len(assigned):
        raise SystemExit("deal numbers must be unique and are never reused")
    nxt = max(used, default=0) + 1
    newcomers = [product for product in products if is_live_deal(product) and product["id"] not in assigned]
    newcomers.sort(key=lambda product: (product["last_checked_date"], product.get("sort_index") or 0, product["id"]))
    for product in newcomers:
        while nxt in used:
            nxt += 1
        assigned[product["id"]] = nxt
        used.add(nxt)
        nxt += 1
    return assigned


def save_deal_numbers(assigned: dict[str, int]) -> None:
    if len(set(assigned.values())) != len(assigned):
        raise SystemExit("refusing to save reused deal numbers")
    ordered = dict(sorted(assigned.items(), key=lambda item: (item[1], item[0])))
    payload = {
        "note": (
            "Stable deal numbers for social captions. A product id keeps its number permanently. "
            "Ids that leave the catalog stay in this file so the number is never reused."
        ),
        "by_id": ordered,
    }
    DEAL_NUMBERS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def merchant_price_label(product: dict) -> str:
    basis = (product.get("discount_basis") or "").lower()
    if "typical price" in basis:
        return "Typical price"
    if "regular price" in basis or " reg " in f" {basis} ":
        return "Regular price"
    return "List price"


def format_money(value: float) -> str:
    return f"${value:,.2f}"


def format_checked(iso: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    return f"{MONTHS[month - 1]} {day}, {year}"


def render_today_card(product: dict, index: int) -> str:
    product_id = html.escape(product["id"], quote=True)
    title = html.escape(product["title"], quote=True)
    merchant = html.escape(product["merchant"], quote=True)
    topic = html.escape(product["topic"], quote=True)
    image_url = html.escape(product["image_url"], quote=True)
    alt = html.escape(product.get("image_alt") or product["title"], quote=True)
    number = int(product["deal_number"])
    href = f"/go/{product_id}/"
    label = html.escape(merchant_price_label(product), quote=True)
    typical = html.escape(format_money(product["list_or_typical_price"]), quote=True)
    current = html.escape(format_money(product["current_price"]), quote=True)
    checked = html.escape(format_checked(product["last_checked_date"]), quote=True)
    loading = "eager" if index < 2 else "lazy"
    priority = ' fetchpriority="high"' if index == 0 else ""
    return f"""<article class="offer-card today-card" id="deal-{number}" data-deal="{number}">
<a class="offer-media-link" href="{href}" rel="sponsored noopener noreferrer">
<div class="offer-media"><p class="deal-number">Deal #{number}</p><img src="{image_url}" alt="{alt}" width="400" height="400" loading="{loading}" decoding="async"{priority}></div>
</a>
<span class="kicker">{topic} · {merchant}</span>
<span class="verified-badge">Verified discount</span>
<h2><a href="{href}" rel="sponsored noopener noreferrer">{title}</a></h2>
<p class="offer-price">{current}</p>
<p class="offer-list">{label} on the merchant page {typical}</p>
<p class="checked">Checked {checked}</p>
<a class="button" href="{href}" rel="sponsored noopener noreferrer">See at {merchant}</a>
</article>
"""


def select_today_deals(products: list[dict], limit: int = TODAY_DEAL_LIMIT) -> list[dict]:
    eligible = [product for product in products if is_live_deal(product) and product.get("deal_number")]
    eligible.sort(
        key=lambda product: (
            product["last_checked_date"],
            product["deal_number"],
            product.get("sort_index") or 0,
        ),
        reverse=True,
    )
    return eligible[:limit]


def write_today_page(deals: list[dict]) -> None:
    if deals:
        cards = '<div class="offer-grid">\n' + "\n".join(
            render_today_card(product, index) for index, product in enumerate(deals)
        ) + "\n</div>"
    else:
        cards = '<p class="lede">Verified discounts from the catalog will appear here with their deal numbers.</p>'
    page = f"""<!doctype html>
<html lang="en">
<head>
{TODAY_GTAG_SNIPPET}<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Today's deals | CheapHub</title>
<meta name="description" content="The newest verified discounts from CheapHub. Each card shows its deal number, the current price, and the typical price from the merchant page.">
<link rel="canonical" href="https://cheaphub.com/today/">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/styles.css">
<meta name="theme-color" content="#142842">
</head>
<body class="today-page">
<a class="skip" href="#main">Skip to content</a>
<div class="topline">CheapHub may earn a commission when you shop through a link here.</div>
<header class="site-header">
<div class="header-inner">
<a class="brand" href="/" aria-label="CheapHub home">cheap<span>hub</span><i>.</i></a>
<button class="menu-toggle" aria-expanded="false" aria-controls="nav">Menu <span aria-hidden="true">☰</span></button>
<nav id="nav" aria-label="Primary">
<a href="/deals/">Best Deals</a>
<a href="/coupons/">Coupons</a>
<a href="/best/">Best Under</a>
<a href="/home-savings/">Home Savings</a>
<a href="/travel/">Travel</a>
<a href="/compare/">Compare</a>
<a href="/guides/">Guides</a>
</nav>
<a class="header-news" href="/newsletter/">Weekly Best Deals <span aria-hidden="true">↗</span></a>
</div>
</header>
<main id="main">
<section class="page-intro wrap">
<p class="eyebrow">Link in bio</p>
<h1>Today's deals</h1>
<p class="lede">The newest verified discounts, each with its deal number. A caption can say link in bio, deal #12, and that number is on the card.</p>
<p class="today-note">The current price sits with the typical price shown on the merchant page. The date is the day that page was checked.</p>
</section>
<section class="wrap section today-deals">
{cards}
<p class="today-more"><a class="text-link" href="/deals/">Browse the full catalog on Best Deals</a></p>
</section>
</main>
<footer>
<div class="footer-inner">
<div class="footer-brand"><a class="brand" href="/">cheap<span>hub</span><i>.</i></a><p>Find Better Deals. Spend Less.</p><p>Practical research for a smarter purchase.</p></div>
<div><h2>Explore</h2><a href="/find/">Find a price</a><a href="/deals/">Best Deals</a><a href="/coupons/">Coupons</a><a href="/stores/">Stores</a><a href="/best/">Best Under</a><a href="/categories/">Categories</a></div>
<div><h2>Learn</h2><a href="/guides/">Buying guides</a><a href="/compare/">Comparisons</a><a href="/seasonal/">Seasonal</a><a href="/newsletter/">Newsletter</a><a href="/methodology/">Our methodology</a></div>
<div><h2>CheapHub</h2><a href="/about/">About</a><a href="/partner/">Partner with us</a><a href="/contact/">Contact</a><a href="/how-we-make-money/">How we make money</a><a href="/affiliate-disclosure/">Affiliate disclosure</a></div>
<div><h2>Policies</h2><a href="/advertising-policy/">Advertising</a><a href="/corrections/">Corrections</a><a href="/accessibility/">Accessibility</a><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a></div>
</div>
<div class="legal-line">Copyright © 2026 CheapHub. Operated by <a href="https://www.marshmack.com">MarshMack Media LLC</a>. CheapHub.com and associated intellectual property are owned by DBMM Anderson LLC and licensed to MarshMack Media LLC. Developed and Designed by <a href="https://www.websitetitans.com">Website Titans</a>. {FOOTER_DISCLOSURE}</div>
</footer>
<script src="/assets/app.js" defer></script>
</body>
</html>
"""
    target = ROOT / "today" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")


def ensure_today_sitemap() -> None:
    path = ROOT / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    loc = f"<loc>{TODAY_SITEMAP_LOC}</loc>"
    if loc in text:
        return
    anchor = "<loc>https://cheaphub.com/deals/</loc></url>"
    if anchor not in text:
        raise SystemExit("sitemap.xml is missing the deals URL")
    path.write_text(text.replace(anchor, anchor + f"<url>{loc}</url>", 1), encoding="utf-8")


def exclusion_reason(row: dict) -> str:
    if row.get("image_exclusion_reason"):
        return row["image_exclusion_reason"]
    url = row.get("product_url") or ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if "/s" == path or path.startswith("/s/") or "search?" in url or "/search" in path:
        return "unlocked_search_or_category_url"
    if parsed.path.startswith("/c/") or "/-/N-" in parsed.path:
        return "unlocked_search_or_category_url"
    if not row.get("image_url"):
        return "no_verified_merchant_photo"
    return "no_verified_merchant_photo"


def main() -> None:
    seed = json.loads((DATA / "seed-catalog.json").read_text())
    overrides = load_overrides()
    products = [normalize_product(row, index, overrides) for index, row in enumerate(seed)]
    unknown_overrides = sorted(set(overrides) - {product["id"] for product in products})
    if unknown_overrides:
        raise ValueError(f"Unknown affiliate override ids: {unknown_overrides}")

    published = [
        product
        for product in products
        if product["image_url"] and product.get("status") != "expired"
    ]
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

    deal_numbers = assign_deal_numbers(published, load_deal_numbers())
    if assign_deal_numbers(published, deal_numbers) != deal_numbers:
        raise SystemExit("deal numbers changed on a second pass")
    save_deal_numbers(deal_numbers)
    for product in products:
        product["deal_number"] = deal_numbers.get(product["id"])

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

    live = [product for product in products if product.get("status") != "expired"]
    hops = {
        product["id"]: tagged
        for product, tagged in zip(live, apply_amazon_tags([product["destination"] for product in live]))
    }
    outbound = {
        product["id"]: {
            "destination": hops[product["id"]],
            "product_url": product["product_url"],
            "affiliate_url": product["affiliate_url"],
            "merchant": product["merchant"],
            "title": product["title"],
        }
        for product in live
    }
    (ASSETS / "outbound.json").write_text(json.dumps(outbound, indent=2) + "\n", encoding="utf-8")

    if GO.exists():
        for leftover in GO.glob("*/index.html"):
            leftover.unlink()
            leftover.parent.rmdir()
    GO.mkdir(exist_ok=True)

    redirect_lines = list(STATIC_REDIRECTS)
    for product in products:
        if product.get("status") == "expired":
            continue
        dest = hops[product["id"]]
        product_id = product["id"]
        redirect_lines.append(f"/go/{product_id} {dest} 302")
        redirect_lines.append(f"/go/{product_id}/ {dest} 302")
        write_go_page(product, dest)
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

    today = select_today_deals(published)
    write_today_page(today)
    ensure_today_sitemap()

    verified = [product["id"] for product in published if product["is_verified_discount"]]
    print(
        f"Today page: {len(today)} verified discounts. "
        f"Deal numbers assigned: {len(deal_numbers)}."
    )
    print(
        f"Published {len(published)} products with photos "
        f"({len(verified)} verified discounts). "
        f"Excluded {len(excluded)} pending photo. Seed rows {len(products)}."
    )
    print(f"Go pages: {len(list(GO.glob('*/index.html')))}")
    print(f"Redirects: {len(redirect_lines)}")


if __name__ == "__main__":
    main()
