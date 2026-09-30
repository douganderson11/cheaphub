import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { loadCatalog } from "../netlify/functions/lib/catalog.mjs";
import { AMAZON_ASSOCIATE_TAG, appendAmazonAssociateTag, cleanProductUrl, encodeOutbound, goHref, resolveOutbound } from "../netlify/functions/lib/go.mjs";
import {
  amazonSearchHits,
  parseAmazonPdp,
  parseHomeDepotPdp,
  parseTargetPdp,
  parseWalmartPdp,
} from "../netlify/functions/lib/parse.mjs";
import { matchCatalog, searchDeals } from "../netlify/functions/lib/search.mjs";

const AMAZON_SALE = `
<span class="a-offscreen">$99.00</span>
<div id="corePriceDisplay_desktop_feature_div">
  <span id="apex-pricetopay-accessibility-label"> $14.20 with 15 percent savings </span>
  <span class="a-price priceToPay apex-pricetopay-value"><span class="a-offscreen"> </span>
    <span class="a-price-whole">14<span class="a-price-decimal">.</span></span>
    <span class="a-price-fraction">20</span>
  </span>
  <span class="apex-basisprice-offscreen-label">Typical price: $16.70</span>
</div>
<span id="productTitle">Amazon Basics Batteries</span>
"hiRes":"https://m.media-amazon.com/images/I/715RL6A12gL._AC_SL1500_.jpg"
`;

const AMAZON_PLAIN = `
<div id="corePriceDisplay_desktop_feature_div">
  <span id="apex-pricetopay-accessibility-label"> $17.90 </span>
  <span class="a-price priceToPay"><span class="a-price-whole">17</span><span class="a-price-fraction">90</span></span>
</div>
<span id="productTitle">Lodge Cast Iron Skillet</span>
"hiRes":"https://m.media-amazon.com/images/I/71H-w0pZIuL._AC_SL500_.jpg"
List Price: <span class="a-text-strike">$40.00</span>
`;

const AMAZON_WAS_ONLY = `
<div id="corePriceDisplay_desktop_feature_div">
  <span class="a-text-strike">$40.00</span>
  <span class="a-offscreen">$40.00</span>
</div>
<span id="productTitle">No selling price</span>
`;

const AMAZON_SEARCH = `
<div role="listitem" data-asin="B0FZK8TT6V" data-component-type="s-search-result" class="s-result-item AdHolder">
  <h2 aria-label="Sponsored Ad - Other pan"></h2>
  <span class="a-offscreen">$4.00</span>
</div>
<div role="listitem" data-asin="B00006JSUA" data-component-type="s-search-result" class="s-result-item s-asin">
  <h2 aria-label="Pre-Seasoned Cast Iron Skillet, 10.25 Inches"></h2>
  <span class="a-offscreen">$1.00</span>
</div>
`;

test("amazon selling price comes from the price-to-pay block, not a nearby higher number", () => {
  const parsed = parseAmazonPdp(AMAZON_SALE);
  assert.equal(parsed.price, 14.2);
  assert.equal(parsed.listPrice, 16.7);
  assert.equal(parsed.listLabel, "Typical price");
  assert.equal(parsed.isVerifiedDiscount, true);
  assert.equal(parsed.title, "Amazon Basics Batteries");
  assert.match(parsed.imageUrl, /^https:\/\/m\.media-amazon\.com\/images\/I\/715RL6A12gL\._AC_SL500_\.jpg$/);
});

test("a list price outside the selling-price block does not become the price or a badge", () => {
  const parsed = parseAmazonPdp(AMAZON_PLAIN);
  assert.equal(parsed.price, 17.9);
  assert.equal(parsed.listPrice, null);
  assert.equal(parsed.isVerifiedDiscount, false);
});

test("a was price alone is not a selling price", () => {
  const parsed = parseAmazonPdp(AMAZON_WAS_ONLY);
  assert.equal(parsed.price, null);
  assert.equal(parsed.isVerifiedDiscount, false);
});

test("amazon search links skip sponsored cards and do not keep snippet prices", () => {
  const hits = amazonSearchHits(AMAZON_SEARCH);
  assert.equal(hits.length, 2);
  assert.equal(hits[0].sponsored, true);
  assert.equal(hits[1].asin, "B00006JSUA");
  assert.equal(hits[1].url, "https://www.amazon.com/dp/B00006JSUA");
  assert.equal("price" in hits[1], false);
});

test("target html without a price stays unpriced, and a blocked walmart page is a block", () => {
  const target = parseTargetPdp("<title>OXO Swivel Peeler : Target</title><p>Loading</p>");
  assert.equal(target.price, null);
  assert.equal(target.isVerifiedDiscount, false);
  assert.equal(target.imageUrl, null);
  const walmart = parseWalmartPdp("<title>Robot or human?</title>", "https://www.walmart.com/blocked?url=1");
  assert.equal(walmart.blocked, true);
  assert.equal(walmart.price, null);
});

