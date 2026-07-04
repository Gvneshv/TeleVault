/**
 * App shell controller.
 *
 * Scope of this file, deliberately: switching the visible section when a nav link is clicked, and nothing else.
 * Each section is a static placeholder for now ("this view isn't built yet").
 * Actual data-fetching views (chat list, message feed, deleted tab, stats dashboard) replace these placeholders one at a time in later steps — this file is the
 * seam they plug into, via the same `data-view` / `.app-view` pattern already wired up below.
 *
 * No client-side router or URL hash handling yet.
 * Adding one is a reasonable future step once there are per-item views (e.g. a single chat or message) that benefit from being linkable/bookmarkable
 * — not needed for the nav-only shell.
 */

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
  }

  links.forEach((link) => {
    link.addEventListener("click", () => showView(link.dataset.view));
  });

  // Default view on load.
  showView("chats");
});
