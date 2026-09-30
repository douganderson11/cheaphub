/**
 * Outbound clicks stay on /go/.
 * An affiliate destination is used only when data/affiliate-overrides.json already has one.
 * Amazon product clicks also pick up AMAZON_ASSOCIATE_TAG when that value is set.
 */

import { pathToFileURL } from "node:url";

const PRODUCT_PATH = {
  amazon: /^\/(?:[^/]+\/)*dp\/[A-Z0-9]{10}\/?$|^\/gp\/product\/[A-Z0-9]{10}\/?$/,
  target: /^\/p\/[^/]+\/-\/A-\d{5,10}\/?$/,
  walmart: /^\/ip\/[^/]+\/\d{3,}\/?$/,
  homedepot: /^\/p\/[^/]+\/\d{6,}\/?$/,
};

function storeFromHost(hostname) {
  const host = hostname.replace(/^www\./, "");
  if (host === "amazon.com") return "amazon";
  if (host === "target.com") return "target";
  if (host === "walmart.com") return "walmart";
  if (host === "homedepot.com") return "homedepot";
  return null;
}

// CheapHub's tracking ID on the existing MarshMack Media LLC Associates store.
// https://cheaphub.com is an approved site. Appended only to Amazon product URLs.
export const AMAZON_ASSOCIATE_TAG = "cheaphubus-20";

export function normalizeAssociateTag(tag) {
  if (typeof tag !== "string") return "";
  const value = tag.trim();
  if (!value || !/^[A-Za-z0-9-]+$/.test(value)) return "";
  return value;
}

export function appendAmazonAssociateTag(url, tag = AMAZON_ASSOCIATE_TAG) {
  const value = normalizeAssociateTag(tag);
  if (!value || typeof url !== "string" || !url) return url;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  if (parsed.protocol !== "https:") return url;
  if (storeFromHost(parsed.hostname) !== "amazon") return url;
  if (!PRODUCT_PATH.amazon.test(parsed.pathname)) return url;
  if (parsed.searchParams.has("tag")) return url;
  parsed.searchParams.set("tag", value);
  return parsed.toString();
}

export function cleanProductUrl(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  const store = storeFromHost(parsed.hostname);
  if (!store) return null;
  if (parsed.search || parsed.username || parsed.password) return null;
  if (!PRODUCT_PATH[store].test(parsed.pathname)) return null;
  parsed.hash = "";
  parsed.hostname = `www.${parsed.hostname.replace(/^www\./, "")}`;
  if (parsed.pathname.endsWith("/") && parsed.pathname !== "/") {
    parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  }
  return parsed.toString();
}

export function encodeOutbound(url) {
  const clean = cleanProductUrl(url);
  if (!clean) return null;
  return Buffer.from(clean, "utf8").toString("base64url");
}

export function resolveOutbound(token) {
  if (!token || typeof token !== "string" || token.length > 800) return null;
  if (!/^[A-Za-z0-9_-]+$/.test(token)) return null;
  let decoded;
  try {
    decoded = Buffer.from(token, "base64url").toString("utf8");
  } catch {
    return null;
  }
  const clean = cleanProductUrl(decoded);
  if (!clean) return null;
  return appendAmazonAssociateTag(clean);
}

export function usesAffiliate(productId, overrides) {
  const value = overrides && overrides[productId];
  return typeof value === "string" && /^https:\/\//.test(value);
}

export function goHref({ catalogId, productUrl }) {
  if (catalogId && /^[a-z0-9-]+$/.test(catalogId)) return `/go/${catalogId}/`;
  const token = encodeOutbound(productUrl);
  if (!token) return null;
  return `/go/out/?u=${token}`;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href && process.argv[2] === "tag-urls") {
  const chunks = [];
  process.stdin.on("data", (chunk) => chunks.push(chunk));
  process.stdin.on("end", () => {
    let urls = [];
    try {
      urls = JSON.parse(Buffer.concat(chunks).toString("utf8") || "[]");
    } catch {
      process.stderr.write("deny\n");
      process.exit(2);
    }
    if (!Array.isArray(urls)) {
      process.stderr.write("deny\n");
      process.exit(2);
    }
    process.stdout.write(JSON.stringify(urls.map((url) => appendAmazonAssociateTag(url))));
  });
}
