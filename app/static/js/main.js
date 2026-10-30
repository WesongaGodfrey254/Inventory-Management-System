(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    // Keep the footer year current.
    var year = document.getElementById("app-year");
    if (year) {
      year.textContent = new Date().getFullYear();
    }

    // Mobile navigation.
    var burger = document.querySelector(".navbar-burger");
    if (burger) {
      burger.addEventListener("click", function () {
        var menu = document.getElementById(burger.dataset.target);
        if (!menu) return;
        var isOpen = menu.classList.toggle("is-active");
        burger.classList.toggle("is-active", isOpen);
        burger.setAttribute("aria-expanded", String(isOpen));
      });
    }

    // Dismiss flash messages.
    document.querySelectorAll(".notification .delete").forEach(function (button) {
      button.addEventListener("click", function () {
        var notification = button.closest(".notification");
        if (!notification) return;
        notification.style.transition = "opacity 0.2s ease";
        notification.style.opacity = "0";
        window.setTimeout(function () {
          notification.remove();
        }, 200);
      });
    });

    // Let success/info messages disappear automatically.
    window.setTimeout(function () {
      document.querySelectorAll(".notification").forEach(function (notification) {
        notification.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        notification.style.opacity = "0";
        notification.style.transform = "translateY(-6px)";
        window.setTimeout(function () {
          notification.remove();
        }, 300);
      });
    }, 6000);

    // Client-side table search.
    document.querySelectorAll("[data-table-filter]").forEach(function (input) {
      var table = document.querySelector(input.dataset.tableFilter);
      if (!table) return;
      input.addEventListener("input", function () {
        var term = input.value.toLowerCase().trim();
        table.querySelectorAll("tbody tr").forEach(function (row) {
          row.style.display = row.textContent.toLowerCase().indexOf(term) !== -1 ? "" : "none";
        });
      });
    });

    // Prevent accidental double submits.
    document.querySelectorAll("form[data-loading]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var button = form.querySelector('button[type="submit"], input[type="submit"]');
        if (!button) return;
        button.classList.add("is-loading");
        button.disabled = true;
      });
    });
  });
})();
