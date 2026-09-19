#!/usr/bin/env python3
"""Inject catalog mounts, disclosure copy, and catalog.js into the static pages."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APP_SCRIPT = '<script src="/assets/app.js" defer></script>'
BOTH_SCRIPTS = APP_SCRIPT + '<script src="/assets/catalog.js" defer></script>'

CATALOG_NOTE = (
    "These buying criteria still apply. Seed products below are price-checked listings "
    "with merchant, basis, restrictions and a last-checked date. A verified-discount "
    "badge appears only when the merchant page itself showed a list-versus-sale price."
)

DISCLOSURE = (
    '<p class="catalog-disclosure">Disclosure: This page contains affiliate links. '
    "We may earn a commission if you buy through them, at no extra cost to you. "
    "We do not invent discount codes or percentages. "
    '<a href="/affiliate-disclosure/">Affiliate disclosure</a> · '
    '<a href="/how-we-make-money/">How we make money</a>.</p>'
)


def catalog_section(eyebrow: str, heading: str, module: str, extra: str = "") -> str:
    return (
        '<section class="wrap section catalog-section">'
        '<div class="section-head"><div>'
        f'<p class="eyebrow">{eyebrow}</p><h2>{heading}</h2>'
        "</div></div>"
        f"{DISCLOSURE}"
        f'<div data-catalog data-module="{module}"{extra}></div>'
        "</section>"
    )


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Could not find expected text in {path}")
    if text.count(old) != 1:
        raise SystemExit(f"Expected one match in {path}, found {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def add_catalog_script() -> None:
    for path in ROOT.rglob("*.html"):
        if "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if APP_SCRIPT in text and "catalog.js" not in text:
            path.write_text(text.replace(APP_SCRIPT, BOTH_SCRIPTS), encoding="utf-8")


def patch_homepage() -> None:
    path = ROOT / "index.html"
    replace_once(
        path,
        "<p>We are preparing a curated catalog. Until merchant terms and destinations have been checked, you will not see a made-up discount here.</p>",
        "<p>The seed catalog is live as a price-check desk. Merchant, basis, restrictions and last-checked dates sit on every card. A verified-discount badge appears only when the merchant page itself showed a list-versus-sale price.</p>",
    )
    replace_once(
        path,
        '<section class="feature-band wrap">',
        catalog_section(
            "Price-check desk",
            "Useful picks with honest terms",
            "priority",
            ' data-limit="8" data-more-href="/deals/"',
        )
        + '<section class="feature-band wrap">',
    )


def patch_deals() -> None:
    path = ROOT / "deals" / "index.html"
    replace_once(
        path,
        '<div class="status-panel"><span class="status-icon" aria-hidden="true">✓</span><div><h2>The verified catalog is being prepared</h2><p>There are no active offers to display yet. We are checking merchant terms and affiliate approvals before publishing prices or coupon codes.</p><p>Browse the guides below while the catalog is assembled.</p></div></div>',
        '<div class="status-panel"><span class="status-icon" aria-hidden="true">✓</span><div>'
        "<h2>A price-check catalog, not a coupon farm</h2>"
        "<p>These 71 products were researched on September 19, 2026. Four have a verified list-versus-sale price on the merchant page. The rest are shown as price checks or secondary signals—never as invented percent-off claims.</p>"
        "<p>Confirm the live merchant price, seller and restrictions before you buy. Affiliate approvals may still be pending; outbound links use a clean product URL until an affiliate URL is added.</p>"
        "</div></div>"
        + DISCLOSURE
        + '<div data-catalog data-module="all" data-filter="category"></div>',
    )
    replace_once(
        path,
        "A good deal should be useful, understandable and current. We publish merchant offers only after checking their terms and destination.",
        "A good deal should be useful, understandable and current. Every card shows the merchant, the price or a check-current-price note, the discount basis, restrictions and the last-checked date.",
    )


def patch_guide(rel: str, old_note: str, eyebrow: str, heading: str, module: str) -> None:
    path = ROOT / rel
    replace_once(path, old_note, CATALOG_NOTE)
    replace_once(
        path,
        '</article><section class="newsletter-strip">',
        "</article>" + catalog_section(eyebrow, heading, module) + '<section class="newsletter-strip">',
    )


def patch_category(rel: str, eyebrow: str, heading: str, module: str) -> None:
    path = ROOT / rel
    replace_once(
        path,
        '<section class="newsletter-strip">',
        catalog_section(eyebrow, heading, module) + '<section class="newsletter-strip">',
    )


def patch_stores() -> None:
    path = ROOT / "stores" / "index.html"
    replace_once(
        path,
        '<div class="status-panel"><div><h2>Store coverage is in review</h2><p>We will add merchant pages as approved programs and current offers become available. In the meantime, use the buying guides to compare total costs and terms.</p></div></div>',
        '<div class="status-panel"><div>'
        "<h2>Merchants in the seed catalog</h2>"
        "<p>Dedicated store pages will follow approved programs and licensed assets. Until then, filter Best Deals by merchant or use the listings below.</p>"
        "</div></div>"
        + DISCLOSURE
        + '<div data-catalog data-module="all" data-filter="merchant"></div>',
    )


def patch_methodology() -> None:
    path = ROOT / "methodology" / "index.html"
    replace_once(
        path,
        "<p>Before publishing, we review the merchant terms and record when they were checked. We remove or mark expired offers and correct material errors.</p>",
        "<p>Before publishing, we review the merchant terms and record when they were checked. We show the price or a check-current-price note, the discount basis and restrictions. A verified-discount badge is used only when a list-versus-sale (or equivalent) appeared on the merchant page itself. Secondary deal blogs are labeled as such and never presented as a verified sale. We remove or mark expired offers and correct material errors.</p>",
    )


def rewrite_policy_page(
    rel: str,
    title: str,
    description: str,
    canonical: str,
    eyebrow: str,
    heading: str,
    lede: str,
    sections: list[tuple[str, str]],
) -> None:
    import re

    path = ROOT / rel
    original = path.read_text(encoding="utf-8")
    header_end = original.find('<main id="main">')
    footer_start = original.find("</main>")
    if header_end == -1 or footer_start == -1:
        raise SystemExit(f"Could not split chrome for {path}")
    prefix = original[:header_end]
    suffix = original[footer_start:]
    prefix = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", prefix, count=1)
    prefix = re.sub(
        r'<meta name="description" content=".*?">',
        f'<meta name="description" content="{description}">',
        prefix,
        count=1,
    )
    prefix = re.sub(
        r'<link rel="canonical" href=".*?">',
        f'<link rel="canonical" href="{canonical}">',
        prefix,
        count=1,
    )
    body = [
        '<main id="main">',
        '<section class="page-intro wrap">',
        f'<p class="eyebrow">{eyebrow}</p>',
        f"<h1>{heading}</h1>",
        f'<p class="lede">{lede}</p>',
        "</section>",
        '<article class="wrap article compact"><div class="article-body">',
    ]
    for heading_text, paragraph in sections:
        body.append(f"<section><h2>{heading_text}</h2><p>{paragraph}</p></section>")
    body.append('<p class="article-meta">Updated September 2026</p>')
    body.append("</div></article>")
    path.write_text(prefix + "\n".join(body) + suffix, encoding="utf-8")


def patch_affiliate_disclosure() -> None:
    rewrite_policy_page(
        "affiliate-disclosure/index.html",
        "Affiliate disclosure | CheapHub",
        "Some links on CheapHub are affiliate links. We may earn a commission from qualifying purchases, at no extra cost to you.",
        "https://cheaphub.com/affiliate-disclosure/",
        "CheapHub",
        "Affiliate disclosure",
        "CheapHub is operated by MarshMack Media LLC. Some links on this site are affiliate links. If you click and purchase or complete a qualifying action, we may earn a commission at no additional cost to you.",
        [
            (
                "What an affiliate link is",
                "An affiliate link is a material connection: a partner or network may pay CheapHub when a reader follows the link and completes a qualifying action. That payment does not change the price you pay. The merchant controls the product, seller, inventory, shipping, returns and final checkout terms.",
            ),
            (
                "Where links go",
                "Product buttons use a centralized /go/ path. The destination is an optional affiliate URL when one has been approved and saved; otherwise it is the clean merchant product URL from the catalog. Until a network link is installed, you still leave CheapHub for the merchant page.",
            ),
            (
                "Amazon Associates",
                "As an Amazon Associate I earn from qualifying purchases. Amazon links are used inside editorial recommendations, not as a coupon farm.",
            ),
            (
                "How we describe offers",
                "We record the merchant, destination, current price or a check-current-price note, the discount basis, restrictions and the last-checked date. A verified-discount badge appears only when the merchant page itself showed a list-versus-sale price. We do not invent discount codes or percentages.",
            ),
            (
                "Near the links",
                "Pages with catalog cards include a short disclosure above the listings, and each card is labeled as an affiliate link. If a promotion has ended or stock is gone, treat the card as expired context—not a live sale.",
            ),
            (
                "No guarantee of availability",
                "A link may remain reachable after a merchant changes a price or promotion. Confirm the final price, seller, shipping and return terms before completing a transaction.",
            ),
        ],
    )


def patch_how_we_make_money() -> None:
    rewrite_policy_page(
        "how-we-make-money/index.html",
        "How CheapHub makes money | CheapHub",
        "CheapHub monetizes through disclosed affiliate partnerships. Commissions do not change the price you pay.",
        "https://cheaphub.com/how-we-make-money/",
        "CheapHub",
        "How CheapHub makes money",
        "CheapHub monetizes through disclosed affiliate partnerships. When a reader clicks a partner link and completes a qualifying action, we may earn a commission at no extra cost to the reader.",
        [
            (
                "Affiliate commissions",
                "We may earn from retailer and network partnerships (for example Amazon Associates and networks such as Impact, Awin or CJ Affiliate) when those programs are approved. We may also earn from verified coupons or promotions supplied through partner networks. Commission rates and cookie terms vary by partner and are not guaranteed.",
            ),
            (
                "What we do not do",
                "We do not sell fake discount codes, charge readers for coupons, run cashback-for-clicks incentives, or hide material connections. We do not invent percentages off. Some pages may include display advertising later; affiliate relationships remain disclosed.",
            ),
            (
                "Editorial separation",
                "Payment can influence which merchants are available to feature, but it does not make an unverified offer valid. Recommendations are based on usefulness and documented offer terms. Sponsored placement will be labeled.",
            ),
            (
                "Your price",
                "The merchant controls the final price, availability and checkout terms. Using a CheapHub link does not promise a lower price.",
            ),
            (
                "Affiliate reporting",
                "Networks may report transactions after a delay and may later reverse commissions for returns or ineligible orders. Revenue reporting is separate from real-time click counts.",
            ),
            (
                "Related pages",
                'See the <a href="/affiliate-disclosure/">affiliate disclosure</a> for link labeling and Amazon Associates language, and <a href="/methodology/">how we check offers</a> for verification rules.',
            ),
        ],
    )


def main() -> None:
    add_catalog_script()
    patch_homepage()
    patch_deals()
    note = "These are buying criteria, not live product recommendations. Specific products and prices will appear only after evidence and merchant terms have been checked."
    patch_guide(
        "best/useful-home-tools-under-25/index.html",
        note,
        "Price-check picks",
        "Home tools under $25",
        "home-tools-under-25",
    )
    patch_guide(
        "best/kitchen-essentials-under-50/index.html",
        note,
        "Price-check picks",
        "Kitchen essentials under $50",
        "kitchen-under-50",
    )
    patch_guide(
        "best/travel-accessories-under-50/index.html",
        note,
        "Price-check picks",
        "Travel accessories under $50",
        "travel-under-50",
    )
    patch_guide(
        "best/practical-gifts-under-25/index.html",
        note,
        "Price-check picks",
        "Practical items under $25",
        "practical-gifts-under-25",
    )
    patch_guide(
        "best/desk-upgrades-under-100/index.html",
        note,
        "Price-check picks",
        "Desk and cable basics",
        "desk-under-100",
    )
    patch_guide(
        "best/home-comfort-under-100/index.html",
        note,
        "Price-check picks",
        "Comfort and lighting basics",
        "home-comfort-under-100",
    )
    patch_category("categories/home-savings/index.html", "Catalog", "Home products in the seed set", "all")
    # category pages need a category filter, not all
    replace_once(
        ROOT / "categories" / "home-savings" / "index.html",
        'data-module="all"',
        'data-category="home"',
    )
    patch_category("categories/everyday/index.html", "Catalog", "Everyday products in the seed set", "everyday-staples")
    patch_category("categories/travel/index.html", "Catalog", "Travel products in the seed set", "travel-under-50")
    patch_category("home-savings/index.html", "Catalog", "Home products in the seed set", "all")
    replace_once(ROOT / "home-savings" / "index.html", 'data-module="all"', 'data-category="home"')
    patch_category("travel/index.html", "Catalog", "Travel products in the seed set", "travel-under-50")
    patch_stores()
    patch_methodology()
    patch_affiliate_disclosure()
    patch_how_we_make_money()
    print("Catalog page mounts applied.")


if __name__ == "__main__":
    main()
