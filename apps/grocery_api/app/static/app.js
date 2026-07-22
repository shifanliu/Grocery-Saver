(function () {
  "use strict";

  var STORAGE_KEY = "grocerysaver.basket";

  function loadBasket() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveBasket(basket) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(basket));
  }

  function basketKey(item) {
    return item.store_id + ":" + item.id;
  }

  var basket = loadBasket();

  function render() {
    var listEl = document.getElementById("basket-list");
    var emptyEl = document.getElementById("basket-empty");
    var countEl = document.getElementById("basket-count");
    var suggestBtn = document.getElementById("suggest-recipes-btn");

    countEl.textContent = basket.length;
    listEl.innerHTML = "";

    if (basket.length === 0) {
      emptyEl.style.display = "block";
      suggestBtn.disabled = true;
    } else {
      emptyEl.style.display = "none";
      suggestBtn.disabled = false;
      basket.forEach(function (item) {
        var li = document.createElement("li");

        var name = document.createElement("span");
        name.textContent = item.name;
        li.appendChild(name);

        var removeBtn = document.createElement("button");
        removeBtn.className = "remove";
        removeBtn.textContent = "×";
        removeBtn.setAttribute("aria-label", "Remove " + item.name);
        removeBtn.addEventListener("click", function () {
          removeFromBasket(item);
        });
        li.appendChild(removeBtn);

        listEl.appendChild(li);
      });
    }

    syncButtons();
  }

  function syncButtons() {
    var keys = basket.map(basketKey);
    document.querySelectorAll(".add-to-basket").forEach(function (btn) {
      var item = {
        id: btn.getAttribute("data-item-id"),
        store_id: btn.getAttribute("data-item-store"),
      };
      var inBasket = keys.indexOf(basketKey(item)) !== -1;
      btn.classList.toggle("in-basket", inBasket);
      btn.textContent = inBasket ? "✓ In basket" : "+ Add to basket";
    });
  }

  function addToBasket(item) {
    var key = basketKey(item);
    if (basket.some(function (i) { return basketKey(i) === key; })) {
      return;
    }
    basket.push(item);
    saveBasket(basket);
    render();
  }

  function removeFromBasket(item) {
    var key = basketKey(item);
    basket = basket.filter(function (i) { return basketKey(i) !== key; });
    saveBasket(basket);
    render();
  }

  function setRecipeStatus(message, isError) {
    var el = document.getElementById("recipe-results");
    el.innerHTML =
      '<div class="recipe-status' +
      (isError ? " error" : "") +
      '">' +
      message +
      "</div>";
  }

  function renderRecipes(recipes) {
    var el = document.getElementById("recipe-results");
    el.innerHTML = "";
    if (!recipes || recipes.length === 0) {
      setRecipeStatus("No recipe ideas came back. Try adding more items.", false);
      return;
    }
    recipes.forEach(function (recipe) {
      var card = document.createElement("div");
      card.className = "recipe-card";

      var title = document.createElement("h3");
      title.textContent = recipe.title;
      card.appendChild(title);

      card.appendChild(buildList(
        "Uses from your basket", recipe.uses_basket_items, "ul"
      ));
      card.appendChild(buildList(
        "You'll also need", recipe.additional_ingredients, "ul"
      ));
      card.appendChild(buildList("Steps", recipe.steps, "ol"));

      el.appendChild(card);
    });
  }

  function buildList(label, items, tag) {
    var wrap = document.createElement("div");
    if (!items || items.length === 0) {
      return wrap;
    }
    var labelEl = document.createElement("div");
    labelEl.className = "recipe-section-label";
    labelEl.textContent = label;
    wrap.appendChild(labelEl);

    var listEl = document.createElement(tag);
    items.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      listEl.appendChild(li);
    });
    wrap.appendChild(listEl);
    return wrap;
  }

  function suggestRecipes() {
    var suggestBtn = document.getElementById("suggest-recipes-btn");
    suggestBtn.disabled = true;
    setRecipeStatus("Thinking of recipes...", false);

    fetch("/recipes/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: basket.map(function (i) { return i.name; }) }),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (body) {
            throw new Error(body.detail || "Recipe service unavailable.");
          });
        }
        return res.json();
      })
      .then(function (body) {
        renderRecipes(body.recipes);
      })
      .catch(function (err) {
        setRecipeStatus(err.message || "Recipe service unavailable.", true);
      })
      .finally(function () {
        suggestBtn.disabled = basket.length === 0;
      });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".add-to-basket");
    if (btn) {
      addToBasket({
        id: btn.getAttribute("data-item-id"),
        name: btn.getAttribute("data-item-name"),
        store_id: btn.getAttribute("data-item-store"),
      });
    }
  });

  document.getElementById("suggest-recipes-btn").addEventListener("click", suggestRecipes);

  render();
})();
