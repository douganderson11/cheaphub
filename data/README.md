# Seed catalog

| File | Purpose |
|------|---------|
| `seed-catalog.json` | 71 researched products (source of truth for the build) |
| `seed-catalog.csv` | Same rows for spreadsheet review |
| `catalog-schema.md` | Field definitions and publish gates |
| `seed-catalog-summary.md` | Category counts, first-20 priority, module notes |
| `affiliate-overrides.json` | Optional map of `product-id` → affiliate URL |

Leave override values empty (or omit the id) to send `/go/{id}/` to the clean `product_url`. After editing the seed file or overrides, run:

```bash
python3 scripts/build-catalog.py
```
