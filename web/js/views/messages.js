/**
 * Messages global feed view.
 *
 * Fetches GET /api/messages (paginated, newest first) and renders each row:
 * sender, chat + type badge, message text, send timestamp, and an "edited" badge when applicable.
 * Deleted messages never appear here — the API's only_deleted=False is hardcoded on the backend for this endpoint;
 * they live in the separate Deleted tab by design (see api/routes/deleted.py).
 *
 * Filters supported now: free-text search (q) and an "edited only" toggle.
 * Matches from `q` are highlighted inline within message text via TeleVaultDom.highlightMatches() (js/lib/dom.js),
 * using the --color-highlight-bg token (see variables.css) — separate from the seal/patina tokens, which stay reserved for deleted/edited semantics.
 * chat_id/sender_id/date_from/date_to are in the API already but have no UI here yet — there's no per-chat or per-sender entry point to populate them from.
 * Wiring chat_id is a small addition once chat rows become clickable (see the `data-chat-id` note in chats.js).
 *
 * Depends on js/lib/dom.js and js/lib/pagination.js — see index.html for load order.
 * Does not self-initialize on DOMContentLoaded like chats.js does,
 * since this isn't the landing view — app.js's showView() calls initMessagesView() the first time the Messages tab is opened.
 */

const MESSAGES_PER_PAGE = 50;
const SEARCH_DEBOUNCE_MS = 300;

/** Mutable view state. Re-created fresh; not persisted across reloads. */
const messagesViewState = {
  page: 1,
  q: "",
  onlyEdited: false,
  lastData: null,
  /** True once initMessagesView() has run — guards against re-initializing (and re-registering event listeners) if the Messages tab is opened more than once. */
  initialized: false,
};

let searchDebounceTimer = null;

/**
 * Resolve the best human-readable sender name available, mirroring the priority order documented on SenderOut.resolved_name in api/schemas/message.py:
 * display_name -> first+last -> first -> @username -> str(sender_id).
 * Kept in sync with that backend logic; if it changes there, change here too.
 *
 * @param {object | null} sender - a SenderOut record, or null.
 * @returns {string}
 */
function resolveSenderName(sender) {
  if (!sender) return "—";
  if (sender.display_name) return sender.display_name;
  const full = [sender.first_name, sender.last_name].filter(Boolean).join(" ");
  if (full) return full;
  if (sender.username) return `@${sender.username}`;
  return String(sender.sender_id);
}

/**
 * Format an ISO 8601 datetime using the current UI language's locale.
 * @param {string | null} iso
 * @returns {string}
 */
