/* VGPA project page — theme, tabs, lightbox. */
(function () {
  "use strict";

  /* ------------------------------------------------------------ theme -- */
  var root = document.documentElement;
  var toggle = document.getElementById("themeToggle");

  try {
    var saved = localStorage.getItem("vgpa-theme");
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) { /* private mode, blocked storage — fall back to system */ }

  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = root.getAttribute("data-theme");
      if (!current) {
        current = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("vgpa-theme", next); } catch (e) {}
    });
  }

  /* ------------------------------------------------------------- tabs -- */
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab[role=tab]"));

  function selectTab(tab) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      var panel = document.getElementById(t.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    });
  }

  tabs.forEach(function (tab, i) {
    tab.addEventListener("click", function () { selectTab(tab); });
    tab.addEventListener("keydown", function (ev) {
      var d = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      ev.preventDefault();
      var next = tabs[(i + d + tabs.length) % tabs.length];
      next.focus();
      selectTab(next);
    });
  });

  /* --------------------------------------------------------- lightbox -- */
  var lb = document.getElementById("lightbox");
  var lbImg = document.getElementById("lightboxImg");
  var lbClose = document.getElementById("lightboxClose");
  var lastFocus = null;

  function openLightbox(tile) {
    var img = tile.querySelector("img");
    if (!img) return;
    lastFocus = tile;
    lbImg.src = img.src;
    lbImg.alt = img.alt;
    lb.hidden = false;
    lbClose.focus();
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    lb.hidden = true;
    lbImg.src = "";
    document.body.style.overflow = "";
    if (lastFocus) lastFocus.focus();
  }

  Array.prototype.forEach.call(document.querySelectorAll(".tile"), function (tile) {
    tile.addEventListener("click", function () { openLightbox(tile); });
  });

  if (lb) {
    lbClose.addEventListener("click", closeLightbox);
    lb.addEventListener("click", function (ev) {
      if (ev.target === lb) closeLightbox();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !lb.hidden) closeLightbox();
    });
  }

  /* ------------------------------------------------------------- copy -- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-copy]"), function (btn) {
    btn.addEventListener("click", function () {
      var target = document.querySelector(btn.getAttribute("data-copy"));
      if (!target || !navigator.clipboard) return;
      navigator.clipboard.writeText(target.textContent).then(function () {
        var was = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = was; }, 1600);
      });
    });
  });

  /* ---------------------------------------------------- viewer slots --- */
  /* A slot with data-src becomes click-to-load: the iframe is only created
     once the visitor asks for it, so an unopened viewer costs nothing. */
  Array.prototype.forEach.call(document.querySelectorAll(".viewer-slot[data-src]"), function (slot) {
    var label = slot.getAttribute("data-label") || "interactive viewer";
    slot.style.cursor = "pointer";
    slot.innerHTML =
      '<div class="hint"><b>' + label + '</b><span>Click to load the interactive viewer.</span></div>';
    slot.addEventListener("click", function once() {
      var frame = document.createElement("iframe");
      frame.src = slot.getAttribute("data-src");
      frame.title = label;
      frame.loading = "lazy";
      frame.allow = "fullscreen";
      slot.innerHTML = "";
      slot.style.cursor = "";
      slot.style.borderStyle = "solid";
      slot.style.background = "var(--surface-1)";
      slot.appendChild(frame);
      slot.removeEventListener("click", once);
    });
  });
})();
