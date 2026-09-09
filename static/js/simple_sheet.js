/**
 * Simple spreadsheet: add / remove rows (no module-specific validation).
 */
(function () {
  function getRoot() {
    return document.querySelector("[data-simple-sheet]");
  }

  function addRow(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const templateId = root.getAttribute("data-row-template") || "sheet-row-template";
    const template = document.getElementById(templateId);
    if (!template || !tbody) return;
    tbody.appendChild(template.content.cloneNode(true));
  }

  function rowLooksEmpty(row) {
    const fields = row.querySelectorAll("input:not([type=hidden]):not([type=file]), textarea, select");
    return Array.from(fields).every(function (el) {
      return !String(el.value || "").trim();
    });
  }

  function bind(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const addBtn = root.querySelector("[data-sheet-add-row]");

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
      if (!rowLooksEmpty(row)) {
        const ok = window.confirm("This row has data. Remove it anyway?");
        if (!ok) return;
      }
      row.remove();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const root = getRoot();
    if (root) bind(root);
  });
})();
