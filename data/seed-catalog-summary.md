# CheapHub Seed Catalog Summary

**Generated:** 2026-09-19 (CDT)  
**Files:** `seed-catalog.csv`, `seed-catalog.json`, `catalog-schema.md`  
**Product count:** 71 (target 60–80)

## Counts by category

| Category | Count | Site label |
|----------|------:|------------|
| home | 40 | Home Savings |
| everyday | 21 | Everyday Shopping |
| travel | 10 | Travel |

## Counts by ceiling bucket

| Bucket | Count |
|--------|------:|
| under_25 | 48 |
| under_50 | 21 |
| under_100 | 2 |
| other | 0 |

## Discount verification

| Status | Count |
|--------|------:|
| `is_verified_discount: true` (merchant-page list vs sale) | **4** |
| Price-check-only / secondary / null (not a verified sale claim) | **67** |
| Rows with a captured `current_price` | 61 |
| Rows with `current_price: null` (must re-price before live) | 10 |
| Rows sourced from secondary deal reports (Bob Vila Sep 2026) | 24 |

### Verified-discount products (merchant page)

- **TINKR Home Essentials Kit with Canvas Roll-up Case** — Target — $24.99 (list $29.99) — `tinkr-home-essentials-kit-target`
- **Rubbermaid Brilliance Glass 8-Cup Food Storage Container with Lid** — Target — $15.19 (list $16.99) — `rubbermaid-brilliance-glass-8cup-target`
- **Packit Freezable Lunch Bag (Gray Fog)** — Target — $20.99 (list $26.99) — `packit-freezable-lunch-bag-gray-fog-target`
- **Packit Freezable Lunch Bag (travel day-trip use)** — Target — $20.99 (list $26.99) — `packit-freezable-lunch-bag-travel-note`


## Merchant diversity

| Merchant | Count | Suggested network |
|----------|------:|-------------------|
| Amazon | 35 | amazon |
| Target | 19 | impact |
| Walmart | 12 | impact |
| Home Depot | 4 | impact |
| OXO | 1 | pending |


Amazon-heavy is expected for US long-tail SKUs; Target/Walmart/Home Depot provide Impact-friendly diversity if Amazon Associates is delayed.

## Recommended homepage modules

1. **Useful home tools under $25** — Pull `category=home`, `subcategory` in hand-tools/lighting/fasteners, `ceiling_bucket=under_25`. Lead with TINKR kit (verified sale) + Stanley FatMax + BLACK+DECKER LED bars; feature HART clearance only after Walmart PDP re-check.
2. **Kitchen essentials under $50** — `home` + kitchen-tools/cookware/food-storage. Lead with OXO shears/peeler, Lodge 8", Pyrex cups, Microplane, Rubbermaid Brilliance glass (verified sale).
3. **Travel accessories under $50** — `travel` slice: Cabeau pillow, Eagle Creek cubes, Travelon mini bag, luggage tags, Anker power bank (carry-on note).
4. **Everyday staples (price-check honesty)** — Microfiber cloths, Scotch-Brite, Clorox wipes, HDMI cable, batteries — frame as “fair everyday prices,” not fake % off.
5. **Trust strip** — Reuse site copy: confirm merchant, show basis, restrictions, last-checked date, expire when ended.

## First ~20 to publish (after PDP re-check)

Prioritize verified sales + evergreen staples with locked URLs and clear pitches. Re-verify every price on the merchant page the day of publish.

| # | id | Why first |
|---|----|-----------|
| 1 | `tinkr-home-essentials-kit-target` | home / Target — VERIFIED SALE |
| 2 | `rubbermaid-brilliance-glass-8cup-target` | home / Target — VERIFIED SALE |
| 3 | `packit-freezable-lunch-bag-gray-fog-target` | everyday / Target — VERIFIED SALE |
| 4 | `oxo-good-grips-kitchen-scissors-amazon` | home / Amazon — price check |
| 5 | `oxo-good-grips-swivel-peeler-amazon` | home / Amazon — price check |
| 6 | `lodge-8in-cast-iron-skillet-amazon` | home / Amazon — price check |
| 7 | `stanley-fatmax-25ft-tape-homedepot` | home / Home Depot — price check |
| 8 | `black-decker-led-under-cabinet-2bar-homedepot` | home / Home Depot — price check |
| 9 | `amazon-basics-microfiber-cloths-24pk` | everyday / Amazon — price check |
| 10 | `scotch-brite-heavy-duty-sponges-3ct-target` | everyday / Target — price check |
| 11 | `amazon-basics-hdmi-cable-6ft` | everyday / Amazon — price check |
| 12 | `anker-powercore-10000-amazon` | everyday / Amazon — price check |
| 13 | `cabeau-evolution-classic-travel-pillow-target` | travel / Target — price check |
| 14 | `eagle-creek-pack-it-original-set-xs-s-m-amazon` | travel / Amazon — price check |
| 15 | `travelon-rfid-anti-theft-mini-shoulder-target` | travel / Target — price check |
| 16 | `clorox-fresh-scent-wipes-75ct-target` | everyday / Target — price check |
| 17 | `pyrex-3pc-measuring-cup-set-amazon` | home / Amazon — price check |
| 18 | `microplane-premium-classic-zester-target` | home / Target — price check |
| 19 | `room-essentials-storage-crate-target` | everyday / Target — price check |
| 20 | `hart-2-position-ratcheting-screwdriver-walmart` | home / Walmart — price check |


## Research gaps / follow-ups

1. **Merchant page blocking:** Amazon, Target, Walmart, and Home Depot often return bot walls or JS shells to fetchers. Many prices come from search-index snippets or secondary deal coverage—**re-verify on a human browser session before `live`**.
2. **Search URLs:** Several Amazon/Walmart rows use search URLs until an exact ASIN/SKU is locked (especially HART clearance and Bob Vila–sourced tools).
3. **Secondary reports:** Bob Vila Walmart HART (2026-09-17) and Amazon hand-tool (2026-09-15) was/now figures are **not** marked `is_verified_discount`. Inventory is clearing; treat as draft signals.
4. **Null prices:** Anker 20W Nano, Swiffer WetJet, Amazon Basics packing cubes, Command hooks, Scotch Magic Tape, Threshold towel, Room Essentials towel set, DeWalt Tough Tape, Nalgene, TSA toiletry bag — capture live prices before publish.
5. **Cross-listed SKUs:** Packit and Anker PowerCore appear in Everyday and Travel intentionally for modules; CMS may dedupe by merchant SKU.
6. **Images:** Cards require a verified merchant/brand photo (`image_url`). Search/category URLs and bot-walled PDPs are omitted from the public catalog until a photo is locked. See `product-image-report.json` and `excluded-pending-photo.json`. Re-run `python3 scripts/fetch-product-images.py` then `python3 scripts/build-catalog.py` after locking SKUs.
7. **Affiliate:** Networks are suggestions only; no affiliate parameters in `product_url`.

## Quality bar reminder

CheapHub’s public promise: no made-up discounts. Prefer fewer live cards with honest price-check framing over a large catalog of stale % off claims.
