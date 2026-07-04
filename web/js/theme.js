/**
 * Theme management: light/dark via `data-theme` on <html>.
 *
 * Resolution order for the initial theme:
 *   1. Explicit user choice, persisted in localStorage under THEME_KEY.
 *   2. OS-level preference (prefers-color-scheme).
 *   3. "light" as the final fallback.
 *
 * This module is intentionally framework-free and has no dependencies — it runs before anything else so the correct theme applies on first paint
 * (avoids a flash of the wrong theme).
 */

const THEME_KEY = "televault:theme";

/** @returns {"light" | "dark"} */
function getPreferredTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
}

/** @param {"light" | "dark"} theme */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.textContent = theme === "dark" ? "☾" : "☀";
    toggle.setAttribute(
      "aria-label",
      theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
    );
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
}

// Apply immediately on script load (not on DOMContentLoaded) to avoid a flash of unstyled/wrong-theme content.
applyTheme(getPreferredTheme());

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", toggleTheme);
  }
});
