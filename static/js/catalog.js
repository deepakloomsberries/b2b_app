const _settings = window.appSettings || {};
const SHOW_STOCK = _settings.show_stock !== false;
const LOW_STOCK_THRESHOLD = typeof _settings.low_stock_threshold === 'number'
    ? _settings.low_stock_threshold
    : 5;
const CURRENCY = typeof _settings.currency_symbol === 'string'
    ? _settings.currency_symbol
    : 'SAR';

const productList = document.getElementById('product-list');
let productCards = [];
const productData = Array.isArray(window.catalogProducts)
    ? window.catalogProducts
    : [];
const productIndex = new Map(
    productData.map((product) => [String(product.sku), product])
);
const categoryButtons = Array.from(document.querySelectorAll('.category-chip'));
const subcategoryButtons = Array.from(
    document.querySelectorAll('.subcategory-chip')
);
const subsubcategoryButtons = Array.from(
    document.querySelectorAll('.subsubcategory-chip')
);
const searchInput = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search');
const inStockToggle = document.getElementById('in-stock-toggle');
const sortSelect = document.getElementById('sort-select');
const totalSkusEl = document.getElementById('total-skus');
const totalQtyEl = document.getElementById('total-qty');
const totalAmountEl = document.getElementById('total-amount');
const placeOrderBtn = document.getElementById('place-order-btn');
const saveDraftBtn = document.getElementById('save-draft-btn');
const clearDraftBtn = document.getElementById('clear-draft-btn');
const itemsJsonInput = document.getElementById('items-json');
const customerIdInput = document.querySelector('input[name="customer_id"]');
const clearDraftModal = document.getElementById('clear-draft-modal');
const confirmClearDraftBtn = document.getElementById('confirm-clear-draft');
const cancelClearDraftBtn = document.getElementById('cancel-clear-draft');
const cartCount = document.getElementById('cart-count');
const cartButtons = Array.from(document.querySelectorAll('.cart-button'));
const openSearchBtn = document.getElementById('open-search');
const searchDialog = document.getElementById('search-dialog');
const closeSearchBtn = document.getElementById('close-search');
const searchModalInput = document.getElementById('search-modal-input');
const clearSearchModalBtn = document.getElementById('clear-search-modal');
const searchResults = document.getElementById('search-results');
const categoryHierarchyDialog = document.getElementById(
    'category-hierarchy-dialog'
);
const openCategoryHierarchyBtn = document.getElementById(
    'open-category-hierarchy'
);
const closeCategoryHierarchyBtn = document.getElementById(
    'close-category-hierarchy'
);
const categoryHierarchyTitle = document.getElementById(
    'category-hierarchy-title'
);
const categoryHierarchyBody = document.getElementById(
    'category-hierarchy-body'
);
const pdpDialog = document.getElementById('pdp-dialog');
const closePdpBtn = document.getElementById('close-pdp');
const pdpImages = document.getElementById('pdp-images');
const pdpTitle = document.getElementById('pdp-title');
const pdpPrice = document.getElementById('pdp-price');
const pdpSku = document.getElementById('pdp-sku');
const pdpStock = document.getElementById('pdp-stock');
const pdpStockStatus = document.getElementById('pdp-stock-status');
const pdpAddBtn = document.getElementById('pdp-add');
const pdpCartCount = document.getElementById('pdp-cart-count');
const cartFooter = document.getElementById('cart-footer');
const toggleSubcategoriesBtn = document.getElementById('toggle-subcategories');
const subcategoryScroll = document.getElementById('subcategory-scroll');
const toggleSubSubcategoriesBtn = document.getElementById('toggle-subsubcategories');
const subsubcategoryScroll = document.getElementById('subsubcategory-scroll');

let activeCategory = categoryButtons[0]?.dataset.category || '';
let activeSubcategory =
    subcategoryButtons.find(
        (button) => button.dataset.category === activeCategory
    )?.dataset.subcategory || '';
let activeSubSubcategory =
    subsubcategoryButtons.find(
        (button) => button.dataset.subcategory === activeSubcategory
    )?.dataset.subsubcategory || '';
let expandedHierarchyCategories = new Set();

const cart = {};
const cartStoragePrefix = 'sales_cart_';
let searchTimeout;
let visibleCount = 10;
let activePdpCard = null;
const renderBatchSize = 20;
const pdpState = {
    images: [],
    activeIndex: 0,
};
let fullscreenOverlay = null;
let fullscreenImage = null;
let fullscreenCloseBtn = null;

const getCartStorageKey = () => {
    const customerId = customerIdInput?.value;
    return customerId ? `${cartStoragePrefix}${customerId}` : null;
};

