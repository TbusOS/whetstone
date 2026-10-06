/* whetstone docs — shared behaviour: EN/中 toggle + reveal-on-scroll.
 * The <head> of every page sets data-lang before first paint; this file wires the toggle,
 * exposes window.WS for page scripts, and fires a "langchange" event on every switch. */
(function () {
  'use strict';
  var html = document.documentElement;
  var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var hasIO = 'IntersectionObserver' in window;
  var lang = html.getAttribute('data-lang') === 'zh' ? 'zh' : 'en';

  function setLang(l) {
    lang = l;
    html.setAttribute('data-lang', l);
    html.setAttribute('lang', l === 'zh' ? 'zh-CN' : 'en');
    try { localStorage.setItem('whetstone-lang', l); } catch (e) {}
    document.querySelectorAll('.lang').forEach(function (b) { b.textContent = l === 'zh' ? 'EN / 中' : '中 / EN'; });
    document.querySelectorAll('.en-svg').forEach(function (t) { t.style.display = l === 'en' ? '' : 'none'; });
    document.querySelectorAll('.zh-svg').forEach(function (t) { t.style.display = l === 'zh' ? '' : 'none'; });
    document.dispatchEvent(new Event('langchange'));
  }

  var revealObs = hasIO && !reduce ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); revealObs.unobserve(e.target); } });
  }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }) : null;
  function reveal(el) { if (revealObs) revealObs.observe(el); else el.classList.add('in'); }

  /* run fn(true/false) as el enters / leaves the screen */
  function onScreen(el, fn) {
    if (!hasIO) { fn(true); return; }
    new IntersectionObserver(function (es) { es.forEach(function (e) { fn(e.isIntersecting); }); }, { threshold: 0.05 }).observe(el);
  }

  window.WS = {
    T: function (o) { return o[lang] || o.en; },
    lang: function () { return lang; },
    reduce: reduce,
    hasIO: hasIO,
    onScreen: onScreen,
    reveal: reveal
  };

  document.querySelectorAll('.lang').forEach(function (b) {
    b.addEventListener('click', function () { setLang(lang === 'zh' ? 'en' : 'zh'); });
  });
  document.querySelectorAll('.rv').forEach(reveal);
  setLang(lang);
})();
