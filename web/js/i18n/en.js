/**
 * English (en) translation strings.
 *
 * Keys are namespaced by area (nav.*, health.*, common.*) so this stays organized as views are added in later steps.
 * Add new keys here AND in uk.js together — TeleVaultI18n's t() falls back to the key itself if a translation is missing,
 * so a mismatch won't crash the UI, but it will silently show English/raw keys in the Ukrainian UI.
 * Keep both files in sync as a habit, not just when convenient.
 */

export const en = {
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
  "common.pageOfPrefix": "Page",
  "common.pageOfSuffix": "of",
  "common.jumpToPage": "Jump to page",
  "common.first": "First",
  "common.last": "Last",
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

  "deleted.empty": "No deleted messages found.",
  "deleted.searchPlaceholder": "Search deleted message text…",
  "deleted.viewDetails": "View details",
  "deleted.hideDetails": "Hide details",
  "deleted.noRecord": "No deletion record found.",
  "deleted.actor.channel_admin": "Deleted by a channel admin",
  "deleted.actor.self": "Deleted by you",
  "deleted.actor.unknown": "Deleted by — unknown",
  "deleted.confidence.channel_admin":
    "Only a channel admin can delete a channel post — regular subscribers cannot delete posts.",
  "deleted.confidence.self":
    "Saved Messages is only accessible to you — no one else can see it, let alone delete from it.",

  "stats.totalMessages": "Total messages",
  "stats.totalDeleted": "Deleted",
  "stats.totalEdited": "Edited",
  "stats.totalChats": "Chats",
  "stats.totalSenders": "Senders",
  "stats.archivingSince": "Archiving since",
  "stats.perChatTitle": "Per-chat breakdown",
  "stats.empty": "No chat data yet.",
  "stats.tableChat": "Chat",
  "stats.tableMessages": "Messages",
  "stats.tableDeleted": "Deleted",
  "stats.tableEdited": "Edited",
  "stats.tableLastSeen": "Last message",

  "health.statusOk": "OK",
  "health.statusDegraded": "Degraded",
  "health.dbReadable": "Database readable",
  "health.sessionExists": "Telegram session found",
  "health.messageCount": "Archived messages",
  "health.refresh": "Refresh",

  "theme.toggleLabel": "Toggle theme",
  "lang.selectLabel": "Language",
};
