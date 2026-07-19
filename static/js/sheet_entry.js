/**
 * Excel-like sheet entry helpers: add/remove rows, paste, photo preview, validation.
 */
(function () {
  function getSheetRoot() {
    return document.querySelector("[data-sheet-entry]");
  }

  function editableFields(row) {
    return Array.from(row.querySelectorAll("input:not([type=file]), select, textarea"));
  }

  function indexFileInputs(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    if (!tbody) return;
    const rows = tbody.querySelectorAll("tr");
    rows.forEach(function (row, i) {
      const file = row.querySelector('input[type="file"].sheet-photo-input');
      if (file) file.name = "receipt_image_" + i;
    });
  }

  function addRow(tbody, templateId, root) {
    const template = document.getElementById(templateId);
    if (!template || !tbody) return;
    const clone = template.content.cloneNode(true);
    tbody.appendChild(clone);
    if (root) indexFileInputs(root);
  }

  function fieldValue(row, name) {
    const el = row.querySelector('[name="' + name + '"]');
    return el ? String(el.value || "").trim() : "";
  }

  function positiveNumber(value) {
    if (value === "") return false;
    const n = Number(String(value).replace(",", ""));
    return Number.isFinite(n) && n > 0;
  }

  function rowLooksBlank(row) {
    const names = [
      "lot_number",
      "vendor_name",
      "cloth_pv",
      "cloth_read_pick",
      "vendor_metres",
      "factory_metres",
    ];
    const textEmpty = names.every(function (name) {
      return fieldValue(row, name) === "";
    });
    const rolls = fieldValue(row, "rolls");
    const factoryRolls = fieldValue(row, "factory_rolls");
    const numbersDefault =
      (!rolls || rolls === "0") &&
      (!factoryRolls || factoryRolls === "0") &&
      (!fieldValue(row, "vendor_weight") || fieldValue(row, "vendor_weight") === "0") &&
      (!fieldValue(row, "factory_weight") || fieldValue(row, "factory_weight") === "0");
    const noRemarks = fieldValue(row, "remarks") === "";
    const file = row.querySelector('input[type="file"]');
    const hasFile = file && file.files && file.files.length > 0;
    return textEmpty && numbersDefault && noRemarks && !hasFile;
  }

  function validateRow(row) {
    const missing = [];
    if (!fieldValue(row, "lot_number")) missing.push("Lot / Palli Number");
    if (!fieldValue(row, "receipt_date")) missing.push("Date");
    if (!fieldValue(row, "vendor_name")) missing.push("Party");

    function clothMeaningful(v) {
      const t = String(v || "").trim();
      return t !== "" && t !== "/" && t !== "-" && t !== "—";
    }
    const pv = fieldValue(row, "cloth_pv");
    const rp = fieldValue(row, "cloth_read_pick");
    if (!clothMeaningful(pv) && !clothMeaningful(rp)) {
      missing.push("Cloth Type (enter PV blend and/or Read Pick; / = empty)");
    }

    if (!positiveNumber(fieldValue(row, "rolls"))) missing.push("Party Thaan");
    if (!positiveNumber(fieldValue(row, "factory_rolls"))) missing.push("Factory Thaan");
    if (!positiveNumber(fieldValue(row, "vendor_metres"))) missing.push("Vendor M");
    if (!positiveNumber(fieldValue(row, "factory_metres"))) missing.push("Factory M");
    return missing;
  }

  function clearRowErrors(tbody) {
    tbody.querySelectorAll("tr.sheet-row-invalid").forEach(function (row) {
      row.classList.remove("sheet-row-invalid");
    });
  }

  function updatePhotoLabel(input) {
    const cell = input.closest(".sheet-photo-cell");
    if (!cell) return;
    const label = cell.querySelector(".sheet-photo-btn");
    const text = cell.querySelector(".sheet-photo-label");
    const viewBtn = cell.querySelector("[data-photo-view]");
    if (cell._previewUrl) {
      URL.revokeObjectURL(cell._previewUrl);
      cell._previewUrl = "";
    }
    if (input.files && input.files.length) {
      const url = URL.createObjectURL(input.files[0]);
      cell._previewUrl = url;
      if (text) text.textContent = "✓";
      if (label) label.classList.add("has-file");
      if (viewBtn) {
        viewBtn.hidden = false;
        viewBtn.dataset.previewUrl = url;
      }
    } else {
      if (text) text.textContent = "Add";
      if (label) label.classList.remove("has-file");
      if (viewBtn) {
        viewBtn.hidden = true;
        delete viewBtn.dataset.previewUrl;
      }
    }
  }

  function openPhotoModal(url) {
    const modal = document.getElementById("sheet-photo-modal");
    const img = document.getElementById("sheet-photo-modal-img");
    if (!modal || !img || !url) return;
    img.src = url;
    modal.hidden = false;
    document.body.classList.add("sheet-photo-modal-open");
  }

  function closePhotoModal() {
    const modal = document.getElementById("sheet-photo-modal");
    const img = document.getElementById("sheet-photo-modal-img");
    if (!modal) return;
    modal.hidden = true;
    if (img) img.src = "";
    document.body.classList.remove("sheet-photo-modal-open");
  }

  function bindSheet(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const templateId = root.getAttribute("data-row-template") || "sheet-row-template";
    const addBtn = root.querySelector("[data-sheet-add-row]");

    indexFileInputs(root);

    if (addBtn) {
      addBtn.addEventListener("click", function (e) {
        e.preventDefault();
        addRow(tbody, templateId, root);
      });
    }

    root.addEventListener("click", function (e) {
      const removeBtn = e.target.closest("[data-sheet-remove-row]");
      if (removeBtn) {
        e.preventDefault();
        const row = removeBtn.closest("tr");
        if (!row || !tbody || tbody.querySelectorAll("tr").length <= 1) {
          return;
        }
        if (!rowLooksBlank(row)) {
          const ok = window.confirm(
            "This row has data. Remove it anyway?\n\nیہ قطار بھری ہوئی ہے — کیا آپ واقعی ہٹانا چاہتے ہیں؟"
          );
          if (!ok) return;
        }
        const cell = row.querySelector(".sheet-photo-cell");
        if (cell && cell._previewUrl) URL.revokeObjectURL(cell._previewUrl);
        row.remove();
        indexFileInputs(root);
        return;
      }

      const viewBtn = e.target.closest("[data-photo-view]");
      if (viewBtn) {
        e.preventDefault();
        openPhotoModal(viewBtn.dataset.previewUrl || "");
      }
    });

    document.addEventListener("click", function (e) {
      if (e.target.closest("[data-photo-modal-close]")) {
        closePhotoModal();
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePhotoModal();
    });

    root.addEventListener("change", function (e) {
      const input = e.target;
      if (input && input.matches('input[type="file"].sheet-photo-input')) {
        updatePhotoLabel(input);
      }
    });

    root.addEventListener("submit", function (e) {
      if (!tbody) return;
      clearRowErrors(tbody);
      indexFileInputs(root);

      const rows = Array.from(tbody.querySelectorAll("tr"));
      const problems = [];
      rows.forEach(function (row, idx) {
        if (rowLooksBlank(row)) return;
        const missing = validateRow(row);
        if (missing.length) {
          row.classList.add("sheet-row-invalid");
          problems.push("Row " + (idx + 1) + ": " + missing.join(", "));
        }
      });

      // Block submit so the browser keeps all typed values + selected photos.
      if (problems.length) {
        e.preventDefault();
        alert(
          "Incomplete rows are not saved. Your data stays on this page — fix the red rows:\n\n" +
            problems.slice(0, 8).join("\n") +
            (problems.length > 8 ? "\n…" : "")
        );
      }
    });

    // Paste Excel/TSV into focused cell of the sheet
    root.addEventListener("paste", function (e) {
      const target = e.target;
      if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement)) {
        return;
      }
      if (target.type === "file") return;

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

      const startCells = editableFields(startRow);
      const startCol = startCells.indexOf(target);
      if (startCol < 0) return;

      let current = startRow;
      rows.forEach(function (line, rIdx) {
        if (rIdx > 0) {
          if (!current.nextElementSibling) {
            addRow(tbody, templateId, root);
          }
          current = current.nextElementSibling || current;
        }
        const cols = line.split("\t");
        const fields = editableFields(current);
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
