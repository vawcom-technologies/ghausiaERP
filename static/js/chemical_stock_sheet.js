/**
 * Chemical stock sheet: Total = closing + new; Remaining = total - issued.
 */
(function () {
  function stripUnit(value) {
    return String(value || "")
      .trim()
      .replace(/,/g, "")
      .replace(/\s*kgs?\s*$/i, "")
      .trim();
  }

  function parseQty(value) {
    var text = stripUnit(value);
    if (!text) return 0;
    var n = parseFloat(text);
    return Number.isFinite(n) ? n : 0;
  }

  function formatQty(n) {
    if (!Number.isFinite(n)) return "";
    var qty =
      Math.abs(n - Math.round(n)) < 1e-9
        ? String(Math.round(n))
        : String(Math.round(n * 1000) / 1000);
    return qty + " kgs";
  }

  /** Append "kgs" after a entered quantity (closing / new / issued). */
  function withUnit(value) {
    var text = String(value || "").trim();
    if (!text) return "";
    var raw = stripUnit(text);
    if (!raw) return "";
    var n = parseFloat(raw);
    if (!Number.isFinite(n)) return text;
    return formatQty(n);
  }

  function normalizeQtyInput(el) {
    if (!el) return;
    el.value = withUnit(el.value);
  }

  function recalcRow(row) {
    if (!row) return;
    var closing = row.querySelector('[name="closing_stock"]');
    var neu = row.querySelector('[name="new_stock"]');
    var issued = row.querySelector('[name="issued_stock"]');
    var total = row.querySelector('[name="total_stock"]');
    var remaining = row.querySelector('[name="remaining_stock"]');
    if (!total || !remaining) return;

    var totalVal = parseQty(closing && closing.value) + parseQty(neu && neu.value);
    var remainVal = totalVal - parseQty(issued && issued.value);
    total.value = formatQty(totalVal);
    remaining.value = formatQty(remainVal);
  }

  function bind(root) {
    root.addEventListener("input", function (e) {
      var el = e.target;
      if (!el || !el.classList || !el.classList.contains("stock-qty")) return;
      recalcRow(el.closest("tr"));
    });
    root.addEventListener("change", function (e) {
      var el = e.target;
      if (!el || !el.classList || !el.classList.contains("stock-qty")) return;
      normalizeQtyInput(el);
      recalcRow(el.closest("tr"));
    });
    // focusout bubbles; blur does not
    root.addEventListener("focusout", function (e) {
      var el = e.target;
      if (!el || !el.classList || !el.classList.contains("stock-qty")) return;
      normalizeQtyInput(el);
      recalcRow(el.closest("tr"));
    });
    root.querySelectorAll(".stock-qty").forEach(normalizeQtyInput);
    root.querySelectorAll("[data-sheet-row]").forEach(recalcRow);

    // Recalc after Add Row clones a template row.
    var addBtn = root.querySelector("[data-sheet-add-row]");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        setTimeout(function () {
          var rows = root.querySelectorAll("[data-sheet-row]");
          if (rows.length) recalcRow(rows[rows.length - 1]);
        }, 0);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var root = document.querySelector("[data-chemical-stock]");
    if (root) bind(root);
  });
})();
