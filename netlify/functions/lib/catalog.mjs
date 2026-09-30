import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

function readJson(name) {
  const candidates = [
    join(here, "../../..", name),
    join(process.cwd(), name),
    join("/var/task", name),
  ];
  for (const path of candidates) {
    try {
      return JSON.parse(readFileSync(path, "utf8"));
    } catch {
      // Try the next location. Netlify copies included files to /var/task.
    }
  }
  throw new Error(`Missing ${name}`);
}

export function loadCatalog() {
  const catalogFile = readJson("assets/catalog.json");
  const products = Array.isArray(catalogFile.products) ? catalogFile.products : [];
  return products.filter((product) => product && product.image_url && product.status !== "expired" && product.product_url);
}

export function loadOverrides() {
  const overridesFile = readJson("data/affiliate-overrides.json");
  if (!overridesFile || typeof overridesFile !== "object" || Array.isArray(overridesFile)) return {};
  return overridesFile;
}
