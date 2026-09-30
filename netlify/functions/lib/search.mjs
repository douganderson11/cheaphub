import https from "node:https";
import { loadCatalog, loadOverrides } from "./catalog.mjs";
import { cleanProductUrl, goHref, usesAffiliate } from "./go.mjs";
import {
  amazonAsin,
  amazonSearchHits,
  discountBasis,
  homeDepotSearchHits,
  hostStore,
  parseProductPage,
  parseQuery,
  storeLabel,
  targetSearchHits,
  walmartSearchHits,
} from "./parse.mjs";

const STORES = ["amazon", "target", "walmart", "homedepot"];

const SEARCH_URL = {
  amazon: (keywords) => `https://www.amazon.com/s?k=${encodeURIComponent(keywords)}`,
  target: (keywords) => `https://www.target.com/s?searchTerm=${encodeURIComponent(keywords)}`,
  walmart: (keywords) => `https://www.walmart.com/search?q=${encodeURIComponent(keywords)}`,
  homedepot: (keywords) => `https://www.homedepot.com/s/${encodeURIComponent(keywords)}`,
};

const BROWSER_HEADERS = {
  "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
  accept: "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
  "accept-language": "en-US,en;q=0.9",
};

export function defaultFetch(url, timeoutMs, redirects = 0) {
  const timeout = Math.max(500, timeoutMs || 4000);
  return new Promise((resolve) => {
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      resolve({ status: 0, url, text: "", error: "error" });
      return;
    }
    if (parsed.protocol !== "https:" || !hostStore(parsed.toString())) {
      resolve({ status: 0, url, text: "", error: "error" });
      return;
    }
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    const req = https.get(parsed, {
      headers: {
        "User-Agent": BROWSER_HEADERS["user-agent"],
        Accept: BROWSER_HEADERS.accept,
        "Accept-Language": BROWSER_HEADERS["accept-language"],
      },
    }, (res) => {
      const status = res.statusCode || 0;
      const location = res.headers.location;
      if (location && [301, 302, 303, 307, 308].includes(status) && redirects < 3) {
        res.resume();
        let next;
        try {
          next = new URL(location, parsed).toString();
        } catch {
          finish({ status, url, text: "", error: "error" });
          return;
        }
        if (!hostStore(next)) {
          finish({ status, url: next, text: "", error: "error" });
          return;
        }
        defaultFetch(next, timeout, redirects + 1).then(finish);
        return;
      }
      const chunks = [];
      let size = 0;
      res.on("data", (chunk) => {
        size += chunk.length;
        if (size > 4_000_000) {
          req.destroy();
          return;
        }
        chunks.push(chunk);
      });
      res.on("end", () => {
        finish({
          status,
          url: parsed.toString(),
          text: Buffer.concat(chunks).toString("utf8"),
          error: null,
        });
      });
    });
    req.on("error", () => finish({ status: 0, url, text: "", error: "error" }));
    req.setTimeout(timeout, () => {
      req.destroy();
      finish({ status: 0, url, text: "", error: "timeout" });
    });
  });
}

export function matchCatalog(tokens, ceiling, products) {
  if (!tokens.length) return [];
  const need = tokens.length === 1 ? 1 : Math.min(2, tokens.length);
  const ranked = [];
  for (const product of products) {
    const title = String(product.title || "").toLowerCase();
    let hits = 0;
    for (const token of tokens) {
      if (title.includes(token)) hits += 1;
    }
    if (hits < need) continue;
    const remembered = typeof product.current_price === "number" ? product.current_price : null;
    ranked.push({
      product,
      score: hits * 10 + (hits === tokens.length ? 5 : 0),
      underHint: ceiling != null && remembered != null && remembered <= ceiling,
    });
  }
  ranked.sort((a, b) => {
    if (a.underHint !== b.underHint) return a.underHint ? -1 : 1;
    if (a.score !== b.score) return b.score - a.score;
    const aRank = a.product.priority_rank || 999;
    const bRank = b.product.priority_rank || 999;
    if (aRank !== bRank) return aRank - bRank;
    return (a.product.sort_index || 0) - (b.product.sort_index || 0);
  });
  return ranked.map((entry) => entry.product);
}

