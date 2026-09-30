/**
 * Read a selling price from merchant product-page HTML.
 * Search-page prices, remembered catalog prices, and "was" prices are not selling prices.
 */

const IMAGE_HOSTS = new Set([
  "m.media-amazon.com",
  "images-na.ssl-images-amazon.com",
  "images-eu.ssl-images-amazon.com",
  "target.scene7.com",
  "images.thdstatic.com",
  "images.homedepot-static.com",
  "i5.walmartimages.com",
  "i.walmartimages.com",
]);

const STOP_WORDS = new Set([
  "a", "an", "the", "for", "with", "and", "or", "of", "to", "in", "on", "my", "me",
]);

export function usd(raw) {
  if (raw == null) return null;
  const cleaned = String(raw).replace(/,/g, "").trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(cleaned)) return null;
  const value = Number(cleaned);
  if (!Number.isFinite(value) || value <= 0 || value > 100000) return null;
  return Math.round(value * 100) / 100;
}

export function decodeHtml(value) {
  return String(value || "")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/\s+/g, " ")
    .trim();
}

export function allowedImageUrl(url) {
  if (!url || typeof url !== "string") return null;
  if (url.startsWith("/assets/products/")) return url;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:") return null;
    if (!IMAGE_HOSTS.has(parsed.hostname)) return null;
    return url;
  } catch {
    return null;
  }
}

export function parseQuery(raw) {
  const display = String(raw || "").replace(/\s+/g, " ").trim();
  if (!display) {
    return { ok: false, empty: true, error: "Type a product name." };
  }
  if (display.length > 80) {
    return { ok: false, error: "Keep the search under 80 characters." };
  }
  const ceilingMatch = display.match(/\b(?:under|below|less than)\s+\$?\s*(\d{1,4})(?:\.\d{2})?\b/i);
  const ceiling = ceilingMatch ? Number(ceilingMatch[1]) : null;
  const keywords = display
    .replace(/\b(?:under|below|less than)\s+\$?\s*\d+(?:\.\d{2})?\b/gi, " ")
    .replace(/[^\p{L}\p{N}\s.'"-]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (keywords.length < 2) {
    return { ok: false, error: "Type a product name." };
  }
  const tokens = keywords
    .toLowerCase()
    .split(" ")
    .filter((token) => token.length >= 3 && !STOP_WORDS.has(token));
  return { ok: true, display, keywords, tokens, ceiling };
}

function sliceById(html, id) {
  const marker = `id="${id}"`;
  const start = html.indexOf(marker);
  if (start < 0) return "";
  return html.slice(start, start + 16000);
}

function moneyText(amount) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

export function formatMoney(amount) {
  return moneyText(amount);
}

function basisFromChunk(chunk) {
  const match = chunk.match(
    /apex-basisprice-offscreen-label">\s*((?:Typical price|List Price))\s*:\s*\$(\d[\d,]*(?:\.\d{2})?)/i
  );
  if (!match) return null;
  const amount = usd(match[2]);
  if (amount == null) return null;
  const label = /^list price$/i.test(match[1]) ? "List price" : "Typical price";
  return { amount, label };
}

function sellingFromChunk(chunk) {
  const whole = chunk.match(
    /priceToPay[\s\S]{0,700}?a-price-whole">(\d[\d,]*)<[\s\S]{0,160}?a-price-fraction">(\d{2})/
  );
  if (whole) {
    const amount = usd(`${whole[1]}.${whole[2]}`);
    if (amount != null) return amount;
  }
  const access = chunk.match(
    /apex-pricetopay-accessibility-label[^>]*>\s*\$(\d[\d,]*(?:\.\d{2})?)/
  );
  if (access) return usd(access[1]);
  return null;
}

export function parseAmazonPdp(html) {
  const text = String(html || "");
  const titleMatch = text.match(/id="productTitle"[^>]*>\s*([^<]+)/);
  const title = titleMatch ? decodeHtml(titleMatch[1]) : null;
  if (!title) {
    return {
      blocked: true,
      title: null,
      price: null,
      reason: "Amazon didn't return a product page we could read.",
    };
  }
  const chunk = sliceById(text, "corePriceDisplay_desktop_feature_div")
    || sliceById(text, "corePrice_feature_div");
  const price = chunk ? sellingFromChunk(chunk) : null;
  const basis = chunk ? basisFromChunk(chunk) : null;
  const image = amazonImage(text);
  if (price == null) {
    return {
      blocked: false,
      title,
      price: null,
      listPrice: null,
      listLabel: null,
      isVerifiedDiscount: false,
      imageUrl: image,
      reason: "No selling price was in the Amazon product price block.",
    };
  }
  const list = basis && basis.amount > price ? basis : null;
  return {
    blocked: false,
    title,
    price,
    listPrice: list ? list.amount : null,
    listLabel: list ? list.label : null,
    isVerifiedDiscount: Boolean(list),
    imageUrl: image,
    reason: null,
  };
}

function amazonImage(html) {
  const match = html.match(/"hiRes"\s*:\s*"(https:\/\/m\.media-amazon\.com\/images\/I\/[^"\\]+)"/);
  if (!match) return null;
  const sized = match[1].replace(/\._[^./]+_\./, "._AC_SL500_.");
  return allowedImageUrl(sized);
}