const persistCart = () => {
    const key = getCartStorageKey();
    if (!key || !window.localStorage) {
        return;
    }
    const payload = Object.entries(cart)
        .filter(([, qty]) => Number.isFinite(qty) && qty > 0)
        .map(([sku, qty]) => ({ sku, qty }));
    window.localStorage.setItem(key, JSON.stringify(payload));
};

const updateBodyScrollLock = () => {
    const openModal = document.querySelector('.modal[open], .modal.is-open');
    const isFullscreenOpen = fullscreenOverlay && !fullscreenOverlay.hidden;
    document.body.classList.toggle('no-scroll', Boolean(openModal || isFullscreenOpen));
};

const openDialog = (dialog) => {
    if (!dialog) {
        return;
    }
    if (typeof dialog.showModal === 'function') {
        dialog.showModal();
    } else {
        dialog.classList.add('is-open');
        dialog.setAttribute('open', '');
    }
    updateBodyScrollLock();
};

const closeDialog = (dialog) => {
    if (!dialog) {
        return;
    }
    if (typeof dialog.close === 'function') {
        dialog.close();
    } else {
        dialog.classList.remove('is-open');
        dialog.removeAttribute('open');
    }
    updateBodyScrollLock();
};

const setActiveCategory = (category) => {
    activeCategory = category;
    categoryButtons.forEach((button) => {
        button.classList.toggle(
            'active',
            button.dataset.category === activeCategory
        );
    });
    updateSubcategoryOptions();
    applyFilters();
};

const setActiveSubcategory = (subcategory) => {
    activeSubcategory = subcategory;
    subcategoryButtons.forEach((button) => {
        button.classList.toggle(
            'active',
            button.dataset.subcategory === activeSubcategory &&
                button.dataset.category === activeCategory
        );
    });
    updateSubSubcategoryOptions();
    applyFilters();
};

const setActiveSubSubcategory = (subsubcategory, { silent = false } = {}) => {
    activeSubSubcategory = subsubcategory;
    subsubcategoryButtons.forEach((button) => {
        button.classList.toggle(
            'active',
            button.dataset.subsubcategory === activeSubSubcategory &&
                button.dataset.subcategory === activeSubcategory
        );
    });
    if (!silent) {
        applyFilters();
    }
};

const getUniqueValues = (buttons, key, filterFn) =>
    Array.from(
        new Set(
            buttons
                .filter(filterFn)
                .map((button) => button.dataset[key])
                .filter(Boolean)
        )
    );

const buildHierarchyData = () =>
    categoryButtons
        .map((button) => button.dataset.category)
        .filter(Boolean)
        .map((category) => {
            const subcategories = getUniqueValues(
                subcategoryButtons,
                'subcategory',
                (button) => button.dataset.category === category
            );
            const subcategoryItems = subcategories.map((subcategory) => ({
                name: subcategory,
                subsubcategories: getUniqueValues(
                    subsubcategoryButtons,
                    'subsubcategory',
                    (button) => button.dataset.subcategory === subcategory
                ),
            }));
            return { category, subcategories: subcategoryItems };
        });

const renderCategoryHierarchy = () => {
    if (!categoryHierarchyBody) {
        return;
    }
    categoryHierarchyBody.innerHTML = '';
    categoryHierarchyTitle.textContent = 'Categories';

    const data = buildHierarchyData();
    data.forEach(({ category, subcategories }) => {
        const row = document.createElement('div');
        row.className = 'category-hierarchy-row';

        const labelButton = document.createElement('button');
        labelButton.type = 'button';
        labelButton.className = 'category-hierarchy-label';
        labelButton.textContent = category;
        labelButton.classList.toggle('active', category === activeCategory);
        labelButton.addEventListener('click', () => {
            setActiveCategory(category);
            if (subcategories.length) {
                expandedHierarchyCategories.add(category);
                renderCategoryHierarchy();
                return;
            }
            closeDialog(categoryHierarchyDialog);
        });

        const toggleButton = document.createElement('button');
        toggleButton.type = 'button';
        toggleButton.className = 'category-hierarchy-toggle';
        const isExpanded = expandedHierarchyCategories.has(category);
        toggleButton.textContent = isExpanded ? '−' : '+';
        toggleButton.disabled = subcategories.length === 0;
        toggleButton.addEventListener('click', () => {
            if (expandedHierarchyCategories.has(category)) {
                expandedHierarchyCategories.delete(category);
            } else {
                expandedHierarchyCategories.add(category);
            }
            renderCategoryHierarchy();
        });

        row.appendChild(labelButton);
        row.appendChild(toggleButton);
        categoryHierarchyBody.appendChild(row);

        if (subcategories.length && expandedHierarchyCategories.has(category)) {
            const childList = document.createElement('div');
            childList.className = 'category-hierarchy-children';

            subcategories.forEach(({ name, subsubcategories }) => {
                const subButton = document.createElement('button');
                subButton.type = 'button';
                subButton.className = 'category-hierarchy-subitem';
                subButton.textContent = name;
                subButton.classList.toggle(
                    'active',
                    name === activeSubcategory && category === activeCategory
                );
                subButton.addEventListener('click', () => {
                    setActiveCategory(category);
                    setActiveSubcategory(name);
                    if (!subsubcategories.length) {
                        closeDialog(categoryHierarchyDialog);
                    }
                });
                childList.appendChild(subButton);

                if (subsubcategories.length) {
                    const subChildList = document.createElement('div');
                    subChildList.className =
                        'category-hierarchy-children category-hierarchy-subchildren';
                    subsubcategories.forEach((subsub) => {
                        const subSubButton = document.createElement('button');
                        subSubButton.type = 'button';
                        subSubButton.className = 'category-hierarchy-subitem subsub';
                        subSubButton.textContent = subsub;
                        subSubButton.classList.toggle(
                            'active',
                            subsub === activeSubSubcategory &&
                                name === activeSubcategory &&
                                category === activeCategory
                        );
                        subSubButton.addEventListener('click', () => {
                            setActiveCategory(category);
                            setActiveSubcategory(name);
                            setActiveSubSubcategory(subsub);
                            closeDialog(categoryHierarchyDialog);
                        });
                        subChildList.appendChild(subSubButton);
                    });
                    childList.appendChild(subChildList);
                }
            });

            categoryHierarchyBody.appendChild(childList);
        }
    });
};

