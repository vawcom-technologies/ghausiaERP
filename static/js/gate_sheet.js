/**
 * Gate Entry spreadsheet: stock fields use numbered points 1, 2, 3, 4…
 * Type an item, then press Space twice (or Enter) to open the next point.
 */
(function () {
  var STOCK_NAMES = {
    chemical: true,
    electrical: true,
    mechanical: true,
    general: true,
  };

  function getRoot() {
    return document.querySelector("[data-gate-sheet]");
  }

  function fieldValue(row, name) {
    const el = row.querySelector('[name="' + name + '"]');
    if (!el) return "";
    if (STOCK_NAMES[name]) return stockPlainValue(el.value);
    return String(el.value || "").trim();
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

  function indexFileInputs(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    if (!tbody) return;
    tbody.querySelectorAll("tr").forEach(function (row, i) {
      const file = row.querySelector('input[type="file"].sheet-photo-input');
      if (file) file.name = "gate_image_" + i;
    });
  }

  function updatePhotoLabel(input) {
    const cell = input.closest(".sheet-photo-cell");
    if (!cell) return;
    const label = cell.querySelector(".sheet-photo-btn");
    const text = cell.querySelector(".sheet-photo-label");
    const viewBtn = cell.querySelector("[data-photo-view]");
    const keep = cell.querySelector('input[name="photo_keep"]');
    if (cell._previewUrl) {
      URL.revokeObjectURL(cell._previewUrl);
      cell._previewUrl = "";
    }
    if (input.files && input.files.length) {
      const url = URL.createObjectURL(input.files[0]);
      cell._previewUrl = url;
      if (keep) keep.value = "";
      if (text) text.textContent = "✓";
      if (label) label.classList.add("has-file");
      if (viewBtn) {
        viewBtn.hidden = false;
        viewBtn.dataset.previewUrl = url;
      }
    } else if (keep && keep.value) {
      if (text) text.textContent = "✓";
      if (label) label.classList.add("has-file");
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

  function addRow(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const templateId = root.getAttribute("data-row-template") || "gate-row-template";
    const template = document.getElementById(templateId);
    if (!template || !tbody) return;
    tbody.appendChild(template.content.cloneNode(true));
    renumberGates(root);
    indexFileInputs(root);
  }

  function stripItemPrefix(line) {
    return String(line || "")
      .replace(/^\s*\d+\.\s*/, "")
      .trim();
  }

  /** Parse into plain items (supports "1. a", newlines, double spaces). */
  function splitStockItems(text) {
    return String(text || "")
      .split(/\n+/)
      .map(stripItemPrefix)
      .join("\n")
      .split(/\s{2,}|\n+/)
      .map(function (p) {
        return p.replace(/\.\s*$/, "").trim(); // drop smart-period leftovers
      })
      .filter(Boolean);
  }

  function stockPlainValue(text) {
    return splitStockItems(text).join("\n").trim();
  }

  function toNumberedText(items, trailingEmpty) {
    var list = items.slice();
    if (trailingEmpty) list.push("");
    if (!list.length) list = [""];
    return list
      .map(function (item, i) {
        return i + 1 + ". " + item;
      })
      .join("\n");
  }

  function cursorPosForLine(numberedText, lineIndex) {
    var lines = numberedText.split("\n");
    var pos = 0;
    for (var i = 0; i < lineIndex && i < lines.length; i++) {
      pos += lines[i].length + 1;
    }
    return pos + String(lineIndex + 1).length + 2; // "N. "
  }

  /**
   * Finish the current point and open the next number (2, 3, 4…).
   * cutPos = cursor index; optional trimBack removes trailing spaces/period before the break.
   */
  function openNextPoint(el, cutPos, trimBack) {
    var value = el.value;
    var before = value.slice(0, cutPos);
    var after = value.slice(cutPos);

    if (trimBack) {
      before = before.replace(/[\s.]+$/g, "");
    }

    var beforeItems = splitStockItems(before);
    var afterItems = splitStockItems(after);
    var merged = beforeItems.concat([""]).concat(afterItems);
    var numbered = merged
      .map(function (item, i) {
        return i + 1 + ". " + item;
      })
      .join("\n");
    var newLineIndex = beforeItems.length;

    el.value = numbered;
    var pos = cursorPosForLine(numbered, newLineIndex);
    el.selectionStart = el.selectionEnd = pos;
    return true;
  }

  function formatStockField(el, focusLastEmpty) {
    var items = splitStockItems(el.value);
    var numbered = toNumberedText(items, focusLastEmpty || !items.length);
    el.value = numbered;
    if (focusLastEmpty || !items.length) {
      var pos = cursorPosForLine(numbered, items.length);
      try {
        el.selectionStart = el.selectionEnd = pos;
      } catch (err) {
        /* ignore */
      }
    }
  }

  function prepareStockFieldForSubmit(el) {
    el.value = stockPlainValue(el.value);
  }

  function isStockField(el) {
    return el && el.classList && el.classList.contains("gate-stock-input") && el.name && STOCK_NAMES[el.name];
  }

  function bind(root) {
    const tbody = root.querySelector("[data-sheet-body]");
    const addBtn = root.querySelector("[data-sheet-add-row]");

    renumberGates(root);
    indexFileInputs(root);

    root.querySelectorAll(".gate-stock-input").forEach(function (el) {
      if (String(el.value || "").trim()) formatStockField(el, false);
    });

    root.querySelectorAll('input[type="file"].sheet-photo-input').forEach(updatePhotoLabel);

    if (addBtn) {
      addBtn.addEventListener("click", function (e) {
        e.preventDefault();
        addRow(root);
      });
    }

    root.addEventListener("focusin", function (e) {
      var el = e.target;
      if (!isStockField(el)) return;
      if (!String(el.value || "").trim()) {
        el.value = "1. ";
        el.selectionStart = el.selectionEnd = 3;
      } else if (!/^\s*\d+\.\s*/.test(el.value)) {
        formatStockField(el, false);
      }
    });

    // Space twice → next point (intercept 2nd space so macOS cannot turn it into ".")
    // Enter → next point
    root.addEventListener("keydown", function (e) {
      var el = e.target;
      if (!isStockField(el)) return;

      if (e.key === "Enter") {
        e.preventDefault();
        var enterPos = el.selectionStart;
        var enterLineStart = el.value.lastIndexOf("\n", enterPos - 1) + 1;
        var enterContent = stripItemPrefix(el.value.slice(enterLineStart, enterPos));
        if (!enterContent) return; // need text on this point first
        openNextPoint(el, enterPos, true);
        return;
      }

      if (e.key !== " " && e.code !== "Space") return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      var pos = el.selectionStart;
      var end = el.selectionEnd;
      if (pos == null || pos !== end || pos < 1) return;

      var lineStart = el.value.lastIndexOf("\n", pos - 1) + 1;
      var lineBeforeCursor = el.value.slice(lineStart, pos);
      var content = stripItemPrefix(lineBeforeCursor);
      var prev = el.value.charAt(pos - 1);

      // Still on an empty "1. " / "2. " — don't jump ahead
      if (!content) {
        if (prev === " ") e.preventDefault();
        return;
      }

      // Second space (or space after smart-period) → point 2, 3, 4…
      if (prev === " " || prev === ".") {
        e.preventDefault();
        openNextPoint(el, pos, true);
      }
    });

    root.addEventListener(
      "blur",
      function (e) {
        var el = e.target;
        if (!isStockField(el)) return;
        var items = splitStockItems(el.value);
        el.value = items.length ? toNumberedText(items, false) : "";
      },
      true
    );

    root.addEventListener("change", function (e) {
      const input = e.target;
      if (input && input.matches('input[type="file"].sheet-photo-input')) {
        updatePhotoLabel(input);
      }
    });

    root.addEventListener("click", function (e) {
      const removeBtn = e.target.closest("[data-sheet-remove-row]");
      if (removeBtn) {
        e.preventDefault();
        const row = removeBtn.closest("tr");
        if (!row || !tbody || tbody.querySelectorAll("tr").length <= 1) return;
        if (!rowLooksBlank(row)) {
          const ok = window.confirm(
            "This row has data. Remove it anyway?\n\nیہ قطار بھری ہوئی ہے — کیا آپ واقعی ہٹانا چاہتے ہیں؟"
          );
          if (!ok) return;
        }
        const cell = row.querySelector(".sheet-photo-cell");
        if (cell && cell._previewUrl) URL.revokeObjectURL(cell._previewUrl);
        row.remove();
        renumberGates(root);
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

    root.addEventListener("submit", function (e) {
      root.querySelectorAll(".gate-stock-input").forEach(prepareStockFieldForSubmit);
      if (!tbody) return;
      renumberGates(root);
      indexFileInputs(root);
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
        tbody.querySelectorAll(".gate-stock-input").forEach(function (el) {
          if (String(el.value || "").trim()) formatStockField(el, false);
        });
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
