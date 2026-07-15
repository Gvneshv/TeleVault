/**
 * Shared pagination component.
 *
 * Every paginated view (Chats, Messages, Deleted) needs the same prev/next + "page X of Y" control wired to the same PaginatedResponse shape the API always returns.
 * Pulled out here after the second view needed it verbatim — a single bug fix or style change now applies everywhere instead of needing to be repeated per view.
 *
 * First/Last buttons and a direct page-number input only render once there are enough pages that prev/next alone becomes tedious
 * - below that threshold they're just visual clutter for a control nobody needs.
 */

import { t } from "../i18n.js";

const JUMP_THRESHOLD = 10;

/**
 * Build the HTML for a pagination control.
 * Returns an empty string when there's only one page — nothing to paginate, nothing to show.
 *
 * @param {number} page - current page (1-based)
 * @param {number} pages - total page count
 * @returns {string}
 */
function renderPagination(page, pages) {
  if (pages <= 1) return "";

  const showJump = pages > JUMP_THRESHOLD;

  const pageDisplay = showJump
    ? `
      ${t("common.pageOfPrefix")}
      <input
        type="number"
        class="pagination__jump-input"
        min="1"
        max="${pages}"
        value="${page}"
        aria-label="${t("common.jumpToPage")}"
      />
      ${t("common.pageOfSuffix")} ${pages}
    `
    : t("common.pageOf")
        .replace("{page}", String(page))
        .replace("{pages}", String(pages));

  const firstBtn = showJump
    ? `<button class="pagination__btn" data-page-action="first" ${page <= 1 ? "disabled" : ""}>${t("common.first")}</button>`
    : "";
  const lastBtn = showJump
    ? `<button class="pagination__btn" data-page-action="last" ${page >= pages ? "disabled" : ""}>${t("common.last")}</button>`
    : "";

  return `
    <div class="pagination">
      ${firstBtn}
      <button class="pagination__btn" data-page-action="prev" ${page <= 1 ? "disabled" : ""}>
        ${t("common.prev")}
      </button>
      <span class="pagination__info">${pageDisplay}</span>
      <button class="pagination__btn" data-page-action="next" ${page >= pages ? "disabled" : ""}>
        ${t("common.next")}
      </button>
      ${lastBtn}
    </div>
  `;
}

/**
 * Wire up click/submit handlers for a pagination control previously inserted into `root` by renderPagination(). Calls onPageChange(page)
 * with the ABSOLUTE target page number - not a delta.
 * Needed now that first/last/jump all set a specific page directly rather than stepping by one, so prev/next compute their own +-1 from currentPage here too,
 * instead of each view doing its own page arithmetic.
 *
 * @param {HTMLElement} root - container the pagination markup was rendered into
 * @param {number} currentPage
 * @param {number} totalPages
 * @param {(page: number) => void} onPageChange
 */
function attachPaginationHandlers(root, currentPage, totalPages, onPageChange) {
  root.querySelectorAll("[data-page-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.pageAction;
      const target =
        action === "first"
          ? 1
          : action === "last"
            ? totalPages
            : action === "next"
              ? currentPage + 1
              : currentPage - 1;
      onPageChange(target);
    });
  });

  const input = root.querySelector(".pagination__jump-input");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      const target = Math.min(
        Math.max(1, Number(input.value) || 1),
        totalPages,
      );
      onPageChange(target);
    });
    // Losing focus without pressing Enter resets the input back to the current page rather than silently discarding an edited-but-unsubmitted
    // value as if nothing happened, without navigating on every blur (e.g. tabbing past it).
    input.addEventListener("blur", () => {
      input.value = String(currentPage);
    });
  }
}

export { renderPagination as render, attachPaginationHandlers as attach };