const escapeHtml = (value) =>
    String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

const createProductCard = (product) => {
    const images = [
        product.image_url_1,
        product.image_url_2,
        product.image_url_3,
        product.image_url_4,
        product.image_url,
    ].filter(Boolean);
    const stockQty = parseInt(product.available_qty || 0, 10);
    const reservedQty = parseInt(product.reserved_qty || 0, 10);
    const stockClass =
        stockQty <= 0 ? 'out-stock' : stockQty <= LOW_STOCK_THRESHOLD ? 'low-stock' : 'in-stock';
    const priceBase = product.price ?? product.price_credit ?? 0;
    const priceCash = product.price_cash ?? priceBase;
    const priceValue = priceBase;
    const safeTitle = escapeHtml(product.title || '');
    const safeSku = escapeHtml(product.sku || '');
    const safeMfr = escapeHtml(product.mfr_no || '—');
    const safeImages = images.map((img) => escapeHtml(img));
    const card = document.createElement('div');
    card.className = 'product-card';
    card.dataset.sku = product.sku || '';
    card.dataset.title = (product.title || '').toLowerCase();
    card.dataset.category = product.category || '';
    card.dataset.subcategory = product.subcategory || '';
    card.dataset.subsubcategory = product.sub_subcategory || '';
    card.dataset.image = images[0] || '';
    card.dataset.images = JSON.stringify(images);
    card.dataset.price = priceValue;
    card.dataset.priceBase = priceBase;
    card.dataset.priceCash = priceCash;
    card.dataset.stock = stockQty;
    card.dataset.reserved = reservedQty;
    card.dataset.sequence = product.sort_order || '';
    const showCashPrice =
        priceCash !== null &&
        priceCash !== undefined &&
        Math.abs(parseFloat(priceCash) - parseFloat(priceBase || 0)) >= 0.005;
    const stockLineParts = [];
    if (SHOW_STOCK) {
        stockLineParts.push(`${stockQty} available`);
        if (reservedQty > 0) {
            stockLineParts.push(`${reservedQty} reserved`);
        }
    }

    card.innerHTML = `
        <div class="product-image">
            ${
                safeImages.length
                    ? `
                        <img src="${safeImages[0]}" alt="${safeTitle}" loading="lazy" decoding="async" width="160" height="160">
                    `
                    : '<div class="placeholder"><span aria-hidden="true">📦</span></div>'
            }
        </div>
        <div class="product-info">
            <div class="product-title-row">
                <div class="product-title">${safeTitle}</div>
                ${SHOW_STOCK ? `<span class="stock-badge ${stockClass}">
                    ${
                        stockQty <= 0
                            ? 'Out of stock'
                            : stockQty <= LOW_STOCK_THRESHOLD
                              ? 'Low stock'
                              : 'In stock'
                    }
                </span>` : ''}
            </div>
            <div class="product-sku">SKU ${safeSku}${safeMfr && safeMfr !== '—' ? ` &middot; MFR ${safeMfr}` : ''}</div>
            <div class="product-price-row">
                <span class="product-price-main">${CURRENCY} ${parseFloat(priceBase || 0).toFixed(2)}</span>
                ${showCashPrice ? `<span class="product-price-alt">Cash ${CURRENCY} ${parseFloat(priceCash || 0).toFixed(2)}</span>` : ''}
            </div>
            ${stockLineParts.length ? `<div class="product-stock-line">${stockLineParts.join(' &middot; ')}</div>` : ''}
            <div class="product-actions">
                <button type="button" class="add-to-cart" ${
                    stockQty <= 0 ? 'disabled' : ''
                }>Add to Cart</button>
                <div class="qty-control">
                    <button type="button" class="qty-btn" data-action="minus" ${
                        stockQty <= 0 ? 'disabled' : ''
                    }>-</button>
                    <input type="number" min="0" max="${stockQty}" value="0" class="qty-input" ${
                        stockQty <= 0 ? 'disabled' : ''
                    }>
                    <button type="button" class="qty-btn" data-action="plus" ${
                        stockQty <= 0 ? 'disabled' : ''
                    }>+</button>
                </div>
            </div>
        </div>
    `;
    return card;
};