export function amazonAsin(url) {
  const match = String(url || "").match(/\/(?:dp|gp\/product|gp\/aw\/d)\/([A-Z0-9]{10})(?:[/?#]|$)/);
  return match ? match[1] : null;
}

export function amazonSearchHits(html) {
  const hits = [];
  const seen = new Set();
  const re = /<div role="listitem"([^>]*)>/g;
  let match;
  while ((match = re.exec(html))) {
    const attrs = match[1];
    if (!attrs.includes("s-search-result")) continue;
    const asinMatch = attrs.match(/data-asin="([A-Z0-9]{10})"/);
    if (!asinMatch || seen.has(asinMatch[1])) continue;
    const classMatch = attrs.match(/class="([^"]*)"/);
    const sponsored = Boolean(classMatch && classMatch[1].includes("AdHolder"));
    seen.add(asinMatch[1]);
    const window = html.slice(match.index, match.index + 4000);
    const heading = window.match(/<h2[^>]*aria-label="([^"]+)"/);
    let title = heading ? decodeHtml(heading[1]) : null;
    if (title && /^(amazon's choice|sponsored|best seller)\b/i.test(title)) title = null;
    if (!title) {
      const span = window.match(/<h2[\s\S]{0,500}?<span[^>]*>([^<]{8,})<\/span>/i);
      title = span ? decodeHtml(span[1]) : null;
    }
    hits.push({
      asin: asinMatch[1],
      url: `https://www.amazon.com/dp/${asinMatch[1]}`,
      title,
      sponsored,
    });
  }
  return hits;
}

function jsonLdProducts(html) {
  const products = [];
  const re = /<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi;
  let match;
  while ((match = re.exec(html))) {
    try {
      collectProducts(JSON.parse(match[1]), products);
    } catch {
      // Ignore broken JSON-LD. A missing price is a skip, not a guess.
    }
  }
  return products;
}

function collectProducts(node, products) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    node.forEach((item) => collectProducts(item, products));
    return;
  }
  const type = node["@type"];
  const types = Array.isArray(type) ? type : [type];
  if (types.includes("Product")) products.push(node);
  if (node["@graph"]) collectProducts(node["@graph"], products);
}

function offerPrice(offers) {
  const list = Array.isArray(offers) ? offers : [offers];
  for (const offer of list) {
    if (!offer || typeof offer !== "object") continue;
    const currency = offer.priceCurrency || "USD";
    if (currency !== "USD") continue;
    const price = usd(offer.price);
    if (price != null) return price;
  }
  return null;
}

function offerListPrice(offers, selling) {
  const list = Array.isArray(offers) ? offers : [offers];
  for (const offer of list) {
    if (!offer || typeof offer !== "object") continue;
    const specs = Array.isArray(offer.priceSpecification)
      ? offer.priceSpecification
      : [offer.priceSpecification];
    for (const spec of specs) {
      if (!spec || typeof spec !== "object") continue;
      const kind = `${spec.priceType || ""} ${spec.name || ""}`;
      if (!/list|msrp|typical/i.test(kind)) continue;
      const amount = usd(spec.price);
      if (amount != null && amount > selling) {
        return { amount, label: /typical/i.test(kind) ? "Typical price" : "List price" };
      }
    }
  }
  return null;
}

function firstString(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.find((item) => typeof item === "string") || null;
  return null;
}

export function parseJsonLdPdp(html) {
  const products = jsonLdProducts(html);
  for (const product of products) {
    const price = offerPrice(product.offers);
    const title = decodeHtml(product.name || "") || null;
    const image = allowedImageUrl(firstString(product.image));
    if (price == null) {
      return {
        blocked: false,
        title,
        price: null,
        listPrice: null,
        listLabel: null,
        isVerifiedDiscount: false,
        imageUrl: image,
        reason: "The product page had no selling price in its product data.",
      };
    }
    const list = offerListPrice(product.offers, price);
    return {
      blocked: false,
      title,
      price,
      listPrice: list ? list.amount : null,
      listLabel: list ? list.label : null,
      isVerifiedDiscount: Boolean(list),
      imageUrl: image,
      reason: null,
    };
  }
  return null;
}

function pageTitle(html) {
  const match = String(html || "").match(/<title[^>]*>\s*([^<]+)/i);
  return match ? decodeHtml(match[1]) : null;
}

function targetImage(html) {
  const og = html.match(/property=["']og:image["'][^>]*content=["']([^"']+)/i)
    || html.match(/content=["']([^"']+)["'][^>]*property=["']og:image["']/i);
  if (!og) return null;
  const raw = og[1].replace(/&amp;/g, "&").replace(/\\u002F/g, "/");
  if (!/target\.scene7\.com\/is\/image\/Target\/GUEST_/i.test(raw)) return null;
  const bare = raw.split("?")[0];
  return allowedImageUrl(`${bare}?wid=600&hei=600&qlt=85`);
}

export function parseTargetPdp(html) {
  const text = String(html || "");
  const fromLd = parseJsonLdPdp(text);
  if (fromLd && fromLd.price != null) return fromLd;
  const title = pageTitle(text);
  const cleanTitle = title ? title.replace(/\s*[:|]\s*Target\s*$/i, "").trim() : null;
  return {
    blocked: false,
    title: cleanTitle,
    price: null,
    listPrice: null,
    listLabel: null,
    isVerifiedDiscount: false,
    imageUrl: targetImage(text),
    reason: "Target's page loaded, but the selling price is not in the HTML.",
  };
}

export function targetSearchHits(html) {
  const hits = [];
  const seen = new Set();
  const re = /\/p\/[^"'\\\s]+\/-\/A-(\d{5,10})/g;
  let match;
  while ((match = re.exec(html))) {
    if (seen.has(match[1])) continue;
    seen.add(match[1]);
    hits.push({
      id: match[1],
      url: `https://www.target.com${match[0]}`,
    });
  }
  return hits;
}

function walkPriceInfo(node, depth, found) {
  if (!node || depth > 8 || found.product) return;
  if (Array.isArray(node)) {
    for (const item of node.slice(0, 20)) walkPriceInfo(item, depth + 1, found);
    return;
  }
  if (typeof node !== "object") return;
  if (node.product && node.product.priceInfo && usd(node.product.priceInfo.currentPrice?.price) != null) {
    found.product = node.product;
    return;
  }
  const info = node.priceInfo;
  if (info && usd(info.currentPrice?.price) != null && (node.name || node.productName)) {
    found.product = node;
    return;
  }
  for (const key of Object.keys(node).slice(0, 30)) walkPriceInfo(node[key], depth + 1, found);
}

export function parseWalmartPdp(html, finalUrl = "") {
  const text = String(html || "");
  if (/<title>\s*Robot or human\?/i.test(text) || /walmart\.com\/blocked/i.test(finalUrl)) {
    return { blocked: true, price: null, title: null, reason: "Walmart showed a robot check." };
  }
  const next = text.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
  if (next) {
    try {
      const data = JSON.parse(next[1]);
      const found = {};
      walkPriceInfo(data, 0, found);
      if (found.product) {
        const info = found.product.priceInfo;
        const price = usd(info.currentPrice.price);
        const listRaw = info.listPrice && usd(info.listPrice.price);
        const list = listRaw != null && listRaw > price
          ? { amount: listRaw, label: "List price" }
          : null;
        const og = text.match(/property=["']og:image["'][^>]*content=["']([^"']+)/i);
        const image = allowedImageUrl(og && og[1]) || null;
        return {
          blocked: false,
          title: decodeHtml(found.product.name || pageTitle(text) || "") || null,
          price,
          listPrice: list ? list.amount : null,
          listLabel: list ? list.label : null,
          isVerifiedDiscount: Boolean(list),
          imageUrl: image,
          reason: null,
        };
      }
    } catch {
      // Fall through. No price means no price.
    }
  }
  const fromLd = parseJsonLdPdp(text);
  if (fromLd && fromLd.price != null) return fromLd;
  return {
    blocked: false,
    title: pageTitle(text),
    price: null,
    imageUrl: null,
    listPrice: null,
    listLabel: null,
    isVerifiedDiscount: false,
    reason: "Walmart's page did not include a selling price we could read.",
  };
}

export function walmartSearchHits(html) {
  if (/<title>\s*Robot or human\?/i.test(html)) return [];
  const hits = [];
  const seen = new Set();
  const re = /\/ip\/[^"'\\\s]+\/(\d{3,})/g;
  let match;
  while ((match = re.exec(html))) {
    if (seen.has(match[1])) continue;
    seen.add(match[1]);
    hits.push({ id: match[1], url: `https://www.walmart.com${match[0]}` });
  }
  return hits;
}

export function parseHomeDepotPdp(html, status = 200) {
  if (status === 403 || status === 401) {
    return { blocked: true, price: null, title: null, reason: "Home Depot refused the page." };
  }
  const fromLd = parseJsonLdPdp(html);
  if (fromLd && fromLd.price != null) return fromLd;
  return {
    blocked: false,
    title: pageTitle(html),
    price: null,
    imageUrl: fromLd ? fromLd.imageUrl : null,
    listPrice: null,
    listLabel: null,
    isVerifiedDiscount: false,
    reason: "Home Depot's page did not include a selling price we could read.",
  };
}

export function homeDepotSearchHits(html) {
  const hits = [];
  const seen = new Set();
  const re = /\/p\/[^"'\\\s]+\/(\d{6,})/g;
  let match;
  while ((match = re.exec(html))) {
    if (seen.has(match[1])) continue;
    seen.add(match[1]);
    hits.push({ id: match[1], url: `https://www.homedepot.com${match[0]}` });
  }
  return hits;
}

export function hostStore(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (host === "amazon.com") return "amazon";
    if (host === "target.com") return "target";
    if (host === "walmart.com") return "walmart";
    if (host === "homedepot.com") return "homedepot";
  } catch {
    return null;
  }
  return null;
}

export function parseProductPage(store, html, meta = {}) {
  if (store === "amazon") return parseAmazonPdp(html);
  if (store === "target") return parseTargetPdp(html);
  if (store === "walmart") return parseWalmartPdp(html, meta.finalUrl || "");
  if (store === "homedepot") return parseHomeDepotPdp(html, meta.status);
  return { blocked: false, price: null, title: null, reason: "That store is not one we open." };
}

export function discountBasis(storeName, parsed) {
  if (!parsed || parsed.price == null) return null;
  const selling = moneyText(parsed.price);
  if (parsed.isVerifiedDiscount && parsed.listPrice != null && parsed.listLabel) {
    const kind = parsed.listLabel === "Typical price" ? "typical price" : "list price";
    return `The ${storeName} page showed a ${kind} of ${moneyText(parsed.listPrice)} above the ${selling} selling price.`;
  }
  return `Selling price read from the ${storeName} product page just now. That page didn't show a typical or list price above it.`;
}

export function storeLabel(store) {
  if (store === "amazon") return "Amazon";
  if (store === "target") return "Target";
  if (store === "walmart") return "Walmart";
  if (store === "homedepot") return "Home Depot";
  return store;
}
