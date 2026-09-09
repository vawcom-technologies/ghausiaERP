(function () {
    var backdrop = document.querySelector(".mobile-sheet-backdrop");

    function sheetById(id) {
        return id ? document.getElementById(id) : null;
    }

    function closeAll() {
        document.querySelectorAll(".mobile-sheet.is-open").forEach(function (sheet) {
            sheet.classList.remove("is-open");
            sheet.setAttribute("hidden", "");
        });
        document.querySelectorAll(".mobile-dock-item.is-open").forEach(function (item) {
            item.classList.remove("is-open");
            item.setAttribute("aria-expanded", "false");
        });
        if (backdrop) {
            backdrop.classList.remove("is-open");
            backdrop.setAttribute("hidden", "");
        }
        document.body.classList.remove("mobile-sheet-open");
    }

    function openSheet(id, button) {
        var sheet = sheetById(id);
        if (!sheet) return;
        closeAll();
        sheet.removeAttribute("hidden");
        sheet.classList.add("is-open");
        if (button) {
            button.classList.add("is-open");
            button.setAttribute("aria-expanded", "true");
        }
        if (backdrop) {
            backdrop.removeAttribute("hidden");
            backdrop.classList.add("is-open");
        }
        document.body.classList.add("mobile-sheet-open");
    }

    document.querySelectorAll("[data-mobile-open]").forEach(function (button) {
        button.setAttribute("aria-expanded", "false");
    });

    document.addEventListener("click", function (event) {
        var openBtn = event.target.closest("[data-mobile-open]");
        if (openBtn) {
            event.preventDefault();
            var id = openBtn.getAttribute("data-mobile-open");
            if (openBtn.classList.contains("is-open")) {
                closeAll();
            } else {
                openSheet(id, openBtn);
            }
            return;
        }
        if (event.target.closest("[data-mobile-close]")) {
            event.preventDefault();
            closeAll();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeAll();
    });
})();
