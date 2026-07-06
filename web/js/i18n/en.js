/**
 * English (en) translation strings.
 *
 * Keys are namespaced by area (nav.*, health.*, common.*) so this stays organized as views are added in later steps.
 * Add new keys here AND in uk.js together — TeleVaultI18n.t() falls back to the key itself if a translation is missing,
 * so a mismatch won't crash the UI, but it will silently show English/raw keys in the Ukrainian UI.
 * Keep both files in sync as a habit, not just when convenient.
 */

window.TELEVAULT_I18N = window.TELEVAULT_I18N || {};
window.TELEVAULT_I18N.en = {
  "app.wordmark": "TeleVault",

  "nav.chats": "Chats",
  "nav.messages": "Messages",
  "nav.deleted": "Deleted",
  "nav.stats": "Stats",
  "nav.health": "Health",

  "common.comingSoon": "This view isn't built yet.",
  "common.loading": "Loading…",
  "common.error": "Something went wrong.",
  "common.pageOf": "Page {page} of {pages}",
  "common.prev": "Previous",
  "common.next": "Next",
  "common.type.private": "Private",
  "common.type.group": "Group",
  "common.type.supergroup": "Supergroup",
  "common.type.channel": "Channel",

  "chats.empty": "No chats archived yet.",
  "chats.noPreview": "No messages yet",
  "chats.messagesLabel": "messages",
  "chats.deletedLabel": "deleted",

  "messages.empty": "No messages found.",
  "messages.noText": "(no text)",
  "messages.editedLabel": "edited",
  "messages.searchPlaceholder": "Search message text…",
  "messages.onlyEditedLabel": "Edited only",

  "theme.toggleLabel": "Toggle theme",
  "lang.selectLabel": "Language",
};
