# CheapHub Seed Catalog Schema

Field definitions for the Netlify site / CMS ingest of `seed-catalog.csv` / `seed-catalog.json`.

## Product fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | string (slug) | yes | Stable unique key, kebab-case. Used as CMS ID and URL slug candidate. |
| `title` | string | yes | Merchant-facing product name (editorial shortening OK). |
| `category` | enum | yes | One of: `everyday`, `home`, `travel`. Maps to site nav (Everyday Shopping, Home Savings, Travel). |
| `subcategory` | string | yes | Free-text facet (e.g. `hand-tools`, `kitchen-tools`, `packing`). |
| `short_pitch` | string | yes | One editorial sentence. Useful/buying-advice tone; no hype or invented % off. |
| `merchant` | string | yes | Primary retailer name (Amazon, Target, Walmart, Home Depot, brand site, etc.). |
| `product_url` | string (URL) | yes | Canonical **non-affiliate** product or search URL. Replace search URLs with locked PDPs before publish. |
| `list_or_typical_price` | number or null | no | List / reg / typical comparison price in USD. Null if unknown. Never invent. |
| `current_price` | number or null | no | Observed current selling price in USD. Null if unverified. Never invent. |
| `discount_basis` | string | yes | Human-readable explanation of how price/discount was (or was not) established. |
| `is_verified_discount` | boolean | yes | `true` **only** when a clear list-vs-sale (or equivalent) was found on the **merchant page** itself. Secondary deal blogs → `false`. |
| `currency` | string | yes | Always `USD` for this seed set. |
| `ceiling_bucket` | enum | yes | `under_25` \| `under_50` \| `under_100` \| `other`. Derived from current (else list) price when known. |
| `restrictions_notes` | string | yes | Stock, SKU ambiguity, safety, battery rules, regional variance, etc. |
| `last_checked_date` | date (YYYY-MM-DD) | yes | Last research check. Seed pass used `2026-09-19`. |
| `suggested_affiliate_network` | enum | yes | `amazon` \| `impact` \| `shareasale` \| `cj` \| `pending`. Not live affiliate links. |
| `image_notes` | string | yes | Editorial note on the intended photo. Does not replace `image_url`. |
| `image_url` | string (URL) or null | no | Official merchant CDN URL for this listing’s product photo, or `null` when unverified. Never invent or substitute another SKU’s image. |
| `image_alt` | string or null | no | Alt text; use the product title when `image_url` is set. |
| `image_source` | enum or null | no | Merchant CDN that served the photo: `amazon` \| `target` \| `homedepot` \| `walmart` \| `oxo`. |
| `status` | enum | yes | Seed rows are `draft`. Promote to `ready` / `live` / `expired` in CMS after re-verification. |

## Trust / publish gates (must pass before `live`)

1. Confirm merchant + destination URL resolves to the intended SKU.
2. Record price or discount basis from the merchant page (or mark price-check-only).
3. Show restrictions and last-checked date on the public card.
4. Expire or unpublish when the sale ends or stock disappears.
5. Never fabricate discounts or invent prices.

## Discount basis conventions

- `sale vs list on merchant page (...)` — use with `is_verified_discount: true`.
- `price check only — no verified discount` — current (or null) price observed; no claim of % off.
- `secondary deal report citing merchant was/now (...)` — useful draft signal; **must** re-verify on PDP; keep `is_verified_discount: false` until then.
- `under $X ceiling` — optional editorial framing when product fits a guide budget without a sale claim.

## Category mapping to site

| Schema `category` | Site label |
|-------------------|------------|
| `everyday` | Everyday Shopping |
| `home` | Home Savings |
| `travel` | Travel |

## Affiliate notes

- Store `product_url` as clean canonical; generate affiliate wrappers at render time.
- Amazon Associates → `suggested_affiliate_network: amazon`.
- Target / Walmart / Home Depot commonly via Impact (or current network) → `impact`.
- Brand sites without a known program → `pending`.

## Image policy

- Show a real product photo from the listing’s merchant, or show a “no photo” state. Never use stock, guessed, or cross-SKU images.
- Prefer hotlinking the merchant CDN URL captured from that PDP (Amazon `m.media-amazon.com`, Target Scene7 `GUEST_` assets, Home Depot `images.thdstatic.com`, Walmart `i5.walmartimages.com`).
- Amazon images must come from Amazon product-page assets (`/images/I/…` on the PDP, or the Associates image widget)—not third-party mirrors.
- Search/category `product_url` rows stay `image_url: null` until an ASIN/SKU is locked.
- If a PDP bot-walls the fetcher, leave `image_url` null unless the CDN URL can be verified from that same listing (for example a Wayback snapshot of the merchant PDP whose `images.thdstatic.com` URL still resolves).
