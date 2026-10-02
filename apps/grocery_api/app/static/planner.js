(function () {
  "use strict";

  // Everything user- or model-derived is inserted with textContent, never innerHTML.

  var INGREDIENTS = ["rice", "beans", "tomatoes", "onion", "potatoes", "eggs", "tofu",
    "broccoli", "carrots", "pasta", "tortillas", "chicken", "oats"];
  var UNITS = ["g", "kg", "oz", "lb", "ml", "l", "count", "dozen"];
  var EXAMPLES = [
    "Plan a vegetarian dinner for 2 under $40. I have 500 g of onions.",
    "Vegan dinner for 4, budget $15",
    "High-protein meal for 1 under $25",
    "Vegan high-protein dinner for 2, budget $50",
  ];
  var STATUS_TITLES = {
    success: "Plan ready",
    over_budget: "Over budget",
    no_results: "No products found",
    unsupported_data: "Can't price this safely",
    service_unavailable: "Product data unavailable",
    model_unavailable: "Model unavailable",
    invalid_request: "Request not valid",
  };

  var logEl = document.getElementById("planner-log");
  var inputEl = document.getElementById("planner-input");
  var sendBtn = document.getElementById("planner-send");
  var modeEl = document.getElementById("planner-mode");
  var pending = null; // conversation state: fields collected so far (server re-validates it)
  var busy = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  function money(v) {
    var n = Number(v);
    return isFinite(n) ? "$" + n.toFixed(2) : "n/a";
  }

  function qty(v) {
    var n = Number(v);
    return isFinite(n) ? String(Math.round(n * 10) / 10) : "?";
  }

  function addMessage(role, content) {
    var wrap = el("div", "planner-msg planner-" + role);
    if (typeof content === "string") wrap.appendChild(el("p", null, content));
    else wrap.appendChild(content);
    logEl.appendChild(wrap);
    logEl.scrollTop = logEl.scrollHeight;
    return wrap;
  }

  function setBusy(on) {
    busy = on;
    sendBtn.disabled = on;
    document.getElementById("pf-submit").disabled = on;
    inputEl.disabled = on;
    sendBtn.textContent = on ? "Planning..." : "Send";
  }

  // ---------- links: only same-site product pages or verified http(s) retailer URLs ----------

  function safeInternalUrl(u) {
    return typeof u === "string" && /^\/products\/[A-Za-z0-9_.%:\-]+$/.test(u) ? u : null;
  }

  function safeRetailerUrl(u) {
    if (typeof u !== "string") return null;
    try {
      var p = new URL(u);
      return p.protocol === "https:" || p.protocol === "http:" ? p.href : null;
    } catch (e) {
      return null;
    }
  }

  function productCell(li) {
    var td = el("td");
    td.appendChild(el("div", "pl-name", li.product_name));
    var internal = safeInternalUrl(li.product_url);
    var external = safeRetailerUrl(li.retailer_url);
    if (internal) {
      var a = el("a", "pl-link", "View product details");
      a.href = internal;
      a.target = "_blank";
      a.rel = "noopener";
      td.appendChild(a);
    }
    if (external) {
      var b = el("a", "pl-link", "View at retailer");
      b.href = external;
      b.target = "_blank";
      b.rel = "noopener noreferrer";
      td.appendChild(b);
    }
    return td;
  }

  // ---------- result rendering ----------

  function pretty(id) {
    return String(id || "").replace(/_/g, " ");
  }

  function renderResult(result, notes) {
    var box = el("div", "pl-result");
    var status = result.status;
    var head = el("div", "pl-status pl-status-" + status, STATUS_TITLES[status] || status);
    box.appendChild(head);
    box.appendChild(el("p", "pl-message", result.message));

    var cost = result.cost;
    if (cost && cost.line_items) {
      var plan = result.plan || {};
      var req = result.request || {};
      var title = status === "over_budget" ? "Cheapest option tried: " : "";
      box.appendChild(el("h3", "pl-meal",
        title + (plan.name || "Meal") + " for " + (plan.people || req.people) + " people"));
      if (plan.est_protein_g_per_serving) {
        box.appendChild(el("p", "pl-note", "Approx. " + plan.est_protein_g_per_serving +
          " g protein per serving (rough estimate from typical food values; not nutrition advice)."));
      }
      box.appendChild(el("p", "pl-budget",
        "Budget " + money(req.budget) + " | Purchase total " + money(cost.total)));

      var table = el("table", "pl-table");
      var thead = el("thead");
      var hr = el("tr");
      ["Product", "Buy", "Package price", "Line total"].forEach(function (h) {
        hr.appendChild(el("th", null, h));
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      var tbody = el("tbody");
      cost.line_items.forEach(function (li) {
        var tr = el("tr");
        tr.appendChild(productCell(li));
        var buy = li.packages_needed > 0
          ? li.packages_needed + " x " + li.package_size
          : "none (pantry covers it)";
        tr.appendChild(el("td", null, buy));
        tr.appendChild(el("td", null, money(li.unit_price)));
        tr.appendChild(el("td", null, money(li.line_total)));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      var scroll = el("div", "pl-table-wrap");
      scroll.appendChild(table);
      box.appendChild(scroll);
      box.appendChild(el("p", "pl-note",
        "Total = whole packages you must buy, excluding tax and fees. It is not the prorated cost of what is eaten."));

      var used = cost.line_items.filter(function (li) { return Number(li.pantry_deducted) > 0; });
      if (used.length) {
        box.appendChild(el("p", "pl-pantry", "From your pantry: " + used.map(function (li) {
          return li.ingredient + " (" + qty(li.pantry_deducted) + " " + li.base_unit + ")";
        }).join(", ")));
      }
      (cost.pantry_notes || []).forEach(function (n) { box.appendChild(el("p", "pl-note", n)); });
    }

    var attempts = result.attempts || [];
    if (attempts.length > 1) {
      var ul = el("ul", "pl-attempts");
      attempts.forEach(function (a, i) {
        var text = (i === 0 ? "Initial: " : "Adjustment " + i + ": ") + pretty(a.template_id) + " - " +
          (a.status === "ok" ? money(a.total) : "could not be priced");
        ul.appendChild(el("li", null, text));
      });
      box.appendChild(el("p", "pl-note", "Budget adjustments (at most 2 are tried):"));
      box.appendChild(ul);
    }

    var data = result.data || {};
    var meta = el("p", "pl-meta");
    meta.textContent = "Data: " + data.mode + " | " + data.label + " | price date " +
      ((data.price_dates || []).join(", ") || "n/a") + " | planner: " + result.planner_mode;
    box.appendChild(meta);
    (data.warnings || []).forEach(function (w) { box.appendChild(el("p", "pl-warn", "Warning: " + w)); });
    (notes || []).forEach(function (n) { box.appendChild(el("p", "pl-note", n)); });

    var det = el("details", "pl-trace");
    det.appendChild(el("summary", null, "Execution trace"));
    var pre = el("pre");
    pre.textContent = (result.trace || []).map(function (t, i) { return (i + 1) + ". " + t; }).join("\n");
    det.appendChild(pre);
    box.appendChild(det);
    return box;
  }

  // ---------- talking to the server ----------

  function post(path, payload) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 90000);
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) {
          var d = body && body.detail;
          if (Array.isArray(d)) d = d.map(function (x) { return x.msg; }).join("; ");
          throw new Error(d || "Request failed (HTTP " + res.status + ").");
        }
        return body;
      });
    }).catch(function (err) {
      if (err.name === "AbortError") throw new Error("The planner took too long to answer.");
      throw err;
    }).finally(function () { clearTimeout(timer); });
  }

  function handleResponse(body) {
    if (body.pending) pending = body.pending;
    if (body.kind === "ask") {
      addMessage("bot", body.message);
      (body.notes || []).forEach(function (n) { addMessage("bot", n); });
    } else if (body.kind === "error") {
      addMessage("error", body.message || "Something went wrong.");
    } else if (body.kind === "result" && body.result) {
      addMessage("bot", renderResult(body.result, body.notes));
    } else {
      addMessage("error", "Unexpected response from the planner.");
    }
  }

  function showError(err) {
    addMessage("error", err.message || "The planner is unavailable.");
  }

  function sendChat(text) {
    if (busy) return;
    text = (text || "").trim();
    if (!text) return;
    addMessage("user", text);
    setBusy(true);
    post("/planner/chat", { message: text, pending: pending, planner: modeEl.value })
      .then(handleResponse)
      .catch(showError)
      .finally(function () { setBusy(false); inputEl.focus(); });
  }

  document.getElementById("planner-chat-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var text = inputEl.value;
    if (!text.trim() || busy) return;
    inputEl.value = "";
    sendChat(text);
  });

  // ---------- example prompts, reset ----------

  var exWrap = document.getElementById("planner-examples");
  EXAMPLES.forEach(function (text) {
    var b = el("button", "planner-chip", text);
    b.type = "button";
    b.addEventListener("click", function () { inputEl.value = text; inputEl.focus(); });
    exWrap.appendChild(b);
  });

  document.getElementById("planner-reset").addEventListener("click", function () {
    if (busy) return;
    pending = null;
    logEl.innerHTML = "";
    greet();
  });

  function greet() {
    addMessage("bot", "Hi! Tell me your budget, how many people, any diet (vegetarian or vegan) and what you already have at home.");
  }

  // ---------- structured form (explicit fallback, no language model needed) ----------

  var pantryWrap = document.getElementById("pf-pantry");

  function addPantryRow() {
    var row = el("div", "pf-row");
    var sel = el("select");
    sel.setAttribute("aria-label", "Ingredient");
    INGREDIENTS.forEach(function (i) { var o = el("option", null, i); o.value = i; sel.appendChild(o); });
    var q = el("input");
    q.type = "number"; q.min = "0.01"; q.step = "any"; q.placeholder = "amount";
    q.setAttribute("aria-label", "Amount");
    var u = el("select");
    u.setAttribute("aria-label", "Unit");
    UNITS.forEach(function (x) { var o = el("option", null, x); o.value = x; u.appendChild(o); });
    var rm = el("button", "planner-secondary", "x");
    rm.type = "button";
    rm.setAttribute("aria-label", "Remove pantry item");
    rm.addEventListener("click", function () { row.remove(); });
    [sel, q, u, rm].forEach(function (n) { row.appendChild(n); });
    pantryWrap.appendChild(row);
  }

  document.getElementById("pf-add-pantry").addEventListener("click", addPantryRow);

  document.getElementById("planner-struct-form").addEventListener("submit", function (e) {
    e.preventDefault();
    if (busy) return;
    var pantry = [];
    var bad = false;
    pantryWrap.querySelectorAll(".pf-row").forEach(function (row) {
      var f = row.querySelectorAll("select, input");
      var amount = parseFloat(f[1].value);
      if (!(amount > 0)) { bad = true; return; }
      pantry.push({ ingredient: f[0].value, quantity: amount, unit: f[2].value });
    });
    if (bad) { addMessage("error", "Every pantry row needs an amount greater than 0."); return; }
    var diet = document.getElementById("pf-diet").value;
    var payload = {
      budget: parseFloat(document.getElementById("pf-budget").value),
      people: parseInt(document.getElementById("pf-people").value, 10),
      dietary_preferences: diet ? diet.split(",") : [],
      pantry: pantry,
      planner: modeEl.value,
    };
    addMessage("user", "Form: $" + payload.budget + ", " + payload.people + " people, " +
      (diet || "no diet preference") + (pantry.length ? ", pantry: " + pantry.map(function (p) {
        return p.quantity + " " + p.unit + " " + p.ingredient; }).join(", ") : ""));
    setBusy(true);
    post("/planner/plan", payload)
      .then(handleResponse)
      .catch(showError)
      .finally(function () { setBusy(false); });
  });

  greet();
})();