function productKey(url) {
  const asin = amazonAsin(url);
  if (asin) return `amazon:${asin}`;
  const clean = cleanProductUrl(url);
  return clean || null;
}

function emptyRead() {
  return { priced: [], unchecked: [] };
}

function pushUnique(list, item, seen) {
  if (!item || !item.href || seen.has(item.key)) return;
  seen.add(item.key);
  list.push(item);
}

export async function searchDeals(rawQuery, deps = {}) {
  const parsedQuery = parseQuery(rawQuery);
  if (!parsedQuery.ok) {
    return {
      httpStatus: parsedQuery.empty ? 200 : 400,
      query: parsedQuery.display || "",
      ceiling: null,
      results: [],
      over_budget: [],
      unchecked: [],
      skipped: [],
      link_note: linkNote([]),
      error: parsedQuery.empty ? null : parsedQuery.error,
      checked_at: new Date().toISOString(),
      took_ms: 0,
    };
  }

  const catalog = deps.catalog || loadCatalog();
  const overrides = deps.overrides || loadOverrides();
  const fetchPage = deps.fetchPage || defaultFetch;
  const budgetMs = deps.budgetMs ?? 8500;
  const started = Date.now();
  const remaining = () => budgetMs - (Date.now() - started);
  const matches = matchCatalog(parsedQuery.tokens, parsedQuery.ceiling, catalog).slice(0, 2);
  const knownKeys = new Set(matches.map((product) => productKey(product.product_url)).filter(Boolean));

  const catalogReads = Promise.all(
    matches.map((product) => readCatalogProduct(product, overrides, fetchPage, remaining))
  );
  const storeReads = Promise.all(
    STORES.map((store) => readStore(store, parsedQuery.keywords, fetchPage, remaining, knownKeys))
  );
  const [catalogItems, storeItems] = await Promise.all([catalogReads, storeReads]);

  const seen = new Set();
  const priced = [];
  const unchecked = [];
  const skipped = [];

  for (const item of catalogItems) {
    if (item.priced) pushUnique(priced, item.priced, seen);
    if (item.unchecked) pushUnique(unchecked, item.unchecked, seen);
  }
  for (const store of storeItems) {
    if (store.skipped) skipped.push(store.skipped);
    for (const item of store.priced) pushUnique(priced, item, seen);
    for (const item of store.unchecked) pushUnique(unchecked, item, seen);
  }

  const results = [];
  const overBudget = [];
  for (const item of priced) {
    const publicItem = publicResult(item);
    if (parsedQuery.ceiling != null && publicItem.price > parsedQuery.ceiling) overBudget.push(publicItem);
    else results.push(publicItem);
  }

  const publicUnchecked = unchecked.slice(0, 4).map(publicUncheckedItem);
  const shown = results.concat(overBudget, publicUnchecked);

  return {
    httpStatus: 200,
    query: parsedQuery.display,
    keywords: parsedQuery.keywords,
    ceiling: parsedQuery.ceiling,
    checked_at: new Date().toISOString(),
    results: results.slice(0, 6),
    over_budget: overBudget.slice(0, 4),
    unchecked: publicUnchecked,
    skipped,
    link_note: linkNote(shown),
    error: null,
    took_ms: Date.now() - started,
  };
}

function linkNote(items) {
  if (items.some((item) => item.uses_affiliate)) {
    return "Clicks go through /go/. An affiliate tag is attached only when that product already has one in the site's affiliate overrides.";
  }
  return "Clicks go through /go/. None of these products have an affiliate tag saved, so each click is a plain product URL.";
}

