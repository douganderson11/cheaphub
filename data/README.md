# Seed catalog

| File | Purpose |
|------|---------|
| `seed-catalog.json` | 71 researched products (source of truth for the build) |
| `seed-catalog.csv` | Same rows for spreadsheet review |
| `catalog-schema.md` | Field definitions and publish gates |
| `seed-catalog-summary.md` | Category counts, first-20 priority, module notes |
| `product-image-report.json` | Last image-fetch outcomes (ok / skipped / missing) |
| `product-image-locks.json` | Verified PDP + photo locks applied by the image pass |
| `excluded-pending-photo.json` | Seed rows omitted from the public catalog until they have a photo |
| `affiliate-overrides.json` | Optional map of `product-id` → affiliate URL |
| `ENTITY.md` | Affiliate operator vs domain/IP owner |

Leave override values empty (or omit the id) to send `/go/{id}/` to the clean `product_url`. After editing the seed file or overrides, run:

```bash
python3 scripts/build-catalog.py
```

To refresh merchant product photos from locked PDPs:

```bash
python3 scripts/fetch-product-images.py
python3 scripts/build-catalog.py
```
