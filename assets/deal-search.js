(function () {
  const form = document.querySelector("#deal-search-form");
  const input = document.querySelector("#deal-q");
  const status = document.querySelector("#deal-status");
  const note = document.querySelector("#deal-note");
  const results = document.querySelector("#deal-results");
  const over = document.querySelector("#deal-over");
  const overList = document.querySelector("#deal-over-list");
  const unchecked = document.querySelector("#deal-unchecked");
  const uncheckedList = document.querySelector("#deal-unchecked-list");
  const skipped = document.querySelector("#deal-skipped");
  const skippedList = document.querySelector("#deal-skipped-list");
  if (!form || !input || !status) return;

  const IMAGE_HOSTS = new Set([
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "target.scene7.com",
    "images.thdstatic.com",
    "images.homedepot-static.com",
    "i5.walmartimages.com",
    "i.walmartimages.com"
  ]);

  const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

  function el(name, className) {
    const node = document.createElement(name);
    if (className) node.className = className;
    return node;
  }

  function text(node, value) {
    node.textContent = value;
    return node;
  }

  function safeHref(href) {
    if (typeof href !== "string") return null;
    if (/^\/go\/[a-z0-9-]+\/$/.test(href)) return href;
    if (/^\/go\/out\/\?u=[A-Za-z0-9_-]+$/.test(href)) return href;
    return null;
  }

  function safeImage(url) {
    if (!url || typeof url !== "string") return null;
    if (url.startsWith("/assets/products/")) return url;
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "https:" || !IMAGE_HOSTS.has(parsed.hostname)) return null;
      return url;
    } catch {
      return null;
    }
  }

  function linkRel(item) {
    return item.uses_affiliate || item.amazon_associate
      ? "sponsored noopener noreferrer"
      : "noopener noreferrer";
  }

  function card(item, priced) {
    const href = safeHref(item.href);
    if (!href || !item.title || !item.merchant) return null;
    const article = el("article", "offer-card");
    const image = safeImage(item.image_url);
    if (image) {
      const link = el("a", "offer-media-link");
      link.href = href;
      link.rel = linkRel(item);
      const media = el("div", "offer-media");
      const img = document.createElement("img");
      img.src = image;
      img.alt = item.image_alt || item.title;
      img.loading = "lazy";
      img.width = 400;
      img.height = 400;
      media.append(img);
      link.append(media);
      article.append(link);
    }

    const kicker = el("span", "kicker");
    kicker.textContent = item.source === "catalog"
      ? `${item.merchant} · In the CheapHub catalog`
      : item.merchant;
    article.append(kicker);

    if (priced && item.is_verified_discount && item.list_price > item.price) {
      article.append(text(el("span", "verified-badge"), "Verified discount"));
    }

    const heading = el("h3");
    const titleLink = el("a");
    titleLink.href = href;
    titleLink.rel = linkRel(item);
    titleLink.textContent = item.title;
    heading.append(titleLink);
    article.append(heading);

    if (priced && typeof item.price === "number") {
      article.append(text(el("p", "offer-price"), money.format(item.price)));
      if (item.is_verified_discount && typeof item.list_price === "number" && item.list_price > item.price) {
        const label = item.list_label || "List price";
        article.append(text(el("p", "offer-list"), `${label} ${money.format(item.list_price)}`));
      }
      if (item.discount_basis) article.append(text(el("p", "offer-basis"), item.discount_basis));
    } else {
      article.append(text(el("p", "offer-basis"), "Price not read"));
      if (item.reason) article.append(text(el("p"), item.reason));
    }

    const button = el("a", "button");
    button.href = href;
    button.rel = linkRel(item);
    button.textContent = priced ? `See at ${item.merchant}` : `Open the ${item.merchant} page`;
    article.append(button);
    return article;
  }

  function fill(section, mount, items, priced) {
    mount.replaceChildren();
    if (!items || !items.length) {
      section.hidden = true;
      return;
    }
    const grid = el("div", "offer-grid");
    items.forEach((item) => {
      const node = card(item, priced);
      if (node) grid.append(node);
    });
    if (!grid.childElementCount) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    mount.append(grid);
  }

  function render(body) {
    const seconds = Math.max(1, Math.round((body.took_ms || 0) / 1000));
    const pricedCount = (body.results || []).length;
    const query = body.query || input.value;
    if (body.error) {
      status.textContent = body.error;
    } else if (!pricedCount && !(body.over_budget || []).length && !(body.unchecked || []).length) {
      status.textContent = `No price came back for “${query}”. Finished in ${seconds} seconds.`;
    } else {
      const noun = pricedCount === 1 ? "price" : "prices";
      status.textContent = `${pricedCount} ${noun} read for “${query}”. Finished in ${seconds} seconds.`;
    }
    note.textContent = body.link_note || "";
    fill(results, results, body.results || [], true);
    fill(over, overList, body.over_budget || [], true);
    fill(unchecked, uncheckedList, body.unchecked || [], false);

    skippedList.replaceChildren();
    const misses = body.skipped || [];
    if (!misses.length) {
      skipped.hidden = true;
      return;
    }
    skipped.hidden = false;
    const list = el("ul", "skipped-list");
    misses.forEach((item) => {
      const li = el("li");
      li.textContent = item.reason || `${item.merchant} was skipped.`;
      list.append(li);
    });
    skippedList.append(list);
  }

  async function run(query) {
    status.textContent = "Opening the product pages now. This usually takes a few seconds.";
    note.textContent = "";
    results.replaceChildren();
    overList.replaceChildren();
    uncheckedList.replaceChildren();
    skippedList.replaceChildren();
    results.hidden = true;
    over.hidden = true;
    unchecked.hidden = true;
    skipped.hidden = true;
    const button = form.querySelector("button");
    if (button) button.disabled = true;
    try {
      const response = await fetch(`/api/deal-search?q=${encodeURIComponent(query)}`, {
        headers: { accept: "application/json" }
      });
      const body = await response.json();
      render(body);
    } catch {
      status.textContent = "The price check didn't finish. Try again in a moment.";
    } finally {
      if (button) button.disabled = false;
    }
  }

  const initial = new URLSearchParams(location.search).get("q");
  if (initial) {
    input.value = initial;
    run(initial.trim());
  }
})();
