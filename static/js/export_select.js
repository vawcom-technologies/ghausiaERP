/**
 * Selective Excel export: click Export → checkboxes appear → click/drag select → download.
 *
 * Markup:
 *   <a href="..." data-export-select-trigger data-export-url="...">Export Excel</a>
 *   <table data-export-select-table>
 *     <tr data-export-id="123">...</tr>
 *   </table>
 *   Optional: auto-start with ?export_select=1
 */
(function () {
  "use strict";

  function csrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input && input.value) return input.value;
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function bindRoot(root) {
    var table = root.querySelector("[data-export-select-table]");
    if (!table) return;

    var triggers = root.querySelectorAll("[data-export-select-trigger]");
    if (!triggers.length) return;

    var tbody = table.tBodies[0] || table;
    var theadRow = table.tHead && table.tHead.rows[0] ? table.tHead.rows[0] : null;
    var mode = false;
    var dragging = false;
    var dragValue = true;
    var toolbar = null;
    var selectColCells = [];
    var headerCheckbox = null;

    function dataRows() {
      return Array.prototype.slice.call(tbody.querySelectorAll("tr[data-export-id]"));
    }

    function ensureToolbar() {
      if (toolbar) return toolbar;
      toolbar = document.createElement("div");
      toolbar.className = "export-select-toolbar";
      toolbar.hidden = true;
      toolbar.innerHTML =
        '<div class="export-select-toolbar-inner">' +
        '<span class="export-select-hint"><i class="bi bi-check2-square"></i> Click or drag to select / unselect rows.</span>' +
        '<span class="export-select-count" data-export-count>0 selected</span>' +
        '<button type="button" class="rcv-btn rcv-btn-secondary" data-export-select-all>Select all</button>' +
        '<button type="button" class="rcv-btn rcv-btn-secondary" data-export-clear>Clear</button>' +
        '<button type="button" class="rcv-btn rcv-btn-primary" data-export-download><i class="bi bi-file-earmark-excel"></i> Download Excel</button>' +
        '<button type="button" class="rcv-btn rcv-btn-ghost" data-export-cancel>Cancel</button>' +
        "</div>";
      var anchor = table.closest(".rcv-panel, .card, .sheet-wrap") || table.parentNode;
      if (anchor && anchor.parentNode) {
        anchor.parentNode.insertBefore(toolbar, anchor);
      } else {
        table.parentNode.insertBefore(toolbar, table);
      }

      toolbar.querySelector("[data-export-select-all]").addEventListener("click", function () {
        setAllSelected(true);
      });
      toolbar.querySelector("[data-export-clear]").addEventListener("click", function () {
        setAllSelected(false);
      });
      toolbar.querySelector("[data-export-cancel]").addEventListener("click", exitMode);
      toolbar.querySelector("[data-export-download]").addEventListener("click", downloadSelected);
      return toolbar;
    }

    function checkboxFor(row) {
      return row.querySelector("[data-export-checkbox]");
    }

    function setRowSelected(row, selected) {
      var cb = checkboxFor(row);
      if (cb) cb.checked = selected;
      row.classList.toggle("is-export-selected", selected);
    }

    function setAllSelected(selected) {
      dataRows().forEach(function (row) {
        setRowSelected(row, selected);
      });
      updateCount();
    }

    function updateCount() {
      var rows = dataRows();
      var n = rows.filter(function (row) {
        var cb = checkboxFor(row);
        return cb && cb.checked;
      }).length;
      var el = toolbar && toolbar.querySelector("[data-export-count]");
      if (el) el.textContent = n + " selected";
      if (headerCheckbox) {
        headerCheckbox.checked = rows.length > 0 && n === rows.length;
        headerCheckbox.indeterminate = n > 0 && n < rows.length;
      }
    }

    function isInteractiveTarget(target) {
      if (!target || !target.closest) return false;
      return Boolean(
        target.closest(
          "a, button, input, select, textarea, label, .gate-action-btn, .gate-stock-block"
        )
      );
    }

    function startDragOnRow(row, e) {
      if (!row || !row.getAttribute("data-export-id")) return;
      var cb = checkboxFor(row);
      if (!cb) return;
      dragging = true;
      // If starting on a selected row → drag unselects; otherwise drag selects
      dragValue = !cb.checked;
      setRowSelected(row, dragValue);
      updateCount();
      e.preventDefault();
    }

    function onRowMouseDown(e) {
      if (!mode || e.button !== 0) return;
      var row = e.currentTarget;
      // Allow normal clicks on action links/buttons, but checkbox/label starts drag
      if (isInteractiveTarget(e.target)) {
        if (e.target.closest("[data-export-select-td], [data-export-checkbox], .export-select-label")) {
          startDragOnRow(row, e);
        }
        return;
      }
      startDragOnRow(row, e);
    }

    function onRowEnter(e) {
      if (!dragging || !mode) return;
      var row = e.currentTarget;
      if (!row || !row.getAttribute("data-export-id")) return;
      setRowSelected(row, dragValue);
      updateCount();
    }

    function onMouseUp() {
      dragging = false;
    }

    function enterMode() {
      if (mode) return;
      mode = true;
      root.classList.add("is-export-selecting");
      table.classList.add("export-select-sheet");
      ensureToolbar().hidden = false;

      if (theadRow && !theadRow.querySelector("[data-export-select-th]")) {
        var th = document.createElement("th");
        th.className = "export-select-col";
        th.setAttribute("data-export-select-th", "");
        th.innerHTML =
          '<label class="export-select-label" title="Select all">' +
          '<input type="checkbox" data-export-select-all-cb class="export-select-checkbox" aria-label="Select all rows">' +
          "</label>";
        var headRows = table.tHead ? Array.prototype.slice.call(table.tHead.rows) : [];
        if (headRows.length > 1) {
          th.rowSpan = headRows.length;
        }
        theadRow.insertBefore(th, theadRow.firstChild);
        selectColCells.push(th);
        headerCheckbox = th.querySelector("[data-export-select-all-cb]");
        headerCheckbox.addEventListener("click", function (e) {
          e.stopPropagation();
          setAllSelected(headerCheckbox.checked);
        });
        headerCheckbox.addEventListener("mousedown", function (e) {
          e.stopPropagation();
        });
      } else if (theadRow) {
        headerCheckbox = theadRow.querySelector("[data-export-select-all-cb]");
      }

      dataRows().forEach(function (row) {
        if (row.querySelector("[data-export-select-td]")) return;
        var td = document.createElement("td");
        td.className = "export-select-col";
        td.setAttribute("data-export-select-td", "");
        td.innerHTML =
          '<label class="export-select-label">' +
          '<input type="checkbox" data-export-checkbox class="export-select-checkbox" aria-label="Select row">' +
          "</label>";
        row.insertBefore(td, row.firstChild);
        selectColCells.push(td);

        var cb = td.querySelector("[data-export-checkbox]");
        cb.addEventListener("click", function (e) {
          e.preventDefault();
        });
        row.addEventListener("mousedown", onRowMouseDown);
        row.addEventListener("mouseenter", onRowEnter);
      });

      tbody.querySelectorAll("tr:not([data-export-id]) td[colspan]").forEach(function (td) {
        var n = parseInt(td.getAttribute("colspan") || "1", 10);
        td.setAttribute("data-export-prev-colspan", String(n));
        td.setAttribute("colspan", String(n + 1));
      });

      updateCount();
      document.addEventListener("mouseup", onMouseUp);
    }

    function exitMode() {
      if (!mode) return;
      mode = false;
      dragging = false;
      root.classList.remove("is-export-selecting");
      table.classList.remove("export-select-sheet");
      if (toolbar) toolbar.hidden = true;
      headerCheckbox = null;

      dataRows().forEach(function (row) {
        row.classList.remove("is-export-selected");
        row.removeEventListener("mousedown", onRowMouseDown);
        row.removeEventListener("mouseenter", onRowEnter);
        var td = row.querySelector("[data-export-select-td]");
        if (td) td.remove();
      });
      selectColCells.forEach(function (cell) {
        if (cell && cell.parentNode) cell.parentNode.removeChild(cell);
      });
      selectColCells = [];

      tbody.querySelectorAll("td[data-export-prev-colspan]").forEach(function (td) {
        td.setAttribute("colspan", td.getAttribute("data-export-prev-colspan"));
        td.removeAttribute("data-export-prev-colspan");
      });

      document.removeEventListener("mouseup", onMouseUp);

      if (window.history && window.history.replaceState) {
        var url = new URL(window.location.href);
        if (url.searchParams.has("export_select")) {
          url.searchParams.delete("export_select");
          window.history.replaceState({}, "", url.pathname + url.search + url.hash);
        }
      }
    }

    function activeExportUrl() {
      for (var i = 0; i < triggers.length; i++) {
        var u = triggers[i].getAttribute("data-export-url");
        if (u) return u;
      }
      return triggers[0].getAttribute("href") || "";
    }

    function downloadSelected() {
      var ids = dataRows()
        .filter(function (row) {
          var cb = checkboxFor(row);
          return cb && cb.checked;
        })
        .map(function (row) {
          return row.getAttribute("data-export-id");
        });

      if (!ids.length) {
        window.alert("Select at least one row to export.");
        return;
      }

      var url = activeExportUrl();
      if (!url) {
        window.alert("Export URL is missing.");
        return;
      }

      var form = document.createElement("form");
      form.method = "POST";
      form.action = url;
      form.style.display = "none";

      var csrf = document.createElement("input");
      csrf.type = "hidden";
      csrf.name = "csrfmiddlewaretoken";
      csrf.value = csrfToken();
      form.appendChild(csrf);

      var flag = document.createElement("input");
      flag.type = "hidden";
      flag.name = "export_selected";
      flag.value = "1";
      form.appendChild(flag);

      ids.forEach(function (id) {
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = "ids";
        input.value = id;
        form.appendChild(input);
      });

      var q = new URLSearchParams(window.location.search).get("q");
      if (q) {
        var qInput = document.createElement("input");
        qInput.type = "hidden";
        qInput.name = "q";
        qInput.value = q;
        form.appendChild(qInput);
      }

      document.body.appendChild(form);
      form.submit();
      document.body.removeChild(form);
    }

    triggers.forEach(function (trigger) {
      trigger.addEventListener("click", function (e) {
        e.preventDefault();
        if (!dataRows().length) {
          window.alert("No rows available to export.");
          return;
        }
        enterMode();
      });
    });

    var params = new URLSearchParams(window.location.search);
    if (params.get("export_select") === "1" && dataRows().length) {
      enterMode();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-export-select]").forEach(bindRoot);
  });
})();
