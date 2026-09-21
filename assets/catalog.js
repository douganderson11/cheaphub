(function () {
  const CATEGORY_LABELS = {
    home: "Home Savings",
    everyday: "Everyday Shopping",
    travel: "Travel"
  };

  const MODULES = {
    "home-tools-under-25": {
      category: "home",
      ceiling: ["under_25"],
      subcategory: ["hand-tools", "lighting", "fasteners"]
    },
    "kitchen-under-50": {
      category: "home",
      ceiling: ["under_25", "under_50"],
      subcategory: ["kitchen-tools", "cookware", "food-storage"]
    },
    "travel-under-50": {
      category: "travel",
      ceiling: ["under_25", "under_50"]
    },
    "everyday-staples": {
      category: "everyday"
    },
    "practical-gifts-under-25": {
      ceiling: ["under_25"],
      subcategory: [
        "cleaning",
        "cables-chargers",
        "organization",
        "batteries",
        "food-storage",
        "kitchen-tools",
        "drinkware"
      ]
    },
    "desk-under-100": {
      ceiling: ["under_25", "under_50", "under_100"],
      subcategory: ["cables-chargers", "organization", "office-home"]
    },
    "home-comfort-under-100": {
      ceiling: ["under_25", "under_50", "under_100"],
      subcategory: ["lighting", "bath", "cleaning-tools"]
    },
    priority: {
      priorityOnly: true
    },
    all: {}
  };

  const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

  const money = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  });

  function text(el, value) {
    el.textContent = value;
    return el;
  }

  function el(name, className) {
    const node = document.createElement(name);
    if (className) node.className = className;
    return node;
  }

  function formatDate(iso) {
    if (!iso) return "Date pending";
    const parts = iso.split("-").map(Number);
    if (parts.length !== 3 || parts.some((n) => !n && n !== 0)) return iso;
    const [year, month, day] = parts;
    return `${MONTHS[month - 1]} ${day}, ${year}`;
  }

  function formatPrice(product) {
    if (product.current_price == null) return "Check current price";
    return money.format(product.current_price);
  }

  function csv(value) {
    return (value || "")
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function matchesMount(product, rules) {
    if (rules.priorityOnly && !product.priority_rank) return false;
    if (rules.category && product.category !== rules.category) return false;
    if (rules.ceiling && !rules.ceiling.includes(product.ceiling_bucket)) return false;
    if (rules.subcategory && !rules.subcategory.includes(product.subcategory)) return false;
    if (rules.merchant && product.merchant !== rules.merchant) return false;
    return true;
  }

  function rulesFromMount(mount) {
    const moduleName = mount.getAttribute("data-module");
    const base = moduleName && MODULES[moduleName] ? { ...MODULES[moduleName] } : {};
    const category = mount.getAttribute("data-category");
    const ceiling = csv(mount.getAttribute("data-ceiling"));
    const subcategory = csv(mount.getAttribute("data-subcategory"));
    const merchant = mount.getAttribute("data-merchant");
    if (category) base.category = category;
    if (ceiling.length) base.ceiling = ceiling;
    if (subcategory.length) base.subcategory = subcategory;
    if (merchant) base.merchant = merchant;
    if (mount.getAttribute("data-priority") === "true") base.priorityOnly = true;
    return base;
  }

  function sortProducts(products) {
    return products.slice().sort((a, b) => {
      if (a.is_verified_discount !== b.is_verified_discount) {
        return a.is_verified_discount ? -1 : 1;
      }
      const aPriority = a.priority_rank || 999;
      const bPriority = b.priority_rank || 999;
      if (aPriority !== bPriority) return aPriority - bPriority;
      return a.sort_index - b.sort_index;
    });
  }

  function outboundHref(product) {
    return `/go/${product.id}/`;
  }

  function hasPhoto(product) {
    return Boolean(product && product.image_url);
  }

  function renderMedia(product) {
    const link = el("a", "offer-media-link");
    link.href = outboundHref(product);
    link.rel = "sponsored noopener noreferrer";

    const media = el("div", "offer-media");
    const img = document.createElement("img");
    img.src = product.image_url;
    img.alt = product.image_alt || product.title;
    img.loading = "lazy";
    img.decoding = "async";
    img.width = 400;
    img.height = 400;
    img.addEventListener("error", () => {
      const card = link.closest(".offer-card");
      if (card) card.remove();
    });
    media.append(img);
    link.append(media);
    return link;
  }

  function renderCard(product) {
    if (!hasPhoto(product)) return null;
    const card = el("article", "offer-card");
    card.id = product.id;
    card.append(renderMedia(product));

    const kicker = el("span", "kicker");
    text(kicker, `${product.topic} · ${product.merchant}`);
    card.append(kicker);

    if (product.is_verified_discount) {
      card.append(text(el("span", "verified-badge"), "Verified discount"));
    }

    const heading = el("h3");
    const titleLink = el("a");
    titleLink.href = outboundHref(product);
    titleLink.rel = "sponsored noopener noreferrer";
    text(titleLink, product.title);
    heading.append(titleLink);
    card.append(heading);

    const price = el("p", "offer-price");
    text(price, formatPrice(product));
    card.append(price);

    if (product.is_verified_discount && product.list_or_typical_price != null) {
      card.append(text(el("p", "offer-list"), `Merchant list price ${money.format(product.list_or_typical_price)}`));
    }

    card.append(text(el("p", "offer-basis"), product.discount_basis));
    card.append(text(el("p"), product.short_pitch));
    card.append(text(el("p", "offer-restrictions"), `Restrictions: ${product.restrictions_notes}`));
    card.append(text(el("p", "checked"), `Last checked: ${formatDate(product.last_checked_date)}`));

    const button = el("a", "button");
    button.href = outboundHref(product);
    button.rel = "sponsored noopener noreferrer";
    text(button, product.current_price == null ? `Check current price at ${product.merchant}` : `See at ${product.merchant}`);
    card.append(button);

    card.append(text(el("p", "disclosure"), "Affiliate link. We may earn a commission if you buy through it."));
    return card;
  }

  function emptyState(mount) {
    const note = el("div", "status-panel catalog-empty");
    note.append(text(el("p"), "No catalog items match this view yet."));
    mount.replaceChildren(note);
  }

  function renderGrid(mount, products) {
    if (!products.length) {
      emptyState(mount);
      return;
    }
    const limit = Number(mount.getAttribute("data-limit") || 0);
    const shown = limit > 0 ? products.slice(0, limit) : products;
    const grid = el("div", "offer-grid");
    shown.forEach((product) => {
      const card = renderCard(product);
      if (card) grid.append(card);
    });
    const nodes = [grid];
    if (limit > 0 && products.length > shown.length) {
      const more = el("p", "catalog-more");
      const link = el("a", "text-link");
      link.href = mount.getAttribute("data-more-href") || "/deals/";
      text(link, `See all ${products.length} matching products`);
      more.append(link);
      nodes.push(more);
    }
    mount.replaceChildren(...nodes);
  }

  function uniqueValues(products, key) {
    return [...new Set(products.map((product) => product[key]))].sort();
  }

  function applyInteractiveFilter(mount, products) {
    const kind = mount.getAttribute("data-filter");
    if (!kind) {
      renderGrid(mount, products);
      return;
    }

    const params = new URLSearchParams(location.search);
    const startValue = params.get(kind) || "all";
    const wrap = el("div", "catalog-filter-wrap");
    const controls = el("div", "filter-controls");
    const id = `catalog-filter-${kind}`;
    const label = el("label");
    label.setAttribute("for", id);
    text(label, kind === "merchant" ? "Merchant" : "Category");
    const select = el("select");
    select.id = id;

    const options = [["all", kind === "merchant" ? "All merchants" : "All categories"]];
    if (kind === "category") {
      uniqueValues(products, "category").forEach((value) => {
        options.push([value, CATEGORY_LABELS[value] || value]);
      });
    } else if (kind === "merchant") {
      uniqueValues(products, "merchant").forEach((value) => options.push([value, value]));
    }
    options.forEach(([value, labelText]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = labelText;
      select.append(option);
    });
    if (options.some(([value]) => value === startValue)) select.value = startValue;

    const gridHost = el("div");
    const apply = () => {
      const value = select.value;
      const filtered = products.filter((product) => value === "all" || product[kind] === value);
      renderGrid(gridHost, filtered);
    };
    select.addEventListener("change", apply);
    controls.append(label, select);
    wrap.append(controls, gridHost);
    mount.replaceChildren(wrap);
    apply();
  }

  function hashScroll() {
    const id = location.hash.replace("#", "");
    if (!id) return;
    const target = document.getElementById(id);
    if (target) target.scrollIntoView({ block: "start" });
  }

  function init(data) {
    const products = (data.products || []).filter(hasPhoto);
    document.querySelectorAll("[data-catalog]").forEach((mount) => {
      const matched = sortProducts(products.filter((product) => matchesMount(product, rulesFromMount(mount))));
      applyInteractiveFilter(mount, matched);
    });
    if (location.hash) hashScroll();
  }

  if (!document.querySelector("[data-catalog]")) return;

  fetch("/assets/catalog.json")
    .then((response) => {
      if (!response.ok) throw new Error("catalog unavailable");
      return response.json();
    })
    .then(init)
    .catch(() => {
      document.querySelectorAll("[data-catalog]").forEach((mount) => {
        const note = el("div", "status-panel catalog-empty");
        note.append(text(el("p"), "The product catalog could not be loaded. Refresh, or browse the buying guides."));
        mount.replaceChildren(note);
      });
    });
})();
