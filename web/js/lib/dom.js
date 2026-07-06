/**
 * Shared DOM helpers used across views.
 *
 * Kept dependency-free and framework-free, same as the rest of web/js/ — no bundler here,
 * so this is loaded via a plain <script> tag and exposes itself on window, same pattern as TeleVaultI18n.
 */

/**
 * Minimal HTML-escaping for text before it's inserted via innerHTML.
 *
 * Used for anything that originates from Telegram or the archive (message text, chat/sender names) — never from this app itself — so it must never be trusted as-is.
 * Uses the browser's own text-node escaping rather than a hand-rolled regex, which is easy to get subtly wrong.
 *
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Wrap occurrences of `query` in <mark> tags within already-HTML-escaped text.
 *
 * Must be called AFTER escapeHtml(), not before — operating on escaped text means the regex only ever matches plain characters,
 * never HTML markup, so there's no risk of matching inside a tag or breaking the escaping.
 *
 * The query itself is escaped for regex special characters (e.g. searching literally for "a.b" or "(hi)" must not be treated as a regex pattern).
 *
 * Shared by the Messages and Deleted views — both let the user search message text and want the match visible in results.
 *
 * One known limitation: if the query contains a character escapeHtml() converts to an entity (e.g. searching for "<"),
 * it won't match the escaped "&lt;" in the text.
 * Edge case, not worth the complexity of matching against un-escaped positions for a personal archive tool.
 *
 * @param {string} escapedText - text that has already been through escapeHtml().
 * @param {string} query - raw (unescaped) search query.
 * @returns {string}
 */
function highlightMatches(escapedText, query) {
  if (!query) return escapedText;
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${escapedQuery})`, "gi");
  return escapedText.replace(regex, "<mark>$1</mark>");
}

window.TeleVaultDom = { escapeHtml, highlightMatches };
