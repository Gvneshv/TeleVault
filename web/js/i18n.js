/**
 * Minimal i18n helper.
 *
 * Translation tables are plain objects loaded via <script> tags (js/i18n/en.js, js/i18n/uk.js) onto window.TELEVAULT_I18N before this file runs
 * — see index.html for load order.
 * No bundler, no fetch: this keeps the app usable offline (relevant once the service worker caches it) and avoids a flash of untranslated content
 * while a JSON file loads.
 *
 * Adding a new language later: create js/i18n/<code>.js following the same window.TELEVAULT_I18N.<code> = {...} pattern, 
 * add a <script> tag for it in index.html, and add an <option> in the language <select>.
 */

const LANG_KEY = "televault:lang";
const DEFAULT_LANG = "en";
const SUPPORTED_LANGS = ["en", "uk"];

function detectBrowserLang() {
  const nav = (navigator.language || DEFAULT_LANG).slice(0, 2).toLowerCase();
  return SUPPORTED_LANGS.includes(nav) ? nav : DEFAULT_LANG;
}

/** @returns {string} */
function getCurrentLang() {
  const stored = localStorage.getItem(LANG_KEY);
  return stored && SUPPORTED_LANGS.includes(stored)
    ? stored
    : detectBrowserLang();
}

/**
 * Translate a key using the current language, falling back to English, then to the raw key itself if no table has it.
 * A missing key is a content gap, not a crash — the raw key is visible enough to catch in review without breaking the page for the user.
 *
 * @param {string} key
 * @returns {string}
 */
function t(key) {
  const lang = getCurrentLang();
  const table = window.TELEVAULT_I18N?.[lang];
  const fallback = window.TELEVAULT_I18N?.[DEFAULT_LANG];
  return table?.[key] ?? fallback?.[key] ?? key;
}

/** Re-applies translations to every element with a data-i18n attribute. */
function applyTranslations() {
  document.documentElement.setAttribute("lang", getCurrentLang());
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria-label")));
  });
}

function setLang(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) return;
  localStorage.setItem(LANG_KEY, lang);
  applyTranslations();
}

window.TeleVaultI18n = {
  t,
  applyTranslations,
  setLang,
  getCurrentLang,
  SUPPORTED_LANGS,
};

document.addEventListener("DOMContentLoaded", () => {
  applyTranslations();
  const select = document.getElementById("lang-select");
  if (select) {
    select.value = getCurrentLang();
    select.addEventListener("change", (e) => setLang(e.target.value));
  }
});