const setVisibleCards = (cards) => {
    cards.forEach((card, index) => {
        card.hidden = index >= visibleCount;
    });
};

const updateTotals = () => {
    const skus = Object.keys(cart).filter((sku) => cart[sku] > 0);
    const totalQty = skus.reduce((sum, sku) => sum + cart[sku], 0);
    const totalAmount = skus.reduce((sum, sku) => {
        const card = productCards.find((item) => item.dataset.sku === sku);
        const price = card
            ? parseFloat(card.dataset.price || '0')
            : parseFloat(
                  productIndex.get(sku)?.price_credit ??
                      productIndex.get(sku)?.price ??
                      0
              );
        return sum + price * cart[sku];
    }, 0);
    totalSkusEl.textContent = skus.length;
    totalQtyEl.textContent = totalQty;
    totalAmountEl.textContent = totalAmount.toFixed(2);
    if (cartCount) {
        cartCount.textContent = totalQty;
    }
    if (pdpCartCount) {
        pdpCartCount.textContent = totalQty;
    }
    placeOrderBtn.disabled = totalQty === 0;
    itemsJsonInput.value = JSON.stringify(
        skus.map((sku) => ({ sku, qty: cart[sku] }))
    );
    persistCart();
};

const registerProductCard = (card) => {
    const sku = card.dataset.sku;
    const input = card.querySelector('.qty-input');
    const buttons = card.querySelectorAll('.qty-btn');
    const addToCartBtn = card.querySelector('.add-to-cart');
    const availableQty = parseInt(card.dataset.stock || '0', 10);

    if (!(sku in cart)) {
        cart[sku] = 0;
    }

    const updateAvailability = (qty) => {
        const disablePlus = qty >= availableQty;
        buttons.forEach((btn) => {
            if (btn.dataset.action === 'plus') {
                btn.disabled = disablePlus || availableQty <= 0;
            }
        });
        if (addToCartBtn) {
            addToCartBtn.disabled = disablePlus || availableQty <= 0;
        }
    };

    const setValue = (value, options = {}) => {
        const qty = Math.max(0, Math.min(value, availableQty));
        if (input) {
            input.value = qty;
        }
        cart[sku] = qty;
        updateAvailability(qty);
        if (!options.silent) {
            updateTotals();
        }
    };

    buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
            if (btn.disabled) {
                return;
            }
            const action = btn.dataset.action;
            const current = parseInt(input?.value || '0', 10);
            if (action === 'plus') {
                setValue(current + 1);
            } else {
                setValue(current - 1);
            }
        });
    });

    input?.addEventListener('change', () => {
        const value = parseInt(input.value || '0', 10);
        setValue(Number.isNaN(value) ? 0 : value);
    });

    addToCartBtn?.addEventListener('click', () => {
        const current = parseInt(input?.value || '0', 10);
        setValue(current + 1);
    });

    card.addEventListener('click', (event) => {
        const target = event.target;
        if (
            target.closest('button') ||
            target.closest('input') ||
            target.closest('a')
        ) {
            return;
        }
        openPdp(card);
    });

    const initialQty = cart[sku] || 0;
    if (input) {
        setValue(initialQty, { silent: true });
    } else {
        updateAvailability(initialQty);
    }
};

