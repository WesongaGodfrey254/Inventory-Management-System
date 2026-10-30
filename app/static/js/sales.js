(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-sale-form]");
    if (!form) return;

    var quantityInputs = form.querySelectorAll(".qty-input");
    var totalOutput = document.getElementById("sale-total");

    function formatMoney(value) {
      return value.toFixed(2);
    }

    function recalculate() {
      var total = 0;

      quantityInputs.forEach(function (input) {
        var price = Number.parseFloat(input.dataset.price) || 0;
        var quantity = Math.max(0, Number.parseInt(input.value, 10) || 0);
        var lineTotal = price * quantity;
        total += lineTotal;

        var cell = document.getElementById("line-total-" + input.dataset.productId);
        if (cell) {
          cell.textContent = formatMoney(lineTotal);
        }
      });

      if (totalOutput) {
        totalOutput.textContent = formatMoney(total);
      }
    }

    quantityInputs.forEach(function (input) {
      input.addEventListener("input", recalculate);
      input.addEventListener("change", recalculate);
    });

    recalculate();
  });
})();
