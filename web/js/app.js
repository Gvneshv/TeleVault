/**
 * App shell controller.
 *
 * Scope of this file, deliberately:
 * switching the visible section when a nav link is clicked, and delegating each view's lazy initialization — nothing else.
 * Views themselves own their fetching/rendering logic.
 *
 * This is the single ES module entry point for the app (see index.html's one <script type="module" src="/js/app.js">).
 * It imports every view module, which is what actually causes their code to run at all — an unimported ES module's top-level code
 * (e.g. chats.js's own DOMContentLoaded listener) never executes, unlike a classic <script> tag which always runs once loaded.
 * chats.js is imported for that side effect only (it self-initializes as the landing view);
 * the other four export an init() called lazily below, the first time their tab is opened.
 *
 * No client-side router or URL hash handling yet.
 * Adding one is a reasonable future step once there are per-item views (e.g. a single chat or message) that benefit from being linkable/bookmarkable
 * — not needed for the nav-only shell.
 */

import "./views/chats.js";
import { initMessagesView } from "./views/messages.js";
import { initDeletedView } from "./views/deleted.js";
import { initStatsView } from "./views/stats.js";
import { initHealthView } from "./views/health.js";
import { initBackfillView } from "./views/backfill.js";

document.addEventListener("DOMContentLoaded", () => {
  const links = document.querySelectorAll(".app-nav__link[data-view]");
  const views = document.querySelectorAll(".app-view");

  function showView(viewName) {
    views.forEach((view) => {
      view.hidden = view.dataset.view !== viewName;
    });
    links.forEach((link) => {
      if (link.dataset.view === viewName) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });

    // Views other than the landing "chats" tab don't self-initialize on DOMContentLoaded (no point fetching data for a hidden tab).
    // Each exports an init() that's safe to call more than once — the view itself guards against re-initializing.
    if (viewName === "messages") initMessagesView();
    if (viewName === "deleted") initDeletedView();
    if (viewName === "stats") initStatsView();
    if (viewName === "health") initHealthView();
    if (viewName === "backfill") initBackfillView();
  }

  links.forEach((link) => {
    link.addEventListener("click", () => showView(link.dataset.view));
  });

  // Default view on load.
  showView("chats");
});