const renderProducts = () => {
    if (!productList) {
        return;
    }
    if (!productData.length) {
        productList.innerHTML =
            '<div class="empty-state">No products available.</div>';
        return;
    }

    let renderIndex = 0;

    const appendBatch = () => {
        const fragment = document.createDocumentFragment();
        const newCards = [];
        for (
            let i = 0;
            i < renderBatchSize && renderIndex < productData.length;
            i += 1, renderIndex += 1
        ) {
            const card = createProductCard(productData[renderIndex]);
            fragment.appendChild(card);
            newCards.push(card);
            productCards.push(card);
        }
        productList.appendChild(fragment);
        newCards.forEach(registerProductCard);
        applyFilters();

        if (renderIndex < productData.length) {
            if ('requestIdleCallback' in window) {
                requestIdleCallback(appendBatch);
            } else {
                setTimeout(appendBatch, 0);
            }
        } else {
            sortProducts();
            applyFilters();
            updateTotals();
        }
    };

    appendBatch();
};

const applyFilters = () => {
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const requireStock = inStockToggle.checked;
    const subcategory = activeSubcategory;
    const subSubcategory = activeSubSubcategory;
    const matchingCards = [];

    productCards.forEach((card) => {
        const title = card.dataset.title;
        const sku = card.dataset.sku.toLowerCase();
        const category = card.dataset.category;
        const subcategoryValue = card.dataset.subcategory;
        const subSubcategoryValue = card.dataset.subsubcategory;
        const stockQty = parseInt(card.dataset.stock || '0', 10);

        const matchesCategory =
            !activeCategory || category === activeCategory;
        const matchesSubcategory =
            !subcategory || subcategoryValue === subcategory;
        const matchesSubSubcategory =
            !subSubcategory || subSubcategoryValue === subSubcategory;
        const matchesSearch =
            title.includes(searchTerm) || sku.includes(searchTerm);
        const matchesStock = !requireStock || stockQty > 0;

        const matches =
            matchesCategory &&
            matchesSubcategory &&
            matchesSubSubcategory &&
            matchesSearch &&
            matchesStock;
        card.style.display = matches ? '' : 'none';
        if (matches) {
            matchingCards.push(card);
        }
    });

    visibleCount = 10;
    setVisibleCards(matchingCards);
};

const updateSubcategoryOptions = () => {
    subcategoryButtons.forEach((button) => {
        button.hidden = button.dataset.category !== activeCategory;
        button.setAttribute(
            'aria-hidden',
            button.hidden ? 'true' : 'false'
        );
    });

    const firstVisible = subcategoryButtons.find((button) => !button.hidden);
    if (!firstVisible) {
        activeSubcategory = '';
        return;
    }

    if (
        !subcategoryButtons.some(
            (button) =>
                button.dataset.subcategory === activeSubcategory &&
                !button.hidden
        )
    ) {
        activeSubcategory = firstVisible.dataset.subcategory;
    }

    subcategoryButtons.forEach((button) => {
        button.classList.toggle(
            'active',
            button.dataset.subcategory === activeSubcategory && !button.hidden
        );
    });

    updateSubSubcategoryOptions();
};

const updateSubSubcategoryOptions = () => {
    if (!subsubcategoryButtons.length) {
        activeSubSubcategory = '';
        return;
    }
    subsubcategoryButtons.forEach((button) => {
        button.hidden = button.dataset.subcategory !== activeSubcategory;
        button.setAttribute(
            'aria-hidden',
            button.hidden ? 'true' : 'false'
        );
    });

    const firstVisible = subsubcategoryButtons.find((button) => !button.hidden);
    if (!firstVisible) {
        activeSubSubcategory = '';
        return;
    }

    if (
        !subsubcategoryButtons.some(
            (button) =>
                button.dataset.subsubcategory === activeSubSubcategory &&
                !button.hidden
        )
    ) {
        activeSubSubcategory = firstVisible.dataset.subsubcategory;
    }

    setActiveSubSubcategory(activeSubSubcategory, { silent: true });
};

const sortProducts = () => {
    const value = sortSelect.value;
    const sorted = [...productCards].sort((a, b) => {
        if (value === 'sequence') {
            const aSeq = parseInt(a.dataset.sequence || '999999', 10);
            const bSeq = parseInt(b.dataset.sequence || '999999', 10);
            return aSeq - bSeq;
        }
        if (value === 'sku') {
            return a.dataset.sku.localeCompare(b.dataset.sku);
        }
        if (value === 'price') {
            return parseFloat(a.dataset.price) - parseFloat(b.dataset.price);
        }
        if (value === 'stock') {
            return parseInt(b.dataset.stock, 10) - parseInt(a.dataset.stock, 10);
        }
        return a.dataset.title.localeCompare(b.dataset.title);
    });
    const list = document.getElementById('product-list');
    sorted.forEach((card) => list.appendChild(card));
    productCards = sorted;
    applyFilters();
};

