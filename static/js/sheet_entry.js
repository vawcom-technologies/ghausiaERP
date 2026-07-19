/**
 * Excel-like sheet entry helpers: add/remove rows and paste from clipboard.
 */
(function () {
  function getSheetRoot() {
    return document.querySelector("[data-sheet-entry]");
  }

  function addRow(tbody, templateId) {
    const template = document.getElementById(templateId);
    if (!template || !tbody) return;
    const clone = template.content.cloneNode(true);
    tbody.appendChild(clone);
  }

  function bindSheet(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const templateId = root.getAttribute("data-row-template") || "sheet-row-template";
    const addBtn = root.querySelector("[data-sheet-add-row]");

    if (addBtn) {
      addBtn.addEventListener("click", function (e) {
        e.preventDefault();
        addRow(tbody, templateId);
      });
    }

    root.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-sheet-remove-row]");
      if (!btn) return;
      e.preventDefault();
      const row = btn.closest("tr");
      if (row && tbody && tbody.querySelectorAll("tr").length > 1) {
        row.remove();
      }
    });

    // Paste Excel/TSV into focused cell of the sheet
    root.addEventListener("paste", function (e) {
      const target = e.target;
      if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement)) {
        return;
      }
      const text = (e.clipboardData || window.clipboardData).getData("text");
      if (!text || (!text.includes("\t") && !text.includes("\n"))) {
        return; // normal single-cell paste
      }
      e.preventDefault();

      const rows = text.replace(/\r/g, "").split("\n").filter(function (r) {
        return r.length > 0;
      });
      const startRow = target.closest("tr");
      if (!startRow || !tbody) return;

      const startCells = Array.from(startRow.querySelectorAll("input, select, textarea"));
      const startCol = startCells.indexOf(target);
      if (startCol < 0) return;

      let current = startRow;
      rows.forEach(function (line, rIdx) {
        if (rIdx > 0) {
          if (!current.nextElementSibling) {
            addRow(tbody, templateId);
          }
          current = current.nextElementSibling || current;
        }
        const cols = line.split("\t");
        const fields = Array.from(current.querySelectorAll("input, select, textarea"));
        cols.forEach(function (val, cIdx) {
          const field = fields[startCol + cIdx];
          if (!field) return;
          if (field.tagName === "SELECT") {
            const options = Array.from(field.options);
            const match = options.find(function (o) {
              return o.value === val || o.text.trim().toLowerCase() === val.trim().toLowerCase();
            });
            if (match) field.value = match.value;
          } else {
            field.value = val;
          }
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const root = getSheetRoot();
    if (root) bindSheet(root);
  });
})();
