/**
 * Gate Entry spreadsheet: add/remove rows, auto G1/G2… numbers, validation.
 */
(function () {
  function getRoot() {
    return document.querySelector("[data-gate-sheet]");
  }

  function fieldValue(row, name) {
    const el = row.querySelector('[name="' + name + '"]');
    return el ? String(el.value || "").trim() : "";
  }

  function rowLooksBlank(row) {
    return (
      !fieldValue(row, "purchaser") &&
      !fieldValue(row, "shop_name") &&
      !fieldValue(row, "chemical") &&
      !fieldValue(row, "electrical") &&
      !fieldValue(row, "mechanical") &&
      !fieldValue(row, "general") &&
      !fieldValue(row, "demanded_by")
    );
  }

  function validateRow(row) {
    const missing = [];
    if (!fieldValue(row, "entry_date")) missing.push("Date");
    if (!fieldValue(row, "purchaser")) missing.push("Purchaser");
    if (!fieldValue(row, "shop_name")) missing.push("Shop Name");
    const stock =
      fieldValue(row, "chemical") ||
      fieldValue(row, "electrical") ||
      fieldValue(row, "mechanical") ||
      fieldValue(row, "general");
    if (!stock) missing.push("Stock Description");
    if (!fieldValue(row, "demanded_by")) missing.push("Demanded By");
    return missing;
  }

  function renumberGates(root) {
    const start = parseInt(root.getAttribute("data-start-seq") || "1", 10) || 1;
    const tbody = root.querySelector("[data-sheet-body]");
    if (!tbody) return;
    Array.from(tbody.querySelectorAll("tr")).forEach(function (row, i) {
      const input = row.querySelector(".gate-number-input");
      if (input) input.value = "G" + (start + i);
    });
  }

  function addRow(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const templateId = root.getAttribute("data-row-template") || "gate-row-template";
    const template = document.getElementById(templateId);
    if (!template || !tbody) return;
    tbody.appendChild(template.content.cloneNode(true));
    renumberGates(root);
  }

  function bind(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const addBtn = root.querySelector("[data-sheet-add-row]");

    renumberGates(root);

    if (addBtn) {
      addBtn.addEventListener("click", function (e) {
        e.preventDefault();
        addRow(root);
      });
    }

    root.addEventListener("click", function (e) {
      const removeBtn = e.target.closest("[data-sheet-remove-row]");
      if (!removeBtn) return;
      e.preventDefault();
      const row = removeBtn.closest("tr");
      if (!row || !tbody || tbody.querySelectorAll("tr").length <= 1) return;
      if (!rowLooksBlank(row)) {
        const ok = window.confirm(
          "This row has data. Remove it anyway?\n\nیہ قطار بھری ہوئی ہے — کیا آپ واقعی ہٹانا چاہتے ہیں؟"
        );
        if (!ok) return;
      }
      row.remove();
      renumberGates(root);
    });

    root.addEventListener("submit", function (e) {
      if (!tbody) return;
      renumberGates(root);
      tbody.querySelectorAll("tr.sheet-row-invalid").forEach(function (row) {
        row.classList.remove("sheet-row-invalid");
      });

      const problems = [];
      Array.from(tbody.querySelectorAll("tr")).forEach(function (row, idx) {
        if (rowLooksBlank(row)) return;
        const missing = validateRow(row);
        if (missing.length) {
          row.classList.add("sheet-row-invalid");
          problems.push("Row " + (idx + 1) + ": " + missing.join(", "));
        }
      });

      if (problems.length) {
        e.preventDefault();
        alert(
          "Incomplete rows are not saved. Fix the red rows:\n\n" +
            problems.slice(0, 8).join("\n") +
            (problems.length > 8 ? "\n…" : "")
        );
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const root = getRoot();
    if (root) bind(root);
  });
})();