const ensureFullscreenOverlay = () => {
    if (fullscreenOverlay) {
        return;
    }
    fullscreenOverlay = document.createElement('div');
    fullscreenOverlay.className = 'pdp-fullscreen';
    fullscreenOverlay.hidden = true;
    fullscreenOverlay.innerHTML = `
        <button type="button" class="exit-fullscreen" aria-label="Exit fullscreen">Exit fullscreen ✕</button>
        <img src="" alt="Fullscreen product image">
    `;
    const overlayParent = pdpDialog || document.body;
    overlayParent.appendChild(fullscreenOverlay);
    fullscreenImage = fullscreenOverlay.querySelector('img');
    fullscreenCloseBtn = fullscreenOverlay.querySelector('.exit-fullscreen');
    fullscreenOverlay.addEventListener('click', (event) => {
        if (event.target === fullscreenOverlay) {
            closeFullscreen();
        }
    });
    fullscreenCloseBtn.addEventListener('click', closeFullscreen);
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && fullscreenOverlay && !fullscreenOverlay.hidden) {
            closeFullscreen();
        }
    });
};

const setActivePdpImage = (index, { scrollIntoView = true } = {}) => {
    if (!pdpState.images.length) {
        return;
    }
    const nextIndex = Math.min(
        Math.max(index, 0),
        pdpState.images.length - 1
    );
    pdpState.activeIndex = nextIndex;
    const mainImage = pdpImages?.querySelector('.pdp-main-image img');
    if (mainImage) {
        mainImage.src = pdpState.images[nextIndex];
    }
    const thumbs = Array.from(pdpImages?.querySelectorAll('.pdp-thumb') || []);
    thumbs.forEach((thumb, thumbIndex) => {
        thumb.classList.toggle('active', thumbIndex === nextIndex);
        if (thumbIndex === nextIndex && scrollIntoView) {
            thumb.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest',
                inline: 'center',
            });
        }
    });
};

const openFullscreen = (index = pdpState.activeIndex) => {
    if (!pdpState.images.length) {
        return;
    }
    ensureFullscreenOverlay();
    setActivePdpImage(index, { scrollIntoView: false });
    if (fullscreenImage) {
        fullscreenImage.src = pdpState.images[pdpState.activeIndex];
    }
    fullscreenOverlay.hidden = false;
    updateBodyScrollLock();
};

const closeFullscreen = () => {
    if (!fullscreenOverlay) {
        return;
    }
    fullscreenOverlay.hidden = true;
    updateBodyScrollLock();
};

const buildImageGallery = (images = []) => {
    pdpImages.innerHTML = '';
    const limitedImages = images.slice(0, 4);
    pdpState.images = limitedImages;
    pdpState.activeIndex = 0;
    const main = document.createElement('div');
    main.className = 'pdp-main-image';
    if (!limitedImages.length) {
        const placeholder = document.createElement('div');
        placeholder.className = 'placeholder';
        placeholder.innerHTML = '<span aria-hidden="true">📦</span>';
        main.appendChild(placeholder);
        pdpImages.appendChild(main);
        return;
    }
    const mainImage = document.createElement('img');
    mainImage.src = limitedImages[0];
    mainImage.alt = pdpTitle?.textContent || 'Product image';
    main.appendChild(mainImage);
    main.addEventListener('click', () => openFullscreen(pdpState.activeIndex));
    const thumbs = document.createElement('div');
    thumbs.className = 'pdp-thumbnails';
    limitedImages.forEach((img, index) => {
        const thumbButton = document.createElement('button');
        thumbButton.type = 'button';
        thumbButton.className = 'pdp-thumb';
        if (index === 0) {
            thumbButton.classList.add('active');
        }
        const thumbImage = document.createElement('img');
        thumbImage.src = img;
        thumbImage.alt = pdpTitle?.textContent || 'Product thumbnail';
        thumbButton.appendChild(thumbImage);
        thumbButton.addEventListener('click', () => {
            setActivePdpImage(index);
            openFullscreen(index);
        });
        thumbs.appendChild(thumbButton);
    });
    pdpImages.appendChild(main);
    pdpImages.appendChild(thumbs);
};

const openPdp = (card) => {
    if (!pdpDialog) {
        return;
    }
    const images = JSON.parse(card.dataset.images || '[]');
    const title = card.querySelector('.product-title')?.textContent?.trim();
    const stockQty = parseInt(card.dataset.stock || '0', 10);
    pdpTitle.textContent = title || 'Product';
    const basePrice = parseFloat(card.dataset.priceBase || '0').toFixed(2);
    const cashPrice = parseFloat(card.dataset.priceCash || '0').toFixed(2);
    pdpPrice.textContent =
        basePrice !== cashPrice
            ? `${CURRENCY} ${basePrice} (Cash ${CURRENCY} ${cashPrice})`
            : `${CURRENCY} ${basePrice}`;
    pdpSku.textContent = `SKU ${card.dataset.sku}`;
    pdpStock.textContent = SHOW_STOCK ? `${stockQty} available` : '';
    pdpStockStatus.textContent = !SHOW_STOCK ? '' :
        stockQty <= 0 ? 'Out of Stock!!' : stockQty <= LOW_STOCK_THRESHOLD ? 'Low Stock' : '';
    buildImageGallery(images);
    activePdpCard = card;
    pdpDialog.showModal();
};


