/**
 * List row Delete buttons: confirm popup → POST delete.
 * Works for gate entry and cloth receiving (.gate-action-delete).
 */
(function () {
  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : "";
  }

  function submitDelete(url) {
    var form = document.getElementById("row-delete-form");
    if (!form) {
      form = document.createElement("form");
      form.method = "post";
      form.id = "row-delete-form";
      var csrf = document.createElement("input");
      csrf.type = "hidden";
      csrf.name = "csrfmiddlewaretoken";
      csrf.value = getCookie("csrftoken");
      form.appendChild(csrf);
      document.body.appendChild(form);
    }
    form.action = url;
    form.submit();
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".gate-action-delete");
    if (!btn) return;

    e.preventDefault();
    e.stopPropagation();

    var label = btn.getAttribute("data-delete-label") || "this record";
    var deleteUrl = btn.getAttribute("data-delete-url");
    if (!deleteUrl) return;

    var message =
      btn.getAttribute("data-confirm-message") ||
      "Delete " + label + "?\n\nThis cannot be undone.";

    if (window.confirm(message)) submitDelete(deleteUrl);
  });
})();
