/**
 * Outbound clicks stay on /go/.
 * An affiliate destination is used only when data/affiliate-overrides.json already has one.
 */

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
  return cleanProductUrl(decoded);
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