const clearDraft = () => {
    Object.keys(cart).forEach((sku) => {
        cart[sku] = 0;
        const card = productCards.find((item) => item.dataset.sku === sku);
        if (card) {
            const input = card.querySelector('.qty-input');
            if (input) {
                input.value = 0;
            }
        }
    });
    updateTotals();
};

categoryButtons.forEach((button, index) => {
    if (index === 0) {
        button.classList.add('active');
    }
    button.addEventListener('click', () => {
        setActiveCategory(button.dataset.category);
    });
});

subcategoryButtons.forEach((button) => {
    button.addEventListener('click', () => {
        setActiveSubcategory(button.dataset.subcategory);
    });
});

subsubcategoryButtons.forEach((button) => {
    button.addEventListener('click', () => {
        setActiveSubSubcategory(button.dataset.subsubcategory);
    });
});

searchInput?.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyFilters();
    }, 300);
});

clearSearchBtn?.addEventListener('click', () => {
    if (searchInput) {
        searchInput.value = '';
    }
    applyFilters();
});

inStockToggle.addEventListener('change', applyFilters);
sortSelect.addEventListener('change', () => {
    sortProducts();
});

saveDraftBtn.addEventListener('click', async () => {
    if (placeOrderBtn.disabled) {
        alert('Add items before saving a draft.');
        return;
    }
    const response = await fetch('/save_draft', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
        },
        body: new URLSearchParams({
            customer_id: customerIdInput.value,
            items_json: itemsJsonInput.value,
        }),
    });
    if (response.ok) {
        alert('Draft saved.');
    } else {
        alert('Unable to save draft.');
    }
});

clearDraftBtn.addEventListener('click', () => {
    openDialog(clearDraftModal);
});

confirmClearDraftBtn.addEventListener('click', () => {
    clearDraft();
    closeDialog(clearDraftModal);
});

cancelClearDraftBtn.addEventListener('click', () => {
    closeDialog(clearDraftModal);
});

openSearchBtn?.addEventListener('click', () => {
    if (!searchDialog) {
        searchInput?.focus();
        return;
    }
    const scrollY = window.scrollY;
    openDialog(searchDialog);
    searchModalInput.value = '';
    window.requestAnimationFrame(() => {
        window.scrollTo({ top: scrollY });
        if (!searchModalInput) {
            return;
        }
        if (typeof searchModalInput.focus === 'function') {
            try {
                searchModalInput.focus({ preventScroll: true });
            } catch (error) {
                searchModalInput.focus();
            }
        }
    });
    renderSearchResults('');
});

openCategoryHierarchyBtn?.addEventListener('click', () => {
    if (!categoryHierarchyDialog) {
        return;
    }
    expandedHierarchyCategories = new Set();
    if (activeCategory) {
        expandedHierarchyCategories.add(activeCategory);
    }
    renderCategoryHierarchy();
    openDialog(categoryHierarchyDialog);
});

closeCategoryHierarchyBtn?.addEventListener('click', () => {
    closeDialog(categoryHierarchyDialog);
});

toggleSubcategoriesBtn?.addEventListener('click', () => {
    if (!subcategoryScroll) {
        return;
    }
    const isHidden = subcategoryScroll.hasAttribute('hidden');
    if (isHidden) {
        subcategoryScroll.removeAttribute('hidden');
        toggleSubcategoriesBtn.setAttribute('aria-expanded', 'true');
        toggleSubcategoriesBtn.textContent = '▾';
    } else {
        subcategoryScroll.setAttribute('hidden', 'true');
        toggleSubcategoriesBtn.setAttribute('aria-expanded', 'false');
        toggleSubcategoriesBtn.textContent = '▸';
    }
});

toggleSubSubcategoriesBtn?.addEventListener('click', () => {
    if (!subsubcategoryScroll) {
        return;
    }
    const isHidden = subsubcategoryScroll.hasAttribute('hidden');
    if (isHidden) {
        subsubcategoryScroll.removeAttribute('hidden');
        toggleSubSubcategoriesBtn.setAttribute('aria-expanded', 'true');
        toggleSubSubcategoriesBtn.textContent = '▾';
    } else {
        subsubcategoryScroll.setAttribute('hidden', 'true');
        toggleSubSubcategoriesBtn.setAttribute('aria-expanded', 'false');
        toggleSubSubcategoriesBtn.textContent = '▸';
    }
});