function formatMessageTimestamp(iso) {
  if (!iso) return "—";
  const locale =
    window.TeleVaultI18n.getCurrentLang() === "uk" ? "uk-UA" : "en-US";
  try {
    return new Date(iso).toLocaleString(locale, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

/**
 * Render one message row as an HTML string.
 * @param {object} msg - a MessageOut record from the API.
 * @returns {string}
 */
function renderMessageRow(msg) {
  const t = window.TeleVaultI18n.t;
  const escapeHtml = window.TeleVaultDom.escapeHtml;

  const chatTypeLabel = msg.chat?.chat_type
    ? t(`common.type.${msg.chat.chat_type}`)
    : "";
  const chatName = msg.chat
    ? escapeHtml(msg.chat.name ?? String(msg.chat.chat_id))
    : "—";

  const editedBadge = msg.is_edited
    ? `<span class="patina-badge">${t("messages.editedLabel")}</span>`
    : "";

  const text = msg.text
    ? window.TeleVaultDom.highlightMatches(
        escapeHtml(msg.text),
        messagesViewState.q,
      )
    : `<span class="message-row__text--empty">${t("messages.noText")}</span>`;

  return `
    <li class="message-row" data-chat-id="${msg.chat?.chat_id ?? ""}">
      <div class="message-row__meta">
        <span class="message-row__sender">${escapeHtml(resolveSenderName(msg.sender))}</span>
        <span class="message-row__chat">
          ${chatName}
          ${chatTypeLabel ? `<span class="info-badge">${chatTypeLabel}</span>` : ""}
        </span>
        <span class="message-row__timestamp">${formatMessageTimestamp(msg.date)}</span>
        ${editedBadge}
      </div>
      <div class="message-row__text">${text}</div>
    </li>
  `;
}

/**
 * Render the view's current state (rows + pagination) from already-fetched data, without a network re-fetch — used both after loading and after a language change.
 *
 * @param {HTMLElement} root
 * @param {object} data - a PaginatedResponse<MessageOut> from the API.
 */
function renderMessagesView(root, data) {
  const t = window.TeleVaultI18n.t;

  if (data.items.length === 0) {
    root.innerHTML = `<div class="empty-state">${t("messages.empty")}</div>`;
    return;
  }

  const rowsHtml = data.items.map(renderMessageRow).join("");
  const paginationHtml = window.TeleVaultPagination.render(
    data.page,
    data.pages,
  );

  root.innerHTML = `
    <ul class="message-list">${rowsHtml}</ul>
    ${paginationHtml}
  `;

  window.TeleVaultPagination.attach(root, (delta) => {
    messagesViewState.page += delta;
    loadMessages(root);
  });
}

/** Fetch one page of messages (with current filters applied), cache it, and render it. */
async function loadMessages(root) {
  const t = window.TeleVaultI18n.t;
  root.innerHTML = `<div class="empty-state">${t("common.loading")}</div>`;

  const params = new URLSearchParams({
    page: String(messagesViewState.page),
    per_page: String(MESSAGES_PER_PAGE),
    only_edited: String(messagesViewState.onlyEdited),
  });
  if (messagesViewState.q) params.set("q", messagesViewState.q);

  let data;
  try {
    const res = await fetch(`/api/messages?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch {
    root.innerHTML = `<div class="empty-state">${t("common.error")}</div>`;
    return;
  }

  messagesViewState.lastData = data;
  renderMessagesView(root, data);
}

/**
 * Build the filter bar (search input + edited-only checkbox) once, and wire its inputs to update state and reload.
 * Idempotent guard lives in the caller (messagesViewState.initialized).
 *
 * @param {HTMLElement} filterBarRoot
 * @param {HTMLElement} listRoot - passed through to loadMessages() on filter change.
 */
function initFilterBar(filterBarRoot, listRoot) {
  const t = window.TeleVaultI18n.t;

  filterBarRoot.innerHTML = `
    <input
      type="search"
      id="messages-search"
      class="messages-filter__search"
      placeholder="${t("messages.searchPlaceholder")}"
      data-i18n-attr-placeholder="messages.searchPlaceholder"
    />
    <label class="messages-filter__toggle">
      <input type="checkbox" id="messages-only-edited" />
      <span>${t("messages.onlyEditedLabel")}</span>
    </label>
  `;

  const searchInput = filterBarRoot.querySelector("#messages-search");
  searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      messagesViewState.q = searchInput.value.trim();
      messagesViewState.page = 1;
      loadMessages(listRoot);
    }, SEARCH_DEBOUNCE_MS);
  });

  const editedCheckbox = filterBarRoot.querySelector("#messages-only-edited");
  editedCheckbox.addEventListener("change", () => {
    messagesViewState.onlyEdited = editedCheckbox.checked;
    messagesViewState.page = 1;
    loadMessages(listRoot);
  });
}

/**
 * Entry point called by app.js the first time the Messages tab is opened.
 * Guards against double-initialization (and duplicate event listeners) if called more than once across a session.
 */
function initMessagesView() {
  if (messagesViewState.initialized) return;
  messagesViewState.initialized = true;

  const filterBarRoot = document.getElementById("messages-filter-bar");
  const listRoot = document.getElementById("messages-root");
  if (!filterBarRoot || !listRoot) return;

  initFilterBar(filterBarRoot, listRoot);
  loadMessages(listRoot);
}

window.TeleVaultMessagesView = { init: initMessagesView };

// Re-render the already-fetched page in the new language — no re-fetch needed for the list,
// but the filter bar's static labels (placeholder, checkbox text) need rebuilding since they aren't data-i18n elements either.
document.addEventListener("televault:langchange", () => {
  if (!messagesViewState.initialized) return;

  const filterBarRoot = document.getElementById("messages-filter-bar");
  const listRoot = document.getElementById("messages-root");
  if (filterBarRoot) {
    // Preserve the current search text and checkbox state across the rebuild.
    const currentQ = messagesViewState.q;
    const currentOnlyEdited = messagesViewState.onlyEdited;
    initFilterBar(filterBarRoot, listRoot);
    filterBarRoot.querySelector("#messages-search").value = currentQ;
    filterBarRoot.querySelector("#messages-only-edited").checked =
      currentOnlyEdited;
  }
  if (listRoot && messagesViewState.lastData) {
    renderMessagesView(listRoot, messagesViewState.lastData);
  }
});
