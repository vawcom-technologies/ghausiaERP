/**
 * Gate Entry list: first click selects a stock block; second click opens a popup
 * where double-space stock text is shown as a numbered list.
 */
(function () {
  var selected = null;

  function getModal() {
    return document.getElementById("gate-stock-modal");
  }

  function clearSelection() {
    if (selected) {
      selected.classList.remove("is-selected");
      selected = null;
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function splitStockItems(text) {
    var raw = String(text || "").trim();
    if (!raw) return [];

    // Encoded from server: "item one || item two"
    if (raw.indexOf("||") !== -1) {
      return raw
        .split("||")
        .map(function (p) {
          return p.trim();
        })
        .filter(Boolean);
    }

    // Typed as double spaces or newlines
    return raw
      .split(/\s{2,}|\n+/)
      .map(function (p) {
        return p.trim();
      })
      .filter(Boolean);
  }

  function formatItems(text) {
    var parts = splitStockItems(text);
    if (!parts.length) return "<p class='gate-stock-empty'>No items</p>";
    if (parts.length === 1) {
      return "<p class='gate-stock-full-text'>" + escapeHtml(parts[0]) + "</p>";
    }
    return (
      "<ol class='gate-stock-item-list'>" +
      parts
        .map(function (item) {
          return "<li>" + escapeHtml(item) + "</li>";
        })
        .join("") +
      "</ol>"
    );
  }

  function openModal(block) {
    var row = block.closest("[data-gate-row]");
    var modal = getModal();
    if (!row || !modal) return;

    var label = block.getAttribute("data-stock-label") || block.getAttribute("data-stock-key") || "";
    var labelUrdu = block.getAttribute("data-stock-label-urdu") || "";
    var value = block.getAttribute("data-stock-value") || "";

    var meta = document.getElementById("gate-stock-modal-meta");
    var focus = document.getElementById("gate-stock-modal-focus");
    var title = document.getElementById("gate-stock-modal-title");

    if (title) {
      title.textContent = label + (labelUrdu ? " · " + labelUrdu : "");
    }
    if (meta) {
      meta.textContent =
        (row.getAttribute("data-gate") || "") +
        " · " +
        (row.getAttribute("data-date") || "") +
        " · " +
        (row.getAttribute("data-purchaser") || "") +
        " · " +
        (row.getAttribute("data-shop") || "");
    }
    if (focus) {
      focus.innerHTML = formatItems(value);
    }

    modal.hidden = false;
    document.body.classList.add("gate-stock-modal-open");
  }

  function closeModal() {
    var modal = getModal();
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("gate-stock-modal-open");
  }

  document.addEventListener("click", function (e) {
    var closeBtn = e.target.closest("[data-stock-modal-close]");
    if (closeBtn) {
      e.preventDefault();
      closeModal();
      return;
    }

    var block = e.target.closest("[data-stock-block]");
    if (!block || block.disabled) {
      if (!e.target.closest(".gate-stock-modal-dialog")) {
        clearSelection();
      }
      return;
    }

    e.preventDefault();
    if (selected === block) {
      openModal(block);
      return;
    }

    clearSelection();
    selected = block;
    block.classList.add("is-selected");
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeModal();
      clearSelection();
    }
  });
})();
