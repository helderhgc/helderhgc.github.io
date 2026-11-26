// Site pessoal — alternância de idioma (PT/EN) e filtros da página de publicações.

(function () {
  "use strict";
  var root = document.documentElement;

  // ---------- Idioma ----------
  function setLang(lang) {
    root.setAttribute("data-lang", lang);
    root.setAttribute("lang", lang === "pt" ? "pt-BR" : "en");
    try { localStorage.setItem("lang", lang); } catch (e) {}
    var btn = document.querySelector(".lang-toggle");
    if (btn) {
      btn.textContent = lang === "pt" ? "EN" : "PT";
      btn.setAttribute("aria-label", lang === "pt" ? "Switch to English" : "Mudar para português");
    }
    var search = document.getElementById("pub-search");
    if (search) search.placeholder = search.getAttribute("data-placeholder-" + lang);
    var title = document.querySelector("meta[name='title-" + lang + "']");
    if (title) document.title = title.content;
  }

  var saved = null;
  try { saved = localStorage.getItem("lang"); } catch (e) {}
  var initial = saved || ((navigator.language || "pt").toLowerCase().indexOf("pt") === 0 ? "pt" : "en");
  setLang(initial);

  document.addEventListener("click", function (ev) {
    if (ev.target.closest(".lang-toggle")) {
      setLang(root.getAttribute("data-lang") === "pt" ? "en" : "pt");
    }
  });

  // ---------- Rodapé: ano atual ----------
  var y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();

  // ---------- Publicações: busca e filtro por tipo ----------
  var search = document.getElementById("pub-search");
  var pubs = Array.prototype.slice.call(document.querySelectorAll(".pub"));
  if (!search || !pubs.length) return;

  var filters = Array.prototype.slice.call(document.querySelectorAll(".filter"));
  var years = Array.prototype.slice.call(document.querySelectorAll(".pub-year"));
  var cats = Array.prototype.slice.call(document.querySelectorAll(".pub-cat"));
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".cat-tab"));
  var countEl = document.getElementById("pub-count-n");
  var activeType = "all";
  var activeCat = "all";

  // Categoria pela âncora do endereço: #indexadas, #nao-indexadas, #preprints
  function catFromHash() {
    var h = location.hash.replace("#", "");
    var map = { "indexadas": "indexada", "nao-indexadas": "nao_indexada", "preprints": "preprint" };
    activeCat = map[h] || "all";
    tabs.forEach(function (t) { t.setAttribute("aria-current", String(t.getAttribute("data-cat") === activeCat)); });
  }
  window.addEventListener("hashchange", function () { catFromHash(); apply(); });
  tabs.forEach(function (t) {
    t.addEventListener("click", function (ev) {
      ev.preventDefault();
      history.replaceState(null, "", t.getAttribute("href"));
      catFromHash(); apply();
    });
  });
  catFromHash();

  function normalize(s) {
    return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  pubs.forEach(function (p) { p._text = normalize(p.textContent); });

  function apply() {
    var q = normalize(search.value.trim());
    var shown = 0;
    pubs.forEach(function (p) {
      var ok = (activeType === "all" || p.getAttribute("data-group") === activeType) &&
               (!q || p._text.indexOf(q) !== -1);
      p.hidden = !ok;
      if (ok) shown++;
    });
    cats.forEach(function (c) {
      var off = activeCat !== "all" && c.getAttribute("data-cat") !== activeCat;
      c.querySelectorAll(".pub").forEach(function (p) {
        if (off && !p.hidden) { p.hidden = true; shown--; }
      });
    });
    years.forEach(function (sec) {
      sec.hidden = !sec.querySelector(".pub:not([hidden])");
    });
    cats.forEach(function (c) {
      c.hidden = !c.querySelector(".pub:not([hidden])");
    });
    if (countEl) countEl.textContent = shown;
  }

  filters.forEach(function (b) {
    b.addEventListener("click", function () {
      activeType = b.getAttribute("data-filter");
      filters.forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
      apply();
    });
  });
  search.addEventListener("input", apply);
  apply();
})();
