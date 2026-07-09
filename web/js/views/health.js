/**
 * Health view.
 *
 * Fetches GET /api/health and shows the API's own liveness report:
 * whether the SQLite file is readable, whether a Telethon session exists, and the current archived message count.
 * See api/routes/health.py for exactly what each check does and doesn't cover
 * (notably: it does NOT confirm the userbot is currently connected to Telegram — that needs IPC, a Phase 3 addition per that file's own docstring).
 *
 * No polling — this is a manually-refreshed diagnostic view, not a live dashboard.
 * Deliberately simple: one fetch, one refresh button.
 * Adding auto-refresh is a small change later if it turns out to be wanted, not something to build speculatively now.
 *
 * Lazy-initialized by app.js on first tab open, same pattern as the other non-landing views.
 */

const healthViewState = {
  initialized: false,
};

/**
 * Render the health check results as an HTML string.
 * @param {object} data - a HealthOut record from the API.
 * @returns {string}
 */
function renderHealthReport(data) {
  const t = window.TeleVaultI18n.t;

  const statusLabel =
    data.status === "ok" ? t("health.statusOk") : t("health.statusDegraded");

  const checkRow = (label, passed) => `
    <li class="health-check">
      <span class="health-check__mark" aria-hidden="true">${passed ? "✓" : "✗"}</span>
      <span>${label}</span>
    </li>
  `;

  return `
    <div class="health-status">
      <span class="info-badge">${statusLabel}</span>
    </div>
    <ul class="health-check-list">
      ${checkRow(t("health.dbReadable"), data.db_readable)}
      ${checkRow(t("health.sessionExists"), data.session_exists)}
    </ul>
    <p class="health-message-count">${t("health.messageCount")}: ${data.db_message_count}</p>
    <button id="health-refresh" class="health-refresh-btn" type="button">${t("health.refresh")}</button>
  `;
}

/** Fetch and render the current health report. */
async function loadHealth(root) {
  const t = window.TeleVaultI18n.t;
  root.innerHTML = `<div class="empty-state">${t("common.loading")}</div>`;

  let data;
  try {
    const res = await fetch("/api/health");
    // Not using res.ok here — health.py always returns 200, even when status is "degraded"
    // (that's the point: the body carries the real state, not the HTTP status — see its docstring).
    // A non-200 here means something is more seriously wrong (e.g. 503 if the DB file can't be opened at all), which the catch block below handles.
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch {
    root.innerHTML = `<div class="empty-state">${t("common.error")}</div>`;
    return;
  }

  root.innerHTML = renderHealthReport(data);
  root
    .querySelector("#health-refresh")
    .addEventListener("click", () => loadHealth(root));
}

/** Entry point called by app.js the first time the Health tab is opened. */
function initHealthView() {
  if (healthViewState.initialized) return;
  healthViewState.initialized = true;

  const root = document.getElementById("health-root");
  if (root) loadHealth(root);
}

window.TeleVaultHealthView = { init: initHealthView };

// Re-render on language change.
// Re-fetches (rather than caching like the other views) since this is a live diagnostic — the whole point of a health check is that it reflects the current moment,
// not the last time the tab happened to be opened.
document.addEventListener("televault:langchange", () => {
  if (!healthViewState.initialized) return;
  const root = document.getElementById("health-root");
  if (root) loadHealth(root);
});
