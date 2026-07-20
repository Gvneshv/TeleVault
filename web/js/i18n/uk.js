/**
 * Ukrainian (uk) translation strings.
 * Keep keys in sync with en.js — see the note there.
 */

export const uk = {
  "app.wordmark": "TeleVault",

  "nav.chats": "Чати",
  "nav.messages": "Повідомлення",
  "nav.deleted": "Видалені",
  "nav.stats": "Статистика",
  "nav.health": "Стан системи",

  "common.comingSoon": "Цей розділ ще не готовий.",
  "common.loading": "Завантаження…",
  "common.error": "Щось пішло не так.",
  "common.pageOf": "Сторінка {page} з {pages}",
  "common.pageOfPrefix": "Сторінка",
  "common.pageOfSuffix": "з",
  "common.jumpToPage": "Перейти до сторінки",
  "common.first": "Перша",
  "common.last": "Остання",
  "common.prev": "Назад",
  "common.next": "Далі",
  "common.type.private": "Приватний",
  "common.type.group": "Група",
  "common.type.supergroup": "Супергрупа",
  "common.type.channel": "Канал",

  "chats.empty": "Ще немає архівованих чатів.",
  "chats.noPreview": "Повідомлень ще немає",
  "chats.messagesLabel": "повідомлень",
  "chats.deletedLabel": "видалено",

  "messages.empty": "Повідомлень не знайдено.",
  "messages.noText": "(без тексту)",
  "messages.editedLabel": "змінено",
  "messages.searchPlaceholder": "Пошук у тексті повідомлень…",
  "messages.onlyEditedLabel": "Лише змінені",

  "deleted.empty": "Видалених повідомлень не знайдено.",
  "deleted.searchPlaceholder": "Пошук у тексті видалених повідомлень…",
  "deleted.viewDetails": "Показати деталі",
  "deleted.hideDetails": "Сховати деталі",
  "deleted.noRecord": "Запис про видалення не знайдено.",
  "deleted.actor.channel_admin": "Видалено адміністратором каналу",
  "deleted.actor.self": "Видалили ви",
  "deleted.actor.unknown": "Хто видалив — невідомо",
  "deleted.confidence.channel_admin":
    "Лише адміністратор каналу може видалити допис у каналі — звичайні підписники не можуть видаляти дописи.",
  "deleted.confidence.self":
    "Збережені повідомлення доступні лише вам — ніхто інший їх не бачить, а тим паче не може щось із них видалити.",

  "stats.totalMessages": "Усього повідомлень",
  "stats.totalDeleted": "Видалено",
  "stats.totalEdited": "Змінено",
  "stats.totalChats": "Чатів",
  "stats.totalSenders": "Відправників",
  "stats.archivingSince": "Архівується з",
  "stats.perChatTitle": "Розбивка по чатах",
  "stats.empty": "Даних про чати ще немає.",
  "stats.tableChat": "Чат",
  "stats.tableMessages": "Повідомлень",
  "stats.tableDeleted": "Видалено",
  "stats.tableEdited": "Змінено",
  "stats.tableLastSeen": "Останнє повідомлення",

  "health.statusOk": "Гаразд",
  "health.statusDegraded": "Є проблеми",
  "health.dbReadable": "База даних доступна",
  "health.sessionExists": "Сесію Telegram знайдено",
  "health.messageCount": "Заархівовано повідомлень",
  "health.refresh": "Оновити",

  "theme.toggleLabel": "Змінити тему",
  "lang.selectLabel": "Мова",

  // Backfill additions
  "nav.backfill": "Резервне заповнення",

  "backfill.aboutTitle": "Про резервне заповнення",
  "backfill.disclaimerSession":
    "Для заповнення потрібне окреме з'єднання з Telegram. Спершу зупиніть живий архіватор (main.py) — Telegram дозволяє лише одну активну сесію одночасно.",
  "backfill.disclaimerDeleted":
    "Повідомлення, видалені ще до того, як чат почали архівувати, відновити неможливо — API історії Telegram повертає лише те, що існує зараз.",
  "backfill.disclaimerEdits":
    "Заповнені повідомлення зберігаються лише в поточному вигляді. Попередні відредаговані версії до початку архівування відновити неможливо.",
  "backfill.disclaimerApprox":
    "Прогрес і залишок часу — приблизні оцінки на основі кількості повідомлень у Telegram, а не точні значення.",
  "backfill.disclaimerBackground":
    "Після запуску заповнення продовжує працювати на сервері, навіть якщо ви закриєте вкладку чи браузер.",
  "backfill.checkingConnection": "Перевірка з'єднання…",
  "backfill.connectionOn": "Живий архіватор зараз підключено",
  "backfill.connectionOff": "Живий архіватор не підключено",
  "backfill.startButton": "Почати заповнення",
  "backfill.confirmTitle": "Почати заповнення?",
  "backfill.confirmBody":
    "Це заархівує історичні повідомлення для вибраного чату (чатів). Для великих історій це може зайняти багато часу.",
  "backfill.warningConnectionOn":
    "Схоже, живий архіватор досі підключено. Зупиніть його перед запуском заповнення.",
  "backfill.chatLabel": "Чат (необов'язково — залиште порожнім для всіх чатів)",
  "backfill.chatPlaceholder": "@username або числовий ID",
  "backfill.limitLabel": "Ліміт повідомлень на чат (необов'язково)",
  "backfill.limitPlaceholder": "напр. 500",
  "backfill.confirmStart": "Почати",
  "backfill.stateRunning": "Виконується",
  "backfill.stateCompleted": "Завершено",
  "backfill.stateCancelled": "Скасовано",
  "backfill.stateError": "Помилка",
  "backfill.chats": "чатів",
  "backfill.eta": "Залишилось приблизно",
  "backfill.cancel": "Скасувати",
  "backfill.historyTitle": "Історія запусків",
  "backfill.noHistory": "Заповнень ще не було.",
  "backfill.historyStarted": "Розпочато",
  "backfill.historyStatus": "Статус",
  "backfill.historyChats": "Чатів",
  "backfill.historyStored": "Збережено",
  "backfill.historySkipped": "Пропущено",
  "backfill.historyDuration": "Тривалість",

  "messages.wholeWordLabel": "Ціле слово",
  "common.cancel": "Скасувати",
};