function publicResult(item) {
  return {
    key: item.key,
    source: item.source,
    title: item.title,
    merchant: item.merchant,
    price: item.price,
    list_price: item.listPrice,
    list_label: item.listLabel,
    is_verified_discount: item.isVerifiedDiscount,
    discount_basis: item.discountBasis,
    image_url: item.imageUrl,
    image_alt: item.title,
    href: item.href,
    uses_affiliate: item.usesAffiliate,
  };
}

function publicUncheckedItem(item) {
  return {
    key: item.key,
    source: item.source,
    title: item.title,
    merchant: item.merchant,
    image_url: item.imageUrl,
    image_alt: item.title,
    href: item.href,
    uses_affiliate: item.usesAffiliate,
    reason: item.reason,
  };
}

async function readCatalogProduct(product, overrides, fetchPage, remaining) {
  const store = hostStore(product.product_url);
  const key = productKey(product.product_url) || `catalog:${product.id}`;
  const href = goHref({ catalogId: product.id, productUrl: product.product_url });
  const affiliate = usesAffiliate(product.id, overrides);
  const catalogImage = allowedCatalogImage(product.image_url);
  const base = {
    key,
    source: "catalog",
    title: product.title,
    merchant: product.merchant || storeLabel(store),
    href,
    usesAffiliate: affiliate,
    imageUrl: catalogImage,
  };
  if (!store || !href) {
    return {
      unchecked: {
        ...base,
        reason: "The catalog link is not a product page on Amazon, Target, Walmart, or Home Depot.",
      },
    };
  }
  if (remaining() < 800) {
    return {
      unchecked: {
        ...base,
        reason: "Time ran out before this product page could be opened.",
      },
    };
  }
  const response = await fetchPage(product.product_url, Math.min(4500, remaining()));
  return classifyRead(base, store, response, { allowCatalogImage: true });
}

function allowedCatalogImage(url) {
  if (!url || typeof url !== "string") return null;
  if (url.startsWith("/assets/products/")) return url;
  try {
    const host = new URL(url).hostname;
    if ([
      "m.media-amazon.com",
      "images-na.ssl-images-amazon.com",
      "target.scene7.com",
      "images.thdstatic.com",
      "images.homedepot-static.com",
      "i5.walmartimages.com",
      "i.walmartimages.com",
    ].includes(host)) return url;
  } catch {
    return null;
  }
  return null;
}

async function readStore(store, keywords, fetchPage, remaining, knownKeys) {
  const label = storeLabel(store);
  if (remaining() < 1200) {
    return {
      ...emptyRead(),
      skipped: { merchant: label, reason: `${label} was skipped because the search ran out of time.` },
    };
  }
  const response = await fetchPage(SEARCH_URL[store](keywords), Math.min(4000, remaining()));
  if (response.error === "timeout") {
    return {
      ...emptyRead(),
      skipped: { merchant: label, reason: `${label} didn't answer before the time limit, so this search skipped it.` },
    };
  }
  if (!response.status || response.status === 403 || response.status === 401 || response.status === 429) {
    return {
      ...emptyRead(),
      skipped: { merchant: label, reason: `${label} refused the search page${response.status ? ` (${response.status})` : ""}, so this search skipped it.` },
    };
  }
  if (store === "walmart" && /<title>\s*Robot or human\?/i.test(response.text)) {
    return {
      ...emptyRead(),
      skipped: { merchant: label, reason: "Walmart showed a robot check, so this search skipped it." },
    };
  }
  const hits = searchHits(store, response.text).filter((hit) => !hit.sponsored);
  const fresh = hits.filter((hit) => {
    const key = productKey(hit.url);
    return key && !knownKeys.has(key);
  }).slice(0, store === "amazon" ? 2 : 1);
  if (!fresh.length) {
    if (hits.length) return { priced: [], unchecked: [], skipped: null };
    return {
      ...emptyRead(),
      skipped: {
        merchant: label,
        reason: `${label}'s search page didn't include product links we could open, so this search skipped it.`,
      },
    };
  }
  if (remaining() < 1200) {
    return {
      ...emptyRead(),
      skipped: { merchant: label, reason: `${label}'s search loaded, but time ran out before a product page opened.` },
    };
  }
  const reads = await Promise.all(fresh.map((hit) => readNewProduct(store, hit, fetchPage, remaining)));
  const priced = [];
  const unchecked = [];
  for (const read of reads) {
    if (read.priced) priced.push(read.priced);
    if (read.unchecked) unchecked.push(read.unchecked);
  }
  if (!priced.length && !unchecked.length) {
    return {
      ...emptyRead(),
      skipped: { merchant: label, reason: `${label}'s product page didn't open, so this search skipped it.` },
    };
  }
  return { priced, unchecked, skipped: priced.length ? null : null };
}

