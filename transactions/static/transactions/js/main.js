function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

const totalBalanceSpan = document.getElementById("total-balance");
const addTransactionModal = document.getElementById("addTransactionModal");
const addTransactionForm = document.getElementById("addTransactionForm");
const typeSelect = document.getElementById("typeSelect");
const errorDiv = document.getElementById("formError");
const transactionTableBody = document.getElementById("transaction-table-body");
const loadMoreBtn = document.getElementById("loadMoreBtn");
const toastContainer = document.querySelector(".toast-container");

const filterTypeSelect = document.getElementById("filterType");
const applyFiltersBtn = document.getElementById("applyFiltersBtn");

const TRANSACTION_LIST_URL = loadMoreBtn.dataset.listUrl;
const ADD_TRANSACTION_URL = addTransactionForm.dataset.addUrl;
const IMPORT_TRANSACTIONS_URL = document.getElementById(
  "loadApiTransactionsBtn"
).dataset.importUrl;

function resetErrorState() {
  errorDiv.classList.add("d-none");
  errorDiv.innerHTML = "";
}

function createTransactionRow(transaction) {
  const row = document.createElement("tr");
  const amountClass = transaction.type;
  const amountValue =
    typeof transaction.amount === "number"
      ? transaction.amount
      : parseFloat(transaction.amount);
  const amountSign = amountValue > 0 ? "+" : "";

  row.innerHTML = `
    <td>${transaction.code || "N/A"}</td>
    <td>${transaction.created_at}</td>
    <td class="${amountClass}">${transaction.type_display}</td>
    <td><span class="${amountClass}">${amountSign}${amountValue.toFixed(
    2
  )}</span></td>
    <td>${transaction.running_balance.toFixed(2)}</td>
  `;
  return row;
}

function showToast(message, type = "success") {
  const toastId = `toast-${Date.now()}`;
  const toastClasses =
    type === "success" ? "text-bg-success" : "text-bg-danger";
  const headerText = type === "success" ? "Success" : "Error";

  const toastHtml = `
    <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="5000">
      <div class="toast-header ${toastClasses}">
        <strong class="me-auto">${headerText}</strong>
        <small>Now</small>
        <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
      <div class="toast-body">
        ${message}
      </div>
    </div>
  `;

  toastContainer.insertAdjacentHTML("beforeend", toastHtml);

  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement);
  toast.show();

  toastElement.addEventListener("hidden.bs.toast", function () {
    toastElement.remove();
  });
}

async function fetchTransactions(page = 1, append = false) {
  const selectedType = filterTypeSelect.value;
  let url = `${TRANSACTION_LIST_URL}?page=${page}`;

  if (selectedType) {
    url += `&type=${selectedType}`;
  }

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    if (!response.ok) {
      throw new Error("Failed to load transactions.");
    }

    const data = await response.json();

    if (!append) {
      transactionTableBody.innerHTML = "";
      if (data.transactions.length === 0) {
        const noTransactionsRow = document.createElement("tr");
        noTransactionsRow.id = "no-transactions-row";
        noTransactionsRow.innerHTML =
          '<td colspan="5" class="text-center">No transactions yet.</td>';
        transactionTableBody.appendChild(noTransactionsRow);
      }
    }

    if (data.transactions && data.transactions.length > 0) {
      const noTransactionsRow = document.getElementById("no-transactions-row");
      if (noTransactionsRow) {
        noTransactionsRow.remove();
      }

      data.transactions.forEach((transaction) => {
        const row = createTransactionRow(transaction);
        transactionTableBody.appendChild(row);
      });
    }

    if (data.total_balance !== undefined && data.total_balance !== null) {
      const balance = parseFloat(data.total_balance);
      if (!isNaN(balance)) {
        totalBalanceSpan.textContent = `$${balance.toFixed(2)}`;
      }
    }

    if (data.has_next) {
      loadMoreBtn.dataset.nextPage = data.next_page_number;
      loadMoreBtn.textContent = "Load More";
      loadMoreBtn.disabled = false;
      loadMoreBtn.style.display = "";
    } else {
      loadMoreBtn.textContent = "No More Transactions";
      loadMoreBtn.disabled = true;
      loadMoreBtn.style.display = "none";
    }
  } catch (error) {
    console.error("Error fetching transactions:", error);
    showToast("Error loading transactions: " + error.message, "error");
    loadMoreBtn.textContent = "Error Loading";
    loadMoreBtn.disabled = false;
    loadMoreBtn.style.display = "";
  }
}

