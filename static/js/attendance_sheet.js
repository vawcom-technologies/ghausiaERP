(function () {
  "use strict";

  var root = document.querySelector("[data-attendance-sheet]");
  if (!root) return;

  var tabs = root.querySelectorAll("[data-attendance-day-tabs] [data-day]");
  var label = root.querySelector("[data-active-day-label]");
  var rows = root.querySelectorAll("[data-sheet-row]");
  var activeDay = parseInt(root.getAttribute("data-active-day") || "1", 10);
  var DAY_COUNT = 15;
  var TIME_FIELDS = ["check_in", "check_out"];

  function storeFor(row, day, field) {
    return row.querySelector(
      '[data-day-store="' + day + '"][data-field="' + field + '"]'
    );
  }

  function visibleFor(row, field) {
    return row.querySelector('[data-day-visible="' + field + '"]');
  }

  function parseHours(value) {
    if (value == null || String(value).trim() === "") return 0;
    var n = parseFloat(String(value).replace(",", "."));
    return Number.isFinite(n) ? n : 0;
  }

  function formatHours(n) {
    if (!n) return "";
    return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);
  }

  function minutesFromTime(value) {
    if (!value) return null;
    var parts = String(value).split(":");
    if (parts.length < 2) return null;
    var h = parseInt(parts[0], 10);
    var m = parseInt(parts[1], 10);
    if (!Number.isFinite(h) || !Number.isFinite(m)) return null;
    return h * 60 + m;
  }

  function hoursBetween(checkIn, checkOut) {
    var start = minutesFromTime(checkIn);
    var end = minutesFromTime(checkOut);
    if (start == null || end == null) return "";
    var diff = end - start;
    if (diff < 0) diff += 24 * 60;
    return formatHours(diff / 60);
  }

  function clearDayTimeFields(row, day) {
    TIME_FIELDS.concat(["hours_worked"]).forEach(function (field) {
      var store = storeFor(row, day, field);
      if (store) store.value = "";
      if (day === activeDay) {
        var visible = visibleFor(row, field);
        if (visible) visible.value = "";
      }
    });
  }

  function setDailyTimeFieldsDisabled(row, disabled) {
    TIME_FIELDS.forEach(function (field) {
      var visible = visibleFor(row, field);
      if (visible) {
        visible.disabled = disabled;
      }
    });
    var hours = visibleFor(row, "hours_worked");
    if (hours) {
      hours.disabled = disabled;
    }
  }

  function applyAbsentState(row, options) {
    options = options || {};
    var pa = visibleFor(row, "pa");
    var isAbsent = pa && pa.value === "A";
    row.classList.toggle("is-absent", Boolean(isAbsent));
    setDailyTimeFieldsDisabled(row, isAbsent);

    if (isAbsent && options.clearTimes) {
      clearDayTimeFields(row, activeDay);
      updateCumulativeTotal(row);
    }
  }

  function updateHoursWorkedForDay(row, day) {
    var paStore = storeFor(row, day, "pa");
    var hoursStore = storeFor(row, day, "hours_worked");
    if (!hoursStore) return;

    if (paStore && paStore.value === "A") {
      hoursStore.value = "";
      if (day === activeDay) {
        var visibleHours = visibleFor(row, "hours_worked");
        if (visibleHours) visibleHours.value = "";
      }
      return;
    }

    var checkInStore = storeFor(row, day, "check_in");
    var checkOutStore = storeFor(row, day, "check_out");
    var checkIn = checkInStore ? checkInStore.value : "";
    var checkOut = checkOutStore ? checkOutStore.value : "";
    hoursStore.value = hoursBetween(checkIn, checkOut);

    if (day === activeDay) {
      var visible = visibleFor(row, "hours_worked");
      if (visible) visible.value = hoursStore.value;
    }
  }

  function updateCumulativeTotal(row) {
    var total = 0;
    for (var day = 1; day <= DAY_COUNT; day++) {
      var paStore = storeFor(row, day, "pa");
      if (paStore && paStore.value === "A") continue;
      var store = storeFor(row, day, "hours_worked");
      if (store) total += parseHours(store.value);
    }
    var totalInput = row.querySelector('[name="total_hours"]');
    if (totalInput) {
      totalInput.value = formatHours(total);
    }
  }

  function recalculateRow(row) {
    updateHoursWorkedForDay(row, activeDay);
    updateCumulativeTotal(row);
    applyAbsentState(row);
  }

  function saveVisibleToDay(day) {
    rows.forEach(function (row) {
      var paVisible = visibleFor(row, "pa");
      var paStore = storeFor(row, day, "pa");
      if (paVisible && paStore) {
        paStore.value = paVisible.value;
      }

      if (paStore && paStore.value === "A") {
        clearDayTimeFields(row, day);
      } else {
        TIME_FIELDS.forEach(function (field) {
          var visible = visibleFor(row, field);
          var store = storeFor(row, day, field);
          if (visible && store) {
            store.value = visible.value;
          }
        });
        updateHoursWorkedForDay(row, day);
      }
      updateCumulativeTotal(row);
    });
  }

  function loadDayIntoVisible(day) {
    rows.forEach(function (row) {
      ["pa", "check_in", "check_out", "hours_worked"].forEach(function (field) {
        var visible = visibleFor(row, field);
        var store = storeFor(row, day, field);
        if (visible && store) {
          visible.value = store.value;
        }
      });
      updateCumulativeTotal(row);
      applyAbsentState(row);
    });
  }

  function setActiveTab(day) {
    tabs.forEach(function (tab) {
      var isActive = parseInt(tab.getAttribute("data-day"), 10) === day;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    if (label) {
      label.textContent = "D" + day;
    }
    root.setAttribute("data-active-day", String(day));
  }

  function switchDay(nextDay) {
    if (nextDay === activeDay) return;
    saveVisibleToDay(activeDay);
    activeDay = nextDay;
    loadDayIntoVisible(activeDay);
    setActiveTab(activeDay);
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      switchDay(parseInt(tab.getAttribute("data-day"), 10));
    });
  });

  rows.forEach(function (row) {
    ["pa", "check_in", "check_out"].forEach(function (field) {
      var visible = visibleFor(row, field);
      if (!visible) return;
      function sync() {
        var store = storeFor(row, activeDay, field);
        if (store && !visible.disabled) {
          store.value = visible.value;
        }
        if (field === "pa") {
          if (store) store.value = visible.value;
          applyAbsentState(row, { clearTimes: visible.value === "A" });
          if (visible.value !== "A") {
            updateHoursWorkedForDay(row, activeDay);
            updateCumulativeTotal(row);
          }
          return;
        }
        if (field === "check_in" || field === "check_out") {
          recalculateRow(row);
        }
      }
      visible.addEventListener("change", sync);
      visible.addEventListener("input", sync);
    });
    recalculateRow(row);
  });

  setActiveTab(activeDay);
  loadDayIntoVisible(activeDay);

  // Flush active day into hidden stores before POST save.
  var form = root.closest("form");
  if (form) {
    form.addEventListener("submit", function () {
      saveVisibleToDay(activeDay);
    });
  }
})();