test("walmart current price is kept and a was price is not treated as the list price", () => {
  const html = `<script id="__NEXT_DATA__" type="application/json">${JSON.stringify({
    props: { pageProps: { product: { name: "Lodge Skillet", priceInfo: { currentPrice: { price: 19.88 }, wasPrice: { price: 40 } } } } },
  })}</script>`;
  const parsed = parseWalmartPdp(html);
  assert.equal(parsed.price, 19.88);
  assert.equal(parsed.listPrice, null);
  assert.equal(parsed.isVerifiedDiscount, false);
});

test("a labeled list price above the selling price can badge a product page", () => {
  const html = `<script type="application/ld+json">${JSON.stringify({
    "@type": "Product",
    name: "Stanley Tape",
    image: "https://images.thdstatic.com/productImages/example.jpg",
    offers: {
      "@type": "Offer",
      price: "24.97",
      priceCurrency: "USD",
      priceSpecification: { "@type": "UnitPriceSpecification", priceType: "https://schema.org/ListPrice", price: "29.97", priceCurrency: "USD" },
    },
  })}</script>`;
  const parsed = parseHomeDepotPdp(html, 200);
  assert.equal(parsed.price, 24.97);
  assert.equal(parsed.listPrice, 29.97);
  assert.equal(parsed.isVerifiedDiscount, true);
  assert.equal(parseHomeDepotPdp("", 403).blocked, true);
});

test("outbound tokens keep a clean product url and add the CheapHub Amazon tag on the way out", () => {
  const clean = "https://www.amazon.com/dp/B00NZ7PTDS";
  const token = encodeOutbound(clean);
  assert.equal(AMAZON_ASSOCIATE_TAG, "cheaphubus-20");
  assert.equal(resolveOutbound(token), "https://www.amazon.com/dp/B00NZ7PTDS?tag=cheaphubus-20");
  assert.equal(Buffer.from(token, "base64url").toString("utf8"), clean);
  assert.equal(cleanProductUrl("https://www.amazon.com/dp/B00NZ7PTDS?tag=invented-20"), null);
  assert.equal(cleanProductUrl("https://evil.example/dp/B00NZ7PTDS"), null);
  assert.equal(cleanProductUrl("https://www.amazon.com/s?k=lodge"), null);
  assert.equal(appendAmazonAssociateTag("https://www.amazon.com/s?k=lodge"), "https://www.amazon.com/s?k=lodge");
  assert.equal(appendAmazonAssociateTag("https://www.target.com/p/oxo-swivel-peeler/-/A-13567836"), "https://www.target.com/p/oxo-swivel-peeler/-/A-13567836");
  assert.equal(appendAmazonAssociateTag("https://www.walmart.com/ip/Lodge-Skillet/123456"), "https://www.walmart.com/ip/Lodge-Skillet/123456");
  assert.equal(appendAmazonAssociateTag("https://www.homedepot.com/p/Stanley-Tape/100052995"), "https://www.homedepot.com/p/Stanley-Tape/100052995");
  assert.equal(goHref({ catalogId: "lodge-8in-cast-iron-skillet-amazon" }), "/go/lodge-8in-cast-iron-skillet-amazon/");
  assert.doesNotMatch(AMAZON_ASSOCIATE_TAG, /luxuryhom06-20|uniqueinamer-20/);
  const cards = readFileSync(new URL("../assets/deal-search.js", import.meta.url), "utf8");
  const catalogCards = readFileSync(new URL("../assets/catalog.js", import.meta.url), "utf8");
  assert.doesNotMatch(cards, /This click uses the Amazon affiliate tag\./);
  assert.doesNotMatch(cards, /Plain product link\. No affiliate tag on this one\./);
  assert.doesNotMatch(cards, /We may earn a commission if you buy through it/);
  assert.doesNotMatch(catalogCards, /We may earn a commission if you buy through it/);
  assert.match(cards, /item\.amazon_associate/);
});

