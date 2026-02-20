const bulkForm = document.getElementById('bulk-form');
const bulkActionInput = document.getElementById('bulk-action');
const bulkOrderNumbers = document.getElementById('bulk-order-numbers');
const selectAll = document.querySelector('.orders-table-header input[type="checkbox"]');
const rowCheckboxes = Array.from(
    document.querySelectorAll('.orders-table-row input[type="checkbox"]')
);
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

const getSelectedOrders = () =>
    rowCheckboxes
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value);

const updateBulkOrders = () => {
    const selected = getSelectedOrders();
    bulkOrderNumbers.value = selected.join(',');
};

selectAll?.addEventListener('change', () => {
    rowCheckboxes.forEach((checkbox) => {
        checkbox.checked = selectAll.checked;
    });
    updateBulkOrders();
});

rowCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
        if (!checkbox.checked && selectAll) {
            selectAll.checked = false;
        }
        updateBulkOrders();
    });
});

bulkForm?.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) {
        return;
    }
    event.preventDefault();
    updateBulkOrders();
    bulkActionInput.value = button.dataset.action;
    bulkForm.requestSubmit(button);
});

const escapeHtml = (value) =>
    String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

const renderOrderItems = (orderNumber, items = []) => {
    detailTitle.textContent = `Order ${orderNumber}`;
    detailContent.innerHTML = '';
    if (!items.length) {
        detailContent.textContent = 'No items found.';
        return;
    }
    items.forEach((item) => {
        const card = document.createElement('div');
        card.className = 'order-detail-item';
        const safeTitle = escapeHtml(item.title);
        const safeSku = escapeHtml(item.sku);
        const safeImageUrl = escapeHtml(item.image_url);
        const imageMarkup = item.image_url
            ? `<img src="${safeImageUrl}" alt="${safeTitle}">`
            : '<div class="placeholder">No Image</div>';
        card.innerHTML = `
            <div class="order-detail-image">
                ${imageMarkup}
            </div>
            <div class="order-detail-body">
                <strong>${safeTitle}</strong>
                <span>SKU: ${safeSku}</span>
                <span>Qty: ${parseFloat(item.qty)}</span>
                <span>Price: SAR ${parseFloat(item.price).toFixed(2)}</span>
            </div>
        `;
        detailContent.appendChild(card);
    });
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
