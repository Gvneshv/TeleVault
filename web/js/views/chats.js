/**
 * Chats list view.
 *
 * Fetches GET /api/chats (paginated) and renders each chat as a row: name, chat-type badge, message/deleted counts, and a preview of the most recent message.
 * This is the landing view, so it self-initializes on DOMContentLoaded rather than waiting for a nav click.
 *
 * Depends on js/lib/dom.js (escapeHtml) and js/lib/pagination.js (render/attach) — see index.html for load order.
 *
 * Scope, deliberately: list + pagination only.
 * Clicking a row does nothing yet — there's no single-chat or filtered-messages view to send it to.
 * Each row still carries `data-chat-id` so that wiring is a one-line addition once a per-chat view exists, instead of a re-render change here.
 *
 * State is kept minimal and re-fetched fresh on every page change;
 * nothing is cached client-side beyond the last page (see lastData below, kept only for language-switch re-rendering).
 * This is a personal single-user archive, not a high-traffic API,
 * so the extra request per page turn is not a real cost — and it keeps this file free of cache-invalidation logic it doesn't need yet.
 */

const CHATS_PER_PAGE = 50;

/** Mutable view state. Re-created fresh; not persisted across reloads. */
const chatsViewState = {
  page: 1,
  /** Last successfully fetched page from the API, kept so a language change can re-render without re-fetching.
   * Null until the first load. */
  lastData: null,
};

/**
 * Format an ISO 8601 datetime string using the current UI language's locale.
 * Returns an em dash for null/undefined — some chats have no messages yet.
 *
 * @param {string | null} iso
 * @returns {string}
 */
function formatChatTimestamp(iso) {
  if (!iso) return "—";
  const locale =
    window.TeleVaultI18n.getCurrentLang() === "uk" ? "uk-UA" : "en-US";
  try {
    return new Date(iso).toLocaleString(locale, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    // Malformed date from the API shouldn't crash the row — fall back to the raw string.
    return iso;
  }
}

/**
 * Build the initials shown in a chat's avatar circle.
 * Falls back to "?" for chats with no name (possible for some private chats where Telegram never supplied one).
 *
 * @param {string | null} name
 * @returns {string}
 */
function chatInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}

/**
 * Render one chat row as an HTML string.
 * @param {object} chat - a ChatOut record from the API.
 * @returns {string}
 */
function renderChatRow(chat) {
  const t = window.TeleVaultI18n.t;
  const escapeHtml = window.TeleVaultDom.escapeHtml;
  const typeKey = `common.type.${chat.chat_type}`;
  const typeLabel = chat.chat_type ? t(typeKey) : "";

  const deletedBadge =
    chat.deleted_count > 0
      ? `<span class="seal-badge">${chat.deleted_count} ${t("chats.deletedLabel")}</span>`
      : "";

  const preview = chat.last_message_preview
    ? escapeHtml(chat.last_message_preview)
    : `<span class="chat-row__preview--empty">${t("chats.noPreview")}</span>`;

  return `
    <li class="chat-row" data-chat-id="${chat.chat_id}">
      <div class="chat-row__avatar" aria-hidden="true">${chatInitials(chat.name)}</div>
      <div class="chat-row__body">
        <div class="chat-row__top">
          <span class="chat-row__name">${escapeHtml(chat.name ?? String(chat.chat_id))}</span>
          ${typeLabel ? `<span class="chat-type-badge">${typeLabel}</span>` : ""}
        </div>
        <div class="chat-row__preview">${preview}</div>
      </div>
      <div class="chat-row__stats">
        <span class="chat-row__count">${chat.message_count} ${t("chats.messagesLabel")}</span>
        ${deletedBadge}
        <span class="chat-row__timestamp">${formatChatTimestamp(chat.last_message_at)}</span>
      </div>
    </li>
  `;
}

/**
 * Render the view's current state (rows + pagination) from already-fetched data.
 * Pulled out of loadChats() so a language change can call this again with the cached page instead of hitting the API a second time.
 *
 * @param {HTMLElement} root
 * @param {object} data - a PaginatedResponse<ChatOut> from the API.
 */
function renderChatsView(root, data) {
  const t = window.TeleVaultI18n.t;

  if (data.items.length === 0) {
    root.innerHTML = `<div class="empty-state">${t("chats.empty")}</div>`;
    return;
  }

  const rowsHtml = data.items.map(renderChatRow).join("");
  const paginationHtml = window.TeleVaultPagination.render(
    data.page,
    data.pages,
  );

  root.innerHTML = `
    <ul class="chat-list">${rowsHtml}</ul>
    ${paginationHtml}
  `;

  window.TeleVaultPagination.attach(root, (delta) => {
    chatsViewState.page += delta;
    loadChats(root);
  });
}

/** Fetch one page of chats, cache it, and render it. */
async function loadChats(root) {
  const t = window.TeleVaultI18n.t;
  root.innerHTML = `<div class="empty-state">${t("common.loading")}</div>`;

  let data;
  try {
    const res = await fetch(
      `/api/chats?page=${chatsViewState.page}&per_page=${CHATS_PER_PAGE}`,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch {
    root.innerHTML = `<div class="empty-state">${t("common.error")}</div>`;
    return;
  }

  chatsViewState.lastData = data;
  renderChatsView(root, data);
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("chats-root");
  if (root) loadChats(root);
});

// Re-render the already-fetched page in the new language — no re-fetch needed, since only the labels change, not the underlying chat data.
document.addEventListener("televault:langchange", () => {
  const root = document.getElementById("chats-root");
  if (root && chatsViewState.lastData) {
    renderChatsView(root, chatsViewState.lastData);
  }
});