closeSearchBtn?.addEventListener('click', () => {
    closeDialog(searchDialog);
});

clearSearchModalBtn?.addEventListener('click', () => {
    searchModalInput.value = '';
    renderSearchResults('');
});

searchModalInput?.addEventListener('input', () => {
    renderSearchResults(searchModalInput.value);
});

[clearDraftModal, searchDialog, pdpDialog, categoryHierarchyDialog].forEach(
    (dialog) => {
    dialog?.addEventListener('click', (event) => {
        if (event.target === dialog) {
            closeDialog(dialog);
        }
    });
    }
);

closePdpBtn?.addEventListener('click', () => {
    closeFullscreen();
    closeDialog(pdpDialog);
});

pdpDialog?.addEventListener('close', () => {
    closeFullscreen();
});

pdpAddBtn?.addEventListener('click', () => {
    if (!activePdpCard) {
        return;
    }
    const input = activePdpCard.querySelector('.qty-input');
    const current = parseInt(input?.value || '0', 10);
    if (input) {
        input.value = current + 1;
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }
});

const handleCartClick = () => {
    if (!placeOrderBtn.disabled) {
        document.getElementById('order-form')?.requestSubmit();
        return;
    }
    cartFooter?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

cartCount?.addEventListener('click', handleCartClick);
cartButtons.forEach((button) => {
    button.addEventListener('click', handleCartClick);
});

const handleScrollLoad = () => {
    const matchingCards = productCards.filter(
        (card) => card.style.display !== 'none'
    );
    if (visibleCount >= matchingCards.length) {
        return;
    }
    const nearBottom =
        window.innerHeight + window.scrollY >=
        document.body.offsetHeight - 200;
    if (nearBottom) {
        visibleCount += 10;
        setVisibleCards(matchingCards);
    }
};

window.addEventListener('scroll', handleScrollLoad, { passive: true });

function renderSearchResults(term) {
    if (!searchResults) {
        return;
    }
    const searchTerm = term.toLowerCase();
    searchResults.innerHTML = '';
    const matches = productCards.filter((card) => {
        const title = card.dataset.title || '';
        const sku = card.dataset.sku.toLowerCase();
        return title.includes(searchTerm) || sku.includes(searchTerm);
    });
    if (!matches.length) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = 'No products found.';
        searchResults.appendChild(empty);
        return;
    }
    matches.slice(0, 20).forEach((card) => {
        const item = document.createElement('div');
        item.className = 'search-card';
        const image = card.dataset.image;
        const searchBasePrice = parseFloat(card.dataset.priceBase || '0').toFixed(2);
        const searchCashPrice = parseFloat(card.dataset.priceCash || '0').toFixed(2);
        item.innerHTML = `
            <div class="search-thumb">
                ${image ? `<img src="${image}" alt="${card.dataset.sku}">` : '<div class="placeholder"><span aria-hidden="true">📦</span></div>'}
            </div>
            <div class="search-content">
                <div class="search-title">${card.querySelector('.product-title')?.textContent || ''}</div>
                <div class="search-meta">SKU ${card.dataset.sku}</div>
                <div class="search-meta">
                    ${CURRENCY} ${searchBasePrice}${searchBasePrice !== searchCashPrice ? ` <span class="muted">(Cash ${CURRENCY} ${searchCashPrice})</span>` : ''}
                </div>
                <button type="button" class="add-to-cart">Add to Cart</button>
            </div>
        `;
        item.querySelector('.add-to-cart')?.addEventListener('click', () => {
            const input = card.querySelector('.qty-input');
            const current = parseInt(input?.value || '0', 10);
            if (input) {
                input.value = current + 1;
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
        item.addEventListener('click', (event) => {
            if (event.target.closest('button')) {
                return;
            }
            openPdp(card);
        });
        searchResults.appendChild(item);
    });
}

const loadDraft = () => {
    const savedItems = [];
    if (window.catalogDraft?.length) {
        savedItems.push(...window.catalogDraft);
    } else {
        const key = getCartStorageKey();
        const localCart = key && window.localStorage ? window.localStorage.getItem(key) : null;
        if (localCart) {
            try {
                const parsed = JSON.parse(localCart);
                if (Array.isArray(parsed)) {
                    savedItems.push(...parsed);
                }
            } catch (error) {
                window.localStorage.removeItem(key);
            }
        }
    }

    savedItems.forEach((item) => {
        const sku = item.sku;
        const qty = parseInt(item.qty || 0, 10);
        if (!sku) {
            return;
        }
        cart[sku] = qty;
    });
};

loadDraft();
updateSubcategoryOptions();
updateSubSubcategoryOptions();
updateTotals();
renderProducts();
