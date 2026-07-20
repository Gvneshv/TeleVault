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

  // Backfill additions
  "nav.backfill": "Backfill",

  "backfill.aboutTitle": "About backfill",
  "backfill.disclaimerSession":
    "Backfill needs its own Telegram connection. The live archiver (main.py) must be stopped first — Telegram only allows one active session at a time.",
  "backfill.disclaimerDeleted":
    "Messages already deleted before a chat was first archived can never be recovered — Telegram's history API only returns what currently exists.",
  "backfill.disclaimerEdits":
    "Backfilled messages are stored as their current text only. Earlier edited versions from before archiving started cannot be recovered.",
  "backfill.disclaimerApprox":
    "Progress and time remaining are estimates based on Telegram's message counts — treat them as a rough guide, not an exact figure.",
  "backfill.disclaimerBackground":
    "Once started, backfill keeps running on the server even if you close this tab or browser.",
  "backfill.checkingConnection": "Checking live connection…",
  "backfill.connectionOn": "Live archiver is currently connected",
  "backfill.connectionOff": "Live archiver is not connected",
  "backfill.startButton": "Start backfill",
  "backfill.confirmTitle": "Start a backfill?",
  "backfill.confirmBody":
    "This will archive historical messages for the selected chat(s). It can take a long time for large histories.",
  "backfill.warningConnectionOn":
    "The live archiver looks like it's still connected. Stop it before starting a backfill.",
  "backfill.chatLabel": "Chat (optional — leave empty for all chats)",
  "backfill.chatPlaceholder": "@username or numeric ID",
  "backfill.limitLabel": "Message limit per chat (optional)",
  "backfill.limitPlaceholder": "e.g. 500",
  "backfill.confirmStart": "Start",
  "backfill.stateRunning": "Running",
  "backfill.stateCompleted": "Completed",
  "backfill.stateCancelled": "Cancelled",
  "backfill.stateError": "Error",
  "backfill.chats": "chats",
  "backfill.eta": "Est. remaining",
  "backfill.cancel": "Cancel",
  "backfill.historyTitle": "Run history",
  "backfill.noHistory": "No backfill runs yet.",
  "backfill.historyStarted": "Started",
  "backfill.historyStatus": "Status",
  "backfill.historyChats": "Chats",
  "backfill.historyStored": "Stored",
  "backfill.historySkipped": "Skipped",
  "backfill.historyDuration": "Duration",

  "messages.wholeWordLabel": "Whole word",
  "common.cancel": "Cancel",
};