addTransactionForm.addEventListener("submit", async function (e) {
  e.preventDefault();
  const form = e.target;
  const type = form.type.value;
  const amount = form.amount.value;

  resetErrorState();

  try {
    const response = await fetch(ADD_TRANSACTION_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({ type, amount }),
    });

    const data = await response.json();

    if (!response.ok) {
      let errorMessage = "";
      if (data.error) {
        if (
          typeof data.error === "object" &&
          data.error.type &&
          Object.keys(data.error).length === 1 &&
          data.error.type[0].includes("Too many expenses today")
        ) {
          errorMessage = data.error.type[0];
        } else if (
          typeof data.error === "object" &&
          data.error.amount &&
          Object.keys(data.error).length === 1 &&
          data.error.amount[0].includes("Not enough balance")
        ) {
          errorMessage = data.error.amount[0];
        } else if (typeof data.error === "object") {
          for (const field in data.error) {
            if (data.error.hasOwnProperty(field)) {
              errorMessage += `<strong>${
                field.charAt(0).toUpperCase() + field.slice(1)
              }:</strong> ${data.error[field].join("<br>")}<br>`;
            }
          }
        } else {
          errorMessage = data.error || data.message;
        }
      } else {
        errorMessage = data.message;
      }

      errorDiv.innerHTML = errorMessage;
      errorDiv.classList.remove("d-none");
      showToast(errorMessage, "error");
      return;
    }

    bootstrap.Modal.getInstance(addTransactionModal).hide();
    showToast(data.message || "Transaction added successfully!", "success");

    if (data.total_balance !== undefined && data.total_balance !== null) {
      const balance = parseFloat(data.total_balance);
      if (!isNaN(balance)) {
        totalBalanceSpan.textContent = `$${balance.toFixed(2)}`;
      }
    }

    if (data.new_transaction) {
      const newRow = createTransactionRow(data.new_transaction);
      transactionTableBody.prepend(newRow);

      const noTransactionsRow = document.getElementById("no-transactions-row");
      if (noTransactionsRow) {
        noTransactionsRow.remove();
      }

      if (transactionTableBody.children.length > 10) {
        transactionTableBody.lastElementChild.remove();
      }
    }
  } catch (err) {
    console.error("Error:", err);
    const errorMessage = "Network error or invalid server response.";
    errorDiv.innerHTML = errorMessage;
    errorDiv.classList.remove("d-none");
    showToast(errorMessage, "error");
  }
});

addTransactionModal.addEventListener("hidden.bs.modal", function () {
  addTransactionForm.reset();
  resetErrorState();
});

typeSelect.addEventListener("change", function () {
  resetErrorState();
});

if (loadMoreBtn) {
  loadMoreBtn.addEventListener("click", function () {
    const nextPage = this.dataset.nextPage;
    fetchTransactions(nextPage, true);
  });
}

if (applyFiltersBtn) {
  applyFiltersBtn.addEventListener("click", function () {
    fetchTransactions(1, false);
  });
}

document
  .getElementById("loadApiTransactionsBtn")
  .addEventListener("click", async function () {
    const button = this;
    button.disabled = true;
    button.textContent = "Loading...";

    try {
      const response = await fetch(IMPORT_TRANSACTIONS_URL, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken"),
        },
      });

      const data = await response.json();

      if (!response.ok) {
        const errorMessage =
          data.error || data.message || "Failed to load transactions from API.";
        throw new Error(errorMessage);
      }

      showToast(data.message, "success");
      await fetchTransactions(1, false);
    } catch (error) {
      console.error("Error importing transactions:", error);
      showToast("Error importing transactions: " + error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = "Load Transactions";
    }
  });