test("catalog matches rank known products first and ignore the remembered price when displaying", async () => {
  const products = loadCatalog();
  const lodge = matchCatalog(["lodge", "cast", "iron", "skillet"], null, products);
  assert.equal(lodge[0].id, "lodge-8in-cast-iron-skillet-amazon");
  assert.ok(lodge.some((product) => product.id === "lodge-10-25-cast-iron-skillet-walmart"));
  const cubes = matchCatalog(["packing", "cubes"], 25, products);
  assert.ok(cubes.some((product) => /packing cubes/i.test(product.title)));

  const catalog = [{
    id: "lodge-8in-cast-iron-skillet-amazon",
    title: "Lodge 8-Inch Pre-Seasoned Cast Iron Skillet",
    merchant: "Amazon",
    product_url: "https://www.amazon.com/dp/B00NZ7PTDS",
    current_price: 999,
    list_or_typical_price: 1200,
    is_verified_discount: true,
    image_url: "https://m.media-amazon.com/images/I/71H-w0pZIuL._AC_SL500_.jpg",
    suggested_affiliate_network: "amazon",
    status: "live",
    priority_rank: 1,
    sort_index: 0,
  }];
  const pages = {
    "https://www.amazon.com/dp/B00NZ7PTDS": { status: 200, url: "https://www.amazon.com/dp/B00NZ7PTDS", text: AMAZON_PLAIN },
    "https://www.amazon.com/s?k=Lodge%20cast%20iron%20skillet": { status: 200, url: "https://www.amazon.com/s?k=Lodge", text: AMAZON_SEARCH },
    "https://www.amazon.com/dp/B00006JSUA": { status: 200, url: "https://www.amazon.com/dp/B00006JSUA", text: AMAZON_SALE },
    "https://www.target.com/s?searchTerm=Lodge%20cast%20iron%20skillet": { status: 200, url: "https://www.target.com/s", text: "<title>Target</title>" },
    "https://www.walmart.com/search?q=Lodge%20cast%20iron%20skillet": { status: 200, url: "https://www.walmart.com/blocked", text: "<title>Robot or human?</title>" },
    "https://www.homedepot.com/s/Lodge%20cast%20iron%20skillet": { status: 403, url: "https://www.homedepot.com/s/Lodge", text: "" },
  };
  const body = await searchDeals("Lodge cast iron skillet", {
    catalog,
    overrides: {},
    budgetMs: 5000,
    fetchPage: async (url) => pages[url] || { status: 0, url, text: "", error: "error" },
  });
  const blob = JSON.stringify(body);
  assert.equal(body.results[0].price, 17.9);
  assert.equal(body.results[0].source, "catalog");
  assert.equal(body.results[0].href, "/go/lodge-8in-cast-iron-skillet-amazon/");
  assert.equal(body.results[0].uses_affiliate, false);
  assert.equal(body.results[0].amazon_associate, true);
  assert.equal(body.results[0].is_verified_discount, false);
  assert.equal(body.results[1].price, 14.2);
  assert.equal(body.results[1].is_verified_discount, true);
  assert.equal(body.results[1].uses_affiliate, false);
  assert.equal(body.results[1].amazon_associate, true);
  assert.equal(body.results[1].href.startsWith("/go/out/?u="), true);
  assert.match(body.link_note, /Amazon affiliate tag/);
  assert.doesNotMatch(blob, /999|1200|15 percent|% off|tag=/);
  assert.ok(body.skipped.some((item) => item.merchant === "Walmart"));
  assert.ok(body.skipped.some((item) => item.merchant === "Home Depot"));
  assert.ok(body.skipped.some((item) => item.merchant === "Target"));
});

test("a saved affiliate override is labeled, and a missing one is not invented", async () => {
  const catalog = [{
    id: "lodge-8in-cast-iron-skillet-amazon",
    title: "Lodge 8-Inch Pre-Seasoned Cast Iron Skillet",
    merchant: "Amazon",
    product_url: "https://www.amazon.com/dp/B00NZ7PTDS",
    current_price: 17.9,
    image_url: "https://m.media-amazon.com/images/I/71H-w0pZIuL._AC_SL500_.jpg",
    suggested_affiliate_network: "amazon",
    status: "live",
  }];
  const body = await searchDeals("Lodge skillet", {
    catalog,
    overrides: { "lodge-8in-cast-iron-skillet-amazon": "https://www.amazon.com/dp/B00NZ7PTDS?tag=saved-20" },
    budgetMs: 3000,
    fetchPage: async (url) => {
      if (url === "https://www.amazon.com/dp/B00NZ7PTDS") {
        return { status: 200, url, text: AMAZON_PLAIN };
      }
      if (url.startsWith("https://www.walmart.com/")) return { status: 200, url, text: "<title>Robot or human?</title>" };
      if (url.startsWith("https://www.homedepot.com/")) return { status: 403, url, text: "" };
      return { status: 200, url, text: "<title>search</title>" };
    },
  });
  assert.equal(body.results[0].uses_affiliate, true);
  assert.equal(body.results[0].amazon_associate, false);
  assert.equal(body.results[0].href, "/go/lodge-8in-cast-iron-skillet-amazon/");
  assert.doesNotMatch(JSON.stringify(body), /tag=/);
  assert.match(body.link_note, /affiliate overrides/);
});

test("a budget phrase keeps cheaper reads in the main list", async () => {
  const catalog = [{
    id: "lodge-8in-cast-iron-skillet-amazon",
    title: "Lodge 8-Inch Pre-Seasoned Cast Iron Skillet",
    merchant: "Amazon",
    product_url: "https://www.amazon.com/dp/B00NZ7PTDS",
    current_price: 17.9,
    image_url: "https://m.media-amazon.com/images/I/71H-w0pZIuL._AC_SL500_.jpg",
    status: "live",
  }];
  const body = await searchDeals("Lodge skillet under $10", {
    catalog,
    overrides: {},
    budgetMs: 3000,
    fetchPage: async (url) => {
      if (url.includes("/dp/")) return { status: 200, url, text: AMAZON_PLAIN };
      if (url.startsWith("https://www.walmart.com/")) return { status: 200, url, text: "<title>Robot or human?</title>" };
      if (url.startsWith("https://www.homedepot.com/")) return { status: 403, url, text: "" };
      return { status: 200, url, text: "<title>search</title>" };
    },
  });
  assert.equal(body.ceiling, 10);
  assert.equal(body.results.length, 0);
  assert.equal(body.over_budget[0].price, 17.9);
});
