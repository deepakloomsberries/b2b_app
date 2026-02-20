const viewButtons = Array.from(document.querySelectorAll('.view-order'));
const detailModal = document.getElementById('order-detail-modal');
const detailContent = document.getElementById('order-detail-content');
const detailTitle = document.getElementById('order-detail-title');
const closeDetail = document.getElementById('close-order-detail');

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
};

const escapeHtml = (value) =>
    String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

const formatMoney = (value) => Number.parseFloat(value || 0).toFixed(2);

const renderOrderItems = (orderNumber, items = []) => {
    detailTitle.textContent = `Order ${orderNumber}`;
    detailContent.innerHTML = '';
    if (!items.length) {
        detailContent.textContent = 'No items found.';
        return;
    }
    const total = items.reduce((sum, item) => {
        const subtotal = Number.parseFloat(item.qty || 0) * Number.parseFloat(item.price || 0);
        return sum + subtotal;
    }, 0);

    const summary = document.createElement('div');
    summary.className = 'order-summary';
    summary.innerHTML = `
        <div class="order-summary-header">
            <span>Item</span>
            <span>Qty</span>
            <span>Price</span>
            <span>Total</span>
        </div>
    `;

    items.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'order-summary-row';
        const safeSku = escapeHtml(item.sku);
        const safeImageUrl = escapeHtml(item.image_url);
        const imageMarkup = item.image_url
            ? `<img src="${safeImageUrl}" alt="SKU ${safeSku}">`
            : '<div class="placeholder">No Image</div>';
        const subtotal = Number.parseFloat(item.qty || 0) * Number.parseFloat(item.price || 0);
        row.innerHTML = `
            <div class="order-summary-item">
                <div class="order-summary-image">
                    ${imageMarkup}
                </div>
                <div class="order-summary-sku">${safeSku}</div>
            </div>
            <div class="order-summary-qty">${Number.parseFloat(item.qty || 0)}</div>
            <div class="order-summary-price">SAR ${formatMoney(item.price)}</div>
            <div class="order-summary-total">SAR ${formatMoney(subtotal)}</div>
        `;
        summary.appendChild(row);
    });

    const totals = document.createElement('div');
    totals.className = 'order-summary-totals';
    totals.innerHTML = `
        <div class="order-summary-total-row">
            <span>Subtotal</span>
            <span>SAR ${formatMoney(total)}</span>
        </div>
        <div class="order-summary-total-row total">
            <span>Total</span>
            <span>SAR ${formatMoney(total)}</span>
        </div>
    `;

    detailContent.appendChild(summary);
    detailContent.appendChild(totals);
};

viewButtons.forEach((button) => {
    button.addEventListener('click', async () => {
        const orderNumber = button.dataset.orderNumber;
        try {
            const response = await fetch(`/orders/${orderNumber}/items`);
            if (!response.ok) {
                renderOrderItems(orderNumber, []);
                openDialog(detailModal);
                return;
            }
            const data = await response.json();
            renderOrderItems(orderNumber, data.items);
            openDialog(detailModal);
        } catch (error) {
            renderOrderItems(orderNumber, []);
            openDialog(detailModal);
        }
    });
});

closeDetail?.addEventListener('click', () => closeDialog(detailModal));

detailModal?.addEventListener('click', (event) => {
    if (event.target === detailModal) {
        closeDialog(detailModal);
    }
});
