/* Motion for thinksynergy.biz.
 *
 * Two rules this file is built around.
 *
 * 1. Nothing here may hide content. Every element starts visible in the
 *    stylesheet. This script opts a page in by putting `js-motion` on <html>,
 *    and only then does the hidden-until-revealed state exist. If the file
 *    fails to load, fails to parse, or the observer is unavailable, the page
 *    renders exactly as it did before any of this was written.
 *
 * 2. A reader who has asked for less motion gets none of it. The stylesheet
 *    already neutralises durations under prefers-reduced-motion; this script
 *    checks the same query and returns before it touches the document, so the
 *    count-ups and the stagger never run at all rather than running instantly.
 */
(function () {
  "use strict";

  var doc = document.documentElement;

  var quiet = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
  if (quiet && quiet.matches) return;
  if (!("IntersectionObserver" in window)) return;

  /* No usable viewport means no scrolling, which means the observer that is
     supposed to reveal this content may never fire. Found on a zero-height
     background tab, where every marked element stayed at opacity 0 forever.
     Print, prerender and thumbnail contexts have the same shape. Motion is
     the optional part here; the words are not. */
  if (!window.innerHeight || window.innerHeight < 200) return;

  /* Groups of elements that should arrive together, in the order they read.
     Each selector is resolved inside its own container so the stagger restarts
     per section rather than counting across the whole page. */
  var GROUPS = [
    [".hero-copy", ":scope > *"],
    [".page-hero", ":scope > *"],
    [".stat-band ul", ":scope > li"],
    [".section-heading", ":scope > *"],
    [".prose-stack", ":scope > *"],
    [".card-grid", ":scope > *"],
    [".flow-strip", ":scope > li"],
    [".method-map", ":scope > *"],
    [".service-list", ":scope > *"],
    [".insight-list", ":scope > *"],
    [".record-list", ":scope > *"],
    [".principle-list", ":scope > *"],
    [".commitment-list", ":scope > *"],
    [".evidence-table tbody", ":scope > tr"],
    [".proof-group", ":scope > *"],
    [".practice-cols", ":scope > *"],
    [".tag-row", ":scope > li"]
  ];

  /* Elements that reveal on their own rather than as part of a run. */
  var SINGLES = [
    ".section-lede", ".service-row", ".case-study", ".system-block",
    ".signal-card", ".credential-card", ".contact-card", ".quality-bar",
    ".estimate-note", ".continuity-note", ".band-note", ".section-footnote",
    ".button-row", ".evidence-table", ".practice-band", ".cta-band > *"
  ];

  var marked = [];

  function mark(el, delay) {
    if (!el || el.hasAttribute("data-r")) return;
    el.setAttribute("data-r", "");
    if (delay) el.style.transitionDelay = delay + "ms";
    marked.push(el);
  }

  GROUPS.forEach(function (pair) {
    Array.prototype.forEach.call(document.querySelectorAll(pair[0]), function (box) {
      var kids = box.querySelectorAll(pair[1]);
      Array.prototype.forEach.call(kids, function (el, i) {
        /* Capped so a long list does not leave its last item waiting. */
        mark(el, Math.min(i * 55, 330));
      });
    });
  });

  SINGLES.forEach(function (sel) {
    Array.prototype.forEach.call(document.querySelectorAll(sel), function (el) {
      mark(el, 0);
    });
  });

  if (!marked.length) return;
  doc.classList.add("js-motion");

  /* ---- Counting the figures up ---------------------------------------
     The numbers are the argument this site makes, so they resolve rather
     than simply appear. The element's final width is measured and pinned
     before the first frame, because a figure that grows from "1" to "13,875"
     while counting would push its own label across the page. */

  function countUp(el) {
    var finalText = el.textContent.trim();
    if (!/^\d[\d,]*$/.test(finalText)) return;
    var target = parseInt(finalText.replace(/,/g, ""), 10);
    if (!isFinite(target) || target < 2) return;

    el.style.display = "inline-block";
    el.style.minWidth = el.getBoundingClientRect().width + "px";
    el.style.fontVariantNumeric = "tabular-nums";

    var grouped = finalText.indexOf(",") !== -1;
    var dur = 900;
    var t0 = null;

    function frame(t) {
      if (t0 === null) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      /* Ease out cubic: fast enough to read as a resolve, slow at the end
         so the last few digits are legible rather than a blur. */
      var eased = 1 - Math.pow(1 - p, 3);
      var v = Math.round(target * eased);
      el.textContent = grouped ? v.toLocaleString("en-US") : String(v);
      if (p < 1) requestAnimationFrame(frame);
      else el.textContent = finalText;
    }
    requestAnimationFrame(frame);
  }

  /* ---- Reveal ---------------------------------------------------------
     unobserve on entry: this is an arrival, not a state that toggles as the
     reader scrolls back up past it. */

  var observerAlive = false;

  /* querySelectorAll, not querySelector. A revealed element is often a column
     holding several figures rather than one figure, and singular lookup counted
     up the first of them and left the rest sitting still. Visible on the home
     page, where the two practice columns hold two figures each. */
  function countUpInside(el) {
    if (el.matches(".stat-figure")) { countUp(el); return; }
    Array.prototype.forEach.call(el.querySelectorAll(".stat-figure"), countUp);
  }

  var io = new IntersectionObserver(function (entries) {
    observerAlive = true;
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      var el = e.target;
      el.classList.add("is-in");
      io.unobserve(el);
      countUpInside(el);
    });
  }, {
    /* Both of these were wrong the first time and each left content permanently
       invisible, which is the only failure this file is not allowed to have.

       rootMargin: a -8% bottom margin means anything that comes to rest inside
       the bottom 8% of the viewport at maximum scroll can never intersect. Three
       elements across the site sat there and never appeared, no matter how far
       the reader scrolled. A small fixed inset gives the same "arrives just
       after it enters" feel without scaling into a dead zone.

       threshold: 0.08 asks for 8% of the ELEMENT to be visible, which an element
       taller than the viewport can never satisfy. On a 390px phone that is an
       ordinary section. Zero means any intersection at all. */
    rootMargin: "0px 0px -48px 0px",
    threshold: 0
  });

  marked.forEach(function (el) { io.observe(el); });

  /* Last line of defence, and the condition is deliberate: it asks whether the
     observer has EVER spoken, not whether anything is visible yet. Observed on
     a browser where IntersectionObserver silently delivers no callbacks at all,
     including for an element plainly in view. In that environment a check on
     "is anything revealed" would be satisfied by the first element and leave
     the rest of the page blank forever. If the observer has not reported once
     by now, the effect is abandoned and everything is shown.

     There is no manual "reveal what is already on screen" pass. A working
     IntersectionObserver fires on observe() for elements already in view, so
     the pass was redundant, and when it ran before layout had settled every
     element measured as being near the top of the page and the whole document
     revealed at once. */
  var allRevealed = false;

  function revealEverything() {
    if (allRevealed) return;
    allRevealed = true;
    marked.forEach(function (el) {
      if (el.classList.contains("is-in")) return;
      el.style.transitionDelay = "0ms";
      el.classList.add("is-in");
      io.unobserve(el);
      countUpInside(el);
    });
  }

  /* A hidden tab is not a broken one. Chrome delivers no IntersectionObserver
     callbacks while document.visibilityState is "hidden", so a page opened in
     a background tab, or restored into one, looks exactly like a page whose
     observer has failed. Giving up there would mean every such page lost the
     effect before the reader ever saw it. So the deadline only starts once the
     document is actually visible, and a page that is still hidden simply waits. */
  function armFailsafe() {
    if (document.hidden) return;
    setTimeout(function () {
      if (observerAlive) return;
      revealEverything();
    }, 1200);
  }

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && !observerAlive) armFailsafe();
  });
  armFailsafe();

  /* Whatever happens, nobody reads a blank page. If the observer has still not
     spoken well after load and the document has been visible for any of it,
     show everything regardless. */
  window.addEventListener("load", function () {
    setTimeout(function () { if (!observerAlive) revealEverything(); }, 4000);
  });

  /* ---- Reading progress and header state ------------------------------ */

  var bar = document.createElement("div");
  bar.className = "read-rail";
  bar.setAttribute("aria-hidden", "true");
  document.body.appendChild(bar);

  var header = document.querySelector(".site-header");
  var ticking = false;

  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      var y = window.scrollY || window.pageYOffset;
      var h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.transform = "scaleX(" + (h > 0 ? Math.min(y / h, 1) : 0) + ")";
      if (header) header.classList.toggle("is-scrolled", y > 24);
      /* At the end of the document there is no more scrolling left to trigger
         anything, so whatever has not arrived by now never will. */
      if (h > 0 && y >= h - 60) revealEverything();
      ticking = false;
    });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();