function searchHits(store, html) {
  if (store === "amazon") return amazonSearchHits(html);
  if (store === "target") return targetSearchHits(html);
  if (store === "walmart") return walmartSearchHits(html);
  if (store === "homedepot") return homeDepotSearchHits(html);
  return [];
}

async function readNewProduct(store, hit, fetchPage, remaining) {
  const label = storeLabel(store);
  const href = goHref({ productUrl: hit.url });
  const key = productKey(hit.url);
  if (!href || !key) return {};
  const response = await fetchPage(hit.url, Math.min(4500, remaining()));
  const base = {
    key,
    source: store,
    title: hit.title || label,
    merchant: label,
    href,
    usesAffiliate: false,
    imageUrl: null,
  };
  return classifyRead(base, store, response, { allowCatalogImage: false });
}

function usefulTitle(title, merchant) {
  if (!title) return null;
  const clean = String(title).trim();
  if (!clean || clean.toLowerCase() === String(merchant || "").toLowerCase()) return null;
  if (/^(amazon's choice|sponsored ad|best seller)\b/i.test(clean)) return null;
  return clean;
}

function classifyRead(base, store, response, options) {
  const label = base.merchant || storeLabel(store);
  const fallbackTitle = usefulTitle(base.title, label) || (base.source === "catalog" ? base.title : null);
  if (!response || response.error === "timeout") {
    if (!fallbackTitle) return {};
    return {
      unchecked: {
        ...base,
        title: fallbackTitle,
        imageUrl: options.allowCatalogImage ? base.imageUrl : null,
        reason: `${label} didn't answer before the time limit. No price was read.`,
      },
    };
  }
  if (!response.status || response.status >= 400) {
    if (!fallbackTitle) return {};
    return {
      unchecked: {
        ...base,
        title: fallbackTitle,
        imageUrl: options.allowCatalogImage ? base.imageUrl : null,
        reason: `${label} wouldn't open the product page${response.status ? ` (${response.status})` : ""}. No price was read.`,
      },
    };
  }
  const parsed = parseProductPage(store, response.text, { status: response.status, finalUrl: response.url });
  const title = usefulTitle(parsed.title, label) || fallbackTitle;
  if (!title) return {};
  if (parsed.blocked || parsed.price == null) {
    const imageUrl = (parsed.imageUrl && !parsed.blocked) ? parsed.imageUrl : (options.allowCatalogImage ? base.imageUrl : null);
    return {
      unchecked: {
        ...base,
        title,
        imageUrl,
        reason: parsed.reason || `${label}'s product page didn't include a selling price.`,
      },
    };
  }
  const imageUrl = parsed.imageUrl || (options.allowCatalogImage ? base.imageUrl : null);
  return {
    priced: {
      ...base,
      title,
      price: parsed.price,
      listPrice: parsed.listPrice,
      listLabel: parsed.listLabel,
      isVerifiedDiscount: Boolean(parsed.isVerifiedDiscount && parsed.listPrice > parsed.price),
      discountBasis: discountBasis(label, parsed),
      imageUrl,
    },
  };
}

