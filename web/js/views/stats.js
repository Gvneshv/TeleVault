/**
 * Stats view.
 *
 * Fetches GET /api/stats once and renders:
 *   - Global totals as a row of stat cards (messages, deleted, edited, chats, senders, archiving-since date)
 *   - A per-chat breakdown table, already sorted by message_count descending by the API — not re-sorted client-side.
 *
 * Percentages (deleted/edited as a % of total messages) are computed here,
 * not returned by the API — StatsOut's own docstring says this is deliberate, to avoid float precision noise in the API response.
 *
 * No filters, no pagination — this is a single-fetch dashboard, not a list view.
 * Lazy-initialized by app.js on first tab open, same pattern as the other non-landing views.
 */

const statsViewState = {
  initialized: false,
  lastData: null,
};

/**
 * Format a percentage for display, rounded to a whole number. Returns "0%" for a zero total rather than dividing by zero.
 * @param {number} part
 * @param {number} total
 * @returns {string}
 */
function formatPercent(part, total) {
  if (!total) return "0%";
  return `${Math.round((part / total) * 100)}%`;
}

/** @param {string | null} iso @returns {string} */
function formatStatsDate(iso) {
  if (!iso) return "—";
  const locale =
    window.TeleVaultI18n.getCurrentLang() === "uk" ? "uk-UA" : "en-US";
  try {
    return new Date(iso).toLocaleDateString(locale, { dateStyle: "medium" });
  } catch {
    return iso;
  }
}

/**
 * Render the global totals as a row of stat cards.
 * @param {object} data - a StatsOut record from the API.
 * @returns {string}
 */
function renderStatCards(data) {
  const t = window.TeleVaultI18n.t;

  const card = (label, value) => `
    <div class="stat-card">
      <span class="stat-card__value">${value}</span>
      <span class="stat-card__label">${label}</span>
    </div>
  `;

  return `
    <div class="stat-card-grid">
      ${card(t("stats.totalMessages"), data.total_messages)}
      ${card(t("stats.totalDeleted"), `${data.total_deleted} (${formatPercent(data.total_deleted, data.total_messages)})`)}
      ${card(t("stats.totalEdited"), `${data.total_edited} (${formatPercent(data.total_edited, data.total_messages)})`)}
      ${card(t("stats.totalChats"), data.total_chats)}
      ${card(t("stats.totalSenders"), data.total_senders)}
      ${card(t("stats.archivingSince"), formatStatsDate(data.archiving_since))}
    </div>
  `;
}

/**
 * Render the per-chat breakdown as a table.
 * @param {object[]} perChat - list of ChatStatRow records.
 * @returns {string}
 */
function renderPerChatTable(perChat) {
  const t = window.TeleVaultI18n.t;
  const escapeHtml = window.TeleVaultDom.escapeHtml;

  if (perChat.length === 0) {
    return `<div class="empty-state">${t("stats.empty")}</div>`;
  }

  const rows = perChat
    .map((row) => {
      const typeLabel = row.chat_type ? t(`common.type.${row.chat_type}`) : "";
      return `
        <tr>
          <td>
            ${escapeHtml(row.name ?? String(row.chat_id))}
            ${typeLabel ? `<span class="info-badge">${typeLabel}</span>` : ""}
          </td>
          <td class="stats-table__num">${row.message_count}</td>
          <td class="stats-table__num">${row.deleted_count}</td>
          <td class="stats-table__num">${row.edited_count}</td>
          <td class="stats-table__date">${formatStatsDate(row.last_message_at)}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="stats-table-wrapper">
      <table class="stats-table">
        <thead>
          <tr>
            <th>${t("stats.tableChat")}</th>
            <th class="stats-table__num">${t("stats.tableMessages")}</th>
            <th class="stats-table__num">${t("stats.tableDeleted")}</th>
            <th class="stats-table__num">${t("stats.tableEdited")}</th>
            <th class="stats-table__date">${t("stats.tableLastSeen")}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

/**
 * Render the view's current state from already-fetched data — used both after loading and after a language change
 * (no re-fetch needed for a language switch; the underlying stats haven't changed).
 *
 * @param {HTMLElement} root
 * @param {object} data - a StatsOut record from the API.
 */
function renderStatsView(root, data) {
  const t = window.TeleVaultI18n.t;

  root.innerHTML = `
    ${renderStatCards(data)}
    <h2 class="stats-section-title">${t("stats.perChatTitle")}</h2>
    ${renderPerChatTable(data.per_chat)}
  `;
}

/** Fetch stats once, cache, and render. */
async function loadStats(root) {
  const t = window.TeleVaultI18n.t;
  root.innerHTML = `<div class="empty-state">${t("common.loading")}</div>`;

  let data;
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch {
    root.innerHTML = `<div class="empty-state">${t("common.error")}</div>`;
    return;
  }

  statsViewState.lastData = data;
  renderStatsView(root, data);
}

/** Entry point called by app.js the first time the Stats tab is opened. */
function initStatsView() {
  if (statsViewState.initialized) return;
  statsViewState.initialized = true;

  const root = document.getElementById("stats-root");
  if (root) loadStats(root);
}

window.TeleVaultStatsView = { init: initStatsView };

document.addEventListener("televault:langchange", () => {
  if (!statsViewState.initialized) return;
  const root = document.getElementById("stats-root");
  if (root && statsViewState.lastData) {
    renderStatsView(root, statsViewState.lastData);
  }
});
