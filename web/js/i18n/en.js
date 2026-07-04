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

  "theme.toggleLabel": "Toggle theme",
  "lang.selectLabel": "Language",
};
