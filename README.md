# CheapHub

Trust-first deals, coupons, and buying guides for [cheaphub.com](https://cheaphub.com/).

This repository is a static site (HTML, CSS, JS) ready for Netlify. The tree matches the former production Drop deploy, plus a seed product catalog and a centralized outbound-link layer.

## Local preview

From the repo root:

```bash
python3 scripts/serve.py
```

Then open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). The helper honors `_redirects`, including `/go/{product-id}/` hops to merchant URLs.

A plain static server also works for page rendering:

```bash
python3 -m http.server 8080
```

`/go/` fallback pages still work that way; Netlify `_redirects` do not.

## Catalog and affiliate links

- Source data: `data/seed-catalog.json` (CSV and schema notes sit beside it)
- Runtime catalog: `assets/catalog.json` (built from the seed file)
- Optional affiliate destinations: `data/affiliate-overrides.json`
- Rebuild generated files after catalog or override edits:

```bash
python3 scripts/build-catalog.py
python3 scripts/check-catalog.py
```

Product photos come from the merchant listing (`image_url` on each catalog row). Re-resolve them after URL/SKU changes:

```bash
python3 scripts/fetch-product-images.py
python3 scripts/build-catalog.py
python3 scripts/check-catalog.py
```

Hotlinked CDNs are Amazon (`m.media-amazon.com`), Target Scene7, and Home Depot (`images.thdstatic.com`). `_headers` allows those hosts in `img-src`. Search/category URLs and bot-walled PDPs stay `image_url: null` and render a “No photo yet” state — never a guessed picture.

Outbound product links use `/go/{id}/`. Destination is `affiliate_url` when set, otherwise the clean `product_url`. Do not invent discounts or percentages; a **Verified discount** badge is rendered only when `is_verified_discount` is true.

## Deploy note

Production is still a Netlify Drop publish until the site is connected to this Git repository. After connecting Git, a production deploy from `main` (or this branch as a preview) will replace Drop.
